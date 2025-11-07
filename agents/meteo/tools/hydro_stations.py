"""Hydro stations tool for MeteoAgent - native v2 implementation."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

import yaml
from pydantic import BaseModel

from agents.meteo.models import RawHydroStation, EnrichedHydroStation, HydroStationsResult
from services.web.adapters.omirl_adapter import get_omirl_adapter

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
THRESHOLDS_PATH = CONFIG_ROOT / "livelli_idrometrici_thresholds.yaml"
GEOGRAPHY_PATH = CONFIG_ROOT / "geography.yaml"


class HydroFilters(BaseModel):
    """Filter parameters for hydro stations query."""
    zona_allerta: Optional[str] = None
    provincia: Optional[str] = None
    comune: Optional[str] = None
    bacino: Optional[str] = None
    corso_acqua: Optional[str] = None


@lru_cache(maxsize=1)
def _load_thresholds() -> tuple[Dict[str, Dict[str, Any]], float]:
    """Load threshold config (cached)."""
    with open(THRESHOLDS_PATH) as f:
        data = yaml.safe_load(f)
    return data['thresholds'], data['analysis_config']['near_threshold_percentage']


@lru_cache(maxsize=1)
def _load_geography() -> Dict[str, Any]:
    """Load geography config (cached)."""
    with open(GEOGRAPHY_PATH) as f:
        return yaml.safe_load(f)['regions']['liguria']


def _enrich_station(raw: RawHydroStation) -> EnrichedHydroStation:
    """Add threshold analysis to raw station data."""
    thresholds, near_ratio = _load_thresholds()
    station_thresholds = thresholds.get(raw.station_code, {})
    
    yellow = station_thresholds.get('yellow')
    red = station_thresholds.get('red')
    current = raw.current_level
    
    # Determine alert level
    if current is None or yellow is None:
        alert_level = "verde"
        percentuale = None
    elif red and current >= red:
        alert_level = "rossa"
        percentuale = round((current / yellow) * 100, 1) if yellow > 0 else None
    elif current >= yellow:
        alert_level = "gialla"
        percentuale = round((current / yellow) * 100, 1) if yellow > 0 else None
    elif current >= (yellow * near_ratio):
        alert_level = "pre-soglia"
        percentuale = round((current / yellow) * 100, 1) if yellow > 0 else None
    else:
        alert_level = "verde"
        percentuale = round((current / yellow) * 100, 1) if yellow > 0 else None
    
    return EnrichedHydroStation(
        **raw.model_dump(),
        alert_level=alert_level,
        soglia_gialla=yellow,
        soglia_rossa=red,
        percentuale_soglia=percentuale
    )


def _apply_filters(stations: list[EnrichedHydroStation], filters: HydroFilters) -> list[EnrichedHydroStation]:
    """Apply user filters."""
    result = stations
    
    if filters.zona_allerta:
        result = [s for s in result if s.zona_allerta.upper() == filters.zona_allerta.upper()]
    
    if filters.provincia:
        # Normalize province - handle "Savona", "SV", or "SV/Savona"
        geo = _load_geography()
        mapping = geo['provinces']['name_to_code_mapping']
        prov_input = filters.provincia.split('/')[0].strip()  # "SV/Savona" → "SV"
        prov_code = mapping.get(prov_input, prov_input).upper()
        result = [s for s in result if s.provincia.upper() == prov_code]
    
    if filters.comune:
        result = [s for s in result if filters.comune.lower() in s.comune.lower()]
    
    if filters.bacino:
        result = [s for s in result if filters.bacino.lower() in s.bacino.lower()]
    
    if filters.corso_acqua:
        result = [s for s in result if filters.corso_acqua.lower() in s.corso_acqua.lower()]
    
    return result


def _build_summary(stations: list[EnrichedHydroStation]) -> str:
    """Template-based summary - no LLM, no v1."""
    critical = [s for s in stations if s.alert_level == "rossa"]
    warning = [s for s in stations if s.alert_level == "gialla"]
    watch = [s for s in stations if s.alert_level == "pre-soglia"]
    
    if critical:
        names = ', '.join(s.localita for s in critical[:3])
        return f"🚨 {len(critical)} stazioni in CRITICITÀ ROSSA: {names}"
    elif warning:
        names = ', '.join(s.localita for s in warning[:3])
        return f"⚠️ {len(warning)} stazioni in CRITICITÀ GIALLA: {names}"
    elif watch:
        return f"👀 {len(watch)} stazioni da monitorare (pre-soglia)"
    else:
        return f"✅ Nessuna criticità ({len(stations)} stazioni monitorate)"


async def fetch_hydro_stations(filters: HydroFilters) -> HydroStationsResult:
    """
    Main tool function - scrape, enrich, filter, summarize.
    No v1 dependencies.
    """
    print(f"\n{'='*60}")
    print(f"🔍 HYDRO STATIONS TOOL")
    print(f"{'='*60}")
    print(f"Filters: {filters.model_dump(exclude_none=True)}")
    
    # 1. Scrape data (no cache for now - keep it simple)
    print("🔄 Scraping OMIRL...")
    adapter = get_omirl_adapter()
    raw_stations = await adapter.fetch_livelli_idrometrici()
    print(f"📊 Loaded {len(raw_stations)} stations")
    
    # 2. Enrich with thresholds
    enriched = [_enrich_station(s) for s in raw_stations]
    
    # 3. Apply filters
    filtered = _apply_filters(enriched, filters)
    print(f"🎯 Filtered to {len(filtered)} stations")
    
    # 4. If generic query (no filters), show only at-risk
    is_generic = not any([
        filters.zona_allerta, filters.provincia, filters.comune,
        filters.bacino, filters.corso_acqua
    ])
    
    if is_generic:
        filtered = [s for s in filtered if s.alert_level in ["pre-soglia", "gialla", "rossa"]]
        print(f"🔍 Generic query - showing {len(filtered)} at-risk stations")
    
    # 5. Build summary
    summary = _build_summary(filtered)
    
    # 6. Count alerts
    critical = sum(1 for s in filtered if s.alert_level in ["rossa", "gialla"])
    warning = sum(1 for s in filtered if s.alert_level == "gialla")
    watch = sum(1 for s in filtered if s.alert_level == "pre-soglia")
    
    print(f"✅ {summary}")
    print(f"{'='*60}\n")
    
    return HydroStationsResult(
        stations=filtered,
        summary=summary,
        critical_count=critical,
        warning_count=warning,
        watch_count=watch,
        filters_applied=filters.model_dump(exclude_none=True)
    )
