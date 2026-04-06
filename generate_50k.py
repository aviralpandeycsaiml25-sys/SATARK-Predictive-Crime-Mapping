import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta
import random

# 1. Connect to PostGIS
engine = create_engine("postgresql://postgres:Aviral19!@localhost:5432/satark_db")

cities = [
    ("Delhi", 28.61, 77.20), ("Mumbai", 19.07, 72.87), 
    ("Lucknow", 26.84, 80.94), ("Bengaluru", 12.97, 77.59)
]
categories = ["Theft", "Assault", "Fraud", "Robbery"]

print("⏳ Generating 50,000 realistic spatial records...")

data = []
start_date = datetime(2023, 1, 1)

for i in range(50000):
    city_name, base_lat, base_lon = random.choice(cities)
    # Add slight "jitter" to create hotspots
    lat = base_lat + np.random.normal(0, 0.1)
    lon = base_lon + np.random.normal(0, 0.1)
    
    # Create temporal patterns (More crime on weekends/nights)
    days_to_add = random.randint(0, 365)
    hours_to_add = random.choices(range(24), weights=[1,1,1,1,2,2,3,5,8,5,3,2,1,1,2,4,6,8,10,12,10,8,5,2])[0]
    ts = start_date + timedelta(days=days_to_add, hours=hours_to_add)
    
    cat = random.choice(categories)
    data.append((city_name, lat, lon, ts, cat))

# 2. Bulk Insert into PostGIS
df_large = pd.DataFrame(data, columns=['city', 'latitude', 'longitude', 'timestamp', 'category'])

with engine.connect() as conn:
    # Clear old small data
    conn.execute(text("TRUNCATE TABLE crimes;"))
    
    # Fast bulk insert
    df_large.to_sql('crimes_temp', engine, if_exists='replace', index=False)
    
    # Convert temp data to Spatial data
    conn.execute(text("""
        INSERT INTO crimes (city, latitude, longitude, timestamp, category, geom)
        SELECT city, latitude, longitude, timestamp, category, 
               ST_SetSRID(ST_Point(longitude, latitude), 4326)
        FROM crimes_temp;
    """))
    conn.execute(text("DROP TABLE crimes_temp;"))
    conn.commit()

print("🚀 PostGIS is now loaded with 50,000 records. Your Brain is ready to learn.")