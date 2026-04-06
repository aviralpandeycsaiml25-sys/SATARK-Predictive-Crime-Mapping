from pydantic import BaseModel
from typing import List, Optional

class HeatmapPoint(BaseModel):
    lat: float
    lon: float
    weight: float  # This tells the map how "Red" the zone is

class HeatmapResponse(BaseModel):
    status: str
    data: List[HeatmapPoint]
class CrimeCreate(BaseModel):
    city: str
    category: str
    latitude: float
    longitude: float
    state: str