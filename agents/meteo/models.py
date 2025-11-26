"""
Pydantic models for MeteoAgent
"""

from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# ============================================================================
# HYDRO MODELS
# ============================================================================

class HydroFilters(BaseModel):
    """Filter parameters for hydro stations query."""
    localita: Optional[str] = None
    zona_allerta: Optional[str] = None
    provincia: Optional[str] = None
    comune: Optional[str] = None
    bacino: Optional[str] = None
    corso_acqua: Optional[str] = None


class RawHydroStation(BaseModel):
    """Direct mapping from OMIRL table scraping - no enrichment."""
    
    # Dimensions from OMIRL data, always provided by OMIRL
    localita: str
    provincia: str # Two letter code
    comune: str
    bacino: str
    corso_acqua: str

    # Measurements from OMIRL data
    max_24h: float
    max_24h_time: str
    last_level: float
    reference_time: str

    # Not in OMIRL columns, added by scraper logic, there is one table per Alert Zone
    zona_allerta: str # corresponding tables are in omirl_adapter.py


class EnrichedHydroStation(RawHydroStation):
    """Adds threshold analysis from livelli_idrometrici_thresholds.yaml."""
    
    criticita: Literal["nessuna", "moderata", "elevata"]
    soglia_gialla: Optional[float] = None
    soglia_rossa: Optional[float] = None

    above_yellow: bool = False
    above_red: bool = False
    near_yellow: bool = False # within 10% of yellow threshold, no need for "near_red"since red is usually close to yellow and above yellow needs contnous monitoring

class HydroStationsResult(BaseModel):
    """Final tool output."""
    
    stations: List[EnrichedHydroStation]
    summary: str

    # Alert counts
    critical_count: int # number of stations above red threshold
    warning_count: int # number of stations above yellow threshold
    watch_count: int # number of stations near yellow threshold

    # Metadata about the query
    filters_applied: Optional[HydroFilters] = None
    timestamp: datetime = Field(default_factory=datetime.now)

# ============================================================================
# RAIN MODELS
# ============================================================================

class RainFilters(BaseModel):
    """Filter parameters for rain data query."""
    zona_allerta: Optional[Literal["A", "B", "C", "D", "E"]] = None
    provincia: Optional[Literal["Genova", "Savona", "Imperia", "La Spezia"]] = None
    time_period: str = "1h"  # Default to 1 hour accumulation


class RawRainData(BaseModel):
    """Direct mapping from OMIRL rain table scraping - no enrichment."""
    
    location: str  # "A", "B", "Imperia", "Savona"
    location_type: Literal["zona", "provincia"]
    time_period: str  # "5'", "15'", "1h", "3h"
    
    # Parsed from cell text
    max_mm: float
    max_time: str  # "02:30"
    max_station: str  # "Rocchetta Nervina"


class EnrichedRainData(RawRainData):
    """Single time period with threshold analysis."""
    
    criticita: Literal["nessuna", "moderata", "elevata"]
    
    # Time-period-specific thresholds from config
    soglia_gialla_min: float  # Yellow range min
    soglia_gialla_max: float  # Yellow range max
    soglia_rossa_min: float   # Red threshold
    
    # Boolean flags for quick filtering
    above_yellow: bool = False  # max_mm >= soglia_gialla_min
    above_red: bool = False     # max_mm >= soglia_rossa_min


class RainStationsResult(BaseModel):
    """Final tool output."""
    
    data: List[EnrichedRainData]
    summary: str

    # Alert counts
    critical_count: int # number of locations above red threshold
    warning_count: int # number of locations above yellow threshold

    # Maximum precipitation info
    max_accumulation_mm: float
    max_location: str
    max_station: str
    max_time: str
    time_period: str

    # Metadata about the query
    filters_applied: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.now)
