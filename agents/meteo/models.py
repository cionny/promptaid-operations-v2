"""
Pydantic models for MeteoAgent
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class RawHydroStation(BaseModel):
    """Direct mapping from OMIRL table scraping - no enrichment."""
    
    station_code: str
    localita: str
    provincia: str
    comune: str
    bacino: str
    corso_acqua: str
    current_level: Optional[float] = None
    current_time: Optional[str] = None
    max_24h: Optional[float] = None
    max_24h_time: Optional[str] = None
    zona_allerta: str


class EnrichedHydroStation(RawHydroStation):
    """Adds threshold analysis from livelli_idrometrici_thresholds.yaml."""
    
    alert_level: Literal["verde", "pre-soglia", "gialla", "rossa"]
    soglia_gialla: Optional[float] = None
    soglia_rossa: Optional[float] = None
    percentuale_soglia: Optional[float] = None


class HydroStationsResult(BaseModel):
    """Final tool output."""
    
    stations: List[EnrichedHydroStation]
    summary: str
    critical_count: int
    warning_count: int
    watch_count: int
    filters_applied: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)


class RawRainData(BaseModel):
    """Direct mapping from OMIRL rain table scraping - no enrichment."""
    
    location: str  # zona or provincia name
    location_type: Literal["zona", "provincia"]
    accumulation_mm: Dict[str, Optional[float]]  # e.g., {"1h": 5.2, "3h": 12.1, ...}


class EnrichedRainData(BaseModel):
    """Single time period with threshold analysis."""
    
    location: str
    location_type: Literal["zona", "provincia"]
    accumulation_mm: float
    time_period: str
    alert_level: Literal["verde", "gialla", "rossa"]
    soglia_gialla: Optional[float] = None
    soglia_rossa: Optional[float] = None
    percentuale_soglia: Optional[float] = None


class RainStationsResult(BaseModel):
    """Final tool output."""
    
    data: List[EnrichedRainData]
    summary: str
    critical_count: int
    warning_count: int
    max_accumulation_mm: float
    max_location: str
    time_period: str
    filters_applied: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
