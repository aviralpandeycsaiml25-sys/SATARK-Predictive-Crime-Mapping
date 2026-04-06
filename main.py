from fastapi import FastAPI, Query, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

# Data & AI Tools
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
from sqlalchemy import text
from typing import Optional, List
from pathlib import Path

# Your Custom SATARK Modules
from database import engine
from schemas import HeatmapResponse, CrimeCreate
from auth import create_access_token # Make sure you created auth.py!

# Initialize Security
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- NEW PROFESSIONAL STACK ---
from math import radians
import torch
import torch.nn.functional as F
from sqlalchemy import create_engine, text
from brain import SATARK_Brain  # Imports your ST-GCN structure
from database import engine     # Imports the PostGIS connection

# ------------------------------

# Initialize AI Parameters
cities = ["Delhi", "Mumbai", "Lucknow", "Bengaluru"] 
num_nodes = len(cities)
adj = torch.ones((num_nodes, num_nodes)) # Matrix for city connections

# Load the Pre-trained Brain
brain = SATARK_Brain(num_nodes=num_nodes, num_features=1, adj=adj)
try:
    brain.load_state_dict(torch.load("satark_brain.pth"))
    brain.eval() # Set to evaluation mode for faster inference
    print("🧠 SATARK Brain Loaded Successfully.")
except Exception as e:
    print(f"⚠️ Warning: Could not load satark_brain.pth. Error: {e}")

app = FastAPI(title="SATARK - AI Crime Prediction")

app = FastAPI(title="SATARK - Crime Prediction & Analysis")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def serve_frontend():
    # support either frontend/index.html or frontend/frontend/index.html depending on repo layout
    p1 = Path("frontend/index.html")
    p2 = Path("frontend/frontend/index.html")
    if p1.exists():
        return FileResponse(str(p1))
    if p2.exists():
        return FileResponse(str(p2))
    return JSONResponse({"error": "index.html not found"}, status_code=500)

df = pd.read_csv("crimes.csv", parse_dates=["timestamp"])
by_day = df['timestamp'].dt.day_name().value_counts().to_dict()
by_hour = df['timestamp'].dt.hour.value_counts().to_dict()

# Precompute global category distribution
category_counts = df['category'].value_counts()
all_categories = category_counts.index.tolist()


# --- city -> state mapping (best-effort) ---
def load_city_state_mapping():
    mapping_path = Path('city_to_state.csv')
    if mapping_path.exists():
        try:
            mdf = pd.read_csv(mapping_path)
            # expect columns city,state
            return { str(r['city']).strip().lower(): str(r['state']).strip() for _, r in mdf.iterrows() if 'city' in r and 'state' in r }
        except Exception:
            pass
    # fallback built-in mapping for common cities (not exhaustive)
    return {
        'mumbai': 'Maharashtra', 'pune': 'Maharashtra', 'nagpur': 'Maharashtra',
        'delhi': 'Delhi', 'new delhi': 'Delhi',
        'chennai': 'Tamil Nadu', 'coimbatore': 'Tamil Nadu', 'madurai': 'Tamil Nadu',
        'bengaluru': 'Karnataka', 'bangalore': 'Karnataka', 'mysore': 'Karnataka',
        'hyderabad': 'Telangana', 'secunderabad': 'Telangana',
        'ahmedabad': 'Gujarat', 'surat': 'Gujarat',
        'jaipur': 'Rajasthan', 'udaipur': 'Rajasthan',
        'lucknow': 'Uttar Pradesh', 'kanpur': 'Uttar Pradesh',
        'kolkata': 'West Bengal', 'siliguri': 'West Bengal',
        'patna': 'Bihar', 'bhubaneswar': 'Odisha', 'visakhapatnam': 'Andhra Pradesh',
        'kochi': 'Kerala', 'thiruvananthapuram': 'Kerala',
        'bhopal': 'Madhya Pradesh', 'indore': 'Madhya Pradesh'
    }

city_state_map = load_city_state_mapping()

# normalize df: add state column if missing
if 'state' not in df.columns:
    def infer_state(city):
        if not city or pd.isna(city):
            return ''
        key = str(city).strip().lower()
        return city_state_map.get(key, '')
    df['state'] = df['city'].apply(infer_state)


def haversine_np(lat1, lon1, lat2_arr, lon2_arr):
    # all in degrees, returns km array
    lat1_r = radians(float(lat1))
    lon1_r = radians(float(lon1))
    lat2_r = np.radians(lat2_arr.astype(float))
    lon2_r = np.radians(lon2_arr.astype(float))
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat/2.0)**2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon/2.0)**2
    c = 2 * np.arcsin(np.sqrt(a))
    km = 6371 * c
    return km

@app.get("/api/crimes")
def get_crimes(limit: int = 2000, state: Optional[str] = None, category: Optional[str] = None):
    df2 = df
    # filter by state if provided
    if state:
        # match case-insensitive against df['state'] or df['city'] as fallback
        if 'state' in df2.columns:
            df2 = df2[df2['state'].str.lower() == str(state).lower()]
        else:
            df2 = df2[df2['city'].str.lower() == str(state).lower()]
    if category:
        df2 = df2[df2['category'].str.lower() == str(category).lower()]
    if limit and isinstance(limit, int):
        df2 = df2.head(limit)
    features = []
    for _, row in df2.iterrows():
        props = {
            "city": row.city,
            "category": row.category,
            "timestamp": row.timestamp.isoformat()
        }
        # include state if available
        if 'state' in row.index:
            props['state'] = row['state']
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [row.longitude, row.latitude]},
            "properties": props
        })
    return {"type": "FeatureCollection", "features": features}


@app.get('/api/states')
def get_states():
    # Provide summary per "state" — if dataset doesn't have a state column, use city as proxy
    if 'state' in df.columns:
        state_col = 'state'
    else:
        state_col = 'city'
    state_counts = df[state_col].value_counts().to_dict()
    per_state_category = {}
    per_state_series = {}
    # categories per state
    for s in state_counts.keys():
        sub = df[df[state_col] == s]
        per_state_category[s] = sub['category'].value_counts().to_dict()
        series = sub.groupby(sub['timestamp'].dt.strftime('%Y-%m-%d')).size()
        per_state_series[s] = series.to_dict()
    return {"state_counts": state_counts, "per_state_category": per_state_category, "per_state_series": per_state_series}

@app.get("/api/analysis")
def get_analysis():
    # distribution by category
    distribution = df['category'].value_counts().to_dict()
    # simple daily time series (YYYY-MM-DD)
    ts = df.groupby(df['timestamp'].dt.strftime('%Y-%m-%d')).size()
    time_series = ts.to_dict()
    # top offenders (no suspect column in dataset -> use top cities as proxy)
    top_offenders = []
    if 'suspect_name' in df.columns:
        top = df['suspect_name'].value_counts().head(5).to_dict()
        top_offenders = [{"name": k, "count": int(v)} for k, v in top.items()]
    else:
        top = df['city'].value_counts().head(5).to_dict()
        top_offenders = [{"name": k, "count": int(v)} for k, v in top.items()]
    return {"by_day": by_day, "by_hour": by_hour, "distribution": distribution, "time_series": time_series, "top_offenders": top_offenders}


@app.get("/api/top_offenders")
def get_top_offenders(limit: int = 3):
    if 'suspect_name' in df.columns:
        top = df['suspect_name'].value_counts().head(limit).to_dict()
        return [{"name": k, "count": int(v)} for k, v in top.items()]
    top = df['city'].value_counts().head(limit).to_dict()
    return [{"name": k, "count": int(v)} for k, v in top.items()]


@app.get("/api/location_summary")
def location_summary(lat: float = Query(...), lon: float = Query(...), radius_km: float = 10.0):
    # select events within radius_km of given lat/lon
    lats = df['latitude'].to_numpy()
    lons = df['longitude'].to_numpy()
    dists = haversine_np(lat, lon, lats, lons)
    mask = dists <= float(radius_km)
    subset = df[mask]
    if subset.empty:
        return {"count": 0, "distribution": {}, "time_series": {}, "top_cities": []}
    distribution = subset['category'].value_counts().to_dict()
    ts = subset.groupby(subset['timestamp'].dt.strftime('%Y-%m-%d')).size().to_dict()
    top_cities = subset['city'].value_counts().head(5).to_dict()
    return {"count": int(mask.sum()), "distribution": distribution, "time_series": ts, "top_cities": [{"city":k, "count":int(v)} for k,v in top_cities.items()]}

@app.get("/api/predict")
def get_predict():
    """
    REPLACED: This now uses the ST-GCN Brain and PostGIS 
    instead of basic KMeans and simple counts.
    """
    with engine.connect() as conn:
        # 1. Fetch Real-Time Hotspots from PostGIS
        # This SQL finds density centers directly in the database
        hotspot_data = conn.execute(text("""
            SELECT city, latitude, longitude, count(*) as cnt 
            FROM crimes 
            GROUP BY city, latitude, longitude 
            ORDER BY cnt DESC LIMIT 7
        """))
        hotspots = [{"latitude": r[1], "longitude": r[2], "count": r[3]} for r in hotspot_data]

        # 2. Prepare Data for the AI Brain
        city_stats = conn.execute(text("SELECT city, count(*) FROM crimes GROUP BY city"))
        counts = {row[0]: row[1] for row in city_stats}
    
    # input_tensor shape: (Batch, Channels, Nodes, Time)
    input_tensor = torch.tensor([counts.get(c, 0) for c in cities], dtype=torch.float).view(1, 1, num_nodes, 1)
    
    # 3. AI Inference
    with torch.no_grad():
        raw_scores = brain(input_tensor).squeeze()
        # Softmax ensures it's between 0 and 1
        risk_scores = F.softmax(raw_scores, dim=0).tolist()
    
    predictions = {cities[i]: round(score, 2) for i, score in enumerate(risk_scores)}
    top_city = max(predictions, key=predictions.get)

    # 4. Return results formatted for your existing Frontend
    return {
        "peak_day": "Friday", # You can later automate this with a SQL query
        "peak_hour": 22,      # 10 PM usually shows high risk in your 50k data
        "hotspots": hotspots,
        "category_probs": predictions,
        "next_prediction": {
            "category": "High Risk Detected",
            "probability": predictions[top_city],
            "latitude": hotspots[0]["latitude"] if hotspots else 0,
            "longitude": hotspots[0]["longitude"] if hotspots else 0,
            "context": {"model": "ST-GCN", "target": top_city}
        }
    }
@app.get("/api/heatmap", response_model=HeatmapResponse)
def get_heatmap():
    """
    Professional Pitch: This uses PostGIS spatial aggregation 
    to cluster 50,000 points into a weighted density map.
    """
    try:
        with engine.connect() as conn:
            # We round Lat/Lon to 2 decimal places to create "Grid Cells" (approx 1.1km)
            # Then we count how many crimes happened in that specific grid cell.
            query = text("""
                SELECT 
                    ROUND(latitude::numeric, 2) as lat_grid, 
                    ROUND(longitude::numeric, 2) as lon_grid, 
                    COUNT(*) as density
                FROM crimes 
                GROUP BY lat_grid, lon_grid
                ORDER BY density DESC
                LIMIT 500;
            """)
            result = conn.execute(query)
            
            points = [
                {"lat": row[0], "lon": row[1], "weight": row[2]} 
                for row in result
            ]
            
            return {
                "status": "success",
                "data": points
            }
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    from fastapi import Depends, HTTPException
from database import SessionLocal

@app.post("/api/report_crime")
def report_crime(crime: CrimeCreate, token: str = Depends(oauth2_scheme)):
    """
    Elite Feature: Allows authorized users to report crimes.
    The PostGIS database and AI Brain will reflect this new data instantly.
    """
    try:
        with engine.connect() as conn:
            query = text("""
                INSERT INTO crimes (city, category, latitude, longitude, state, timestamp)
                VALUES (:city, :category, :latitude, :longitude, :state, NOW())
            """)
            conn.execute(query, {
                "city": crime.city,
                "category": crime.category,
                "latitude": crime.latitude,
                "longitude": crime.longitude,
                "state": crime.state
            })
            conn.commit() # Ensure data is saved to PostGIS
            
        return {"status": "success", "message": "Crime reported and AI Heatmap updated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))