import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime

# 1. Database Connection (Update 'password' to what you set during install)
engine = create_engine("postgresql://postgres:Aviral19!@localhost/satark_db")

# 2. Load your existing data
df = pd.read_csv("crimes.csv")

# 3. Create the table with a Spatial Column
with engine.connect() as conn:
    conn.execute(text("DROP TABLE IF EXISTS crimes;"))
    conn.execute(text("""
        CREATE TABLE crimes (
            id SERIAL PRIMARY KEY,
            city VARCHAR(100),
            latitude FLOAT,
            longitude FLOAT,
            timestamp TIMESTAMP,
            category VARCHAR(100),
            geom GEOMETRY(Point, 4326)
        );
    """))
    conn.commit()

print("✅ Spatial table created. Starting migration...")

# 4. Insert data and convert Lat/Long to Geometry objects
for index, row in df.iterrows():
    with engine.connect() as conn:
        query = text("""
            INSERT INTO crimes (city, latitude, longitude, timestamp, category, geom)
            VALUES (:city, :lat, :lon, :ts, :cat, ST_SetSRID(ST_Point(:lon, :lat), 4326))
        """)
        conn.execute(query, {
            "city": row['city'],
            "lat": row['latitude'],
            "lon": row['longitude'],
            "ts": row['timestamp'],
            "cat": row['category']
        })
        conn.commit()

print(f"🚀 Success! {len(df)} records migrated to PostGIS.")