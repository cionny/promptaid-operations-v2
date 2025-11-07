"""Rain stations tool for MeteoAgent - native v2 implementation."""

from pathlib import Path
from typing import Optional, Dict, Any, Literal
from functools import lru_cache

import yaml
from pydantic import BaseModel

from agents.meteo.models import RawRainData, EnrichedRainData, RainStationsResult
from services.web.adapters.omirl_adapter import get_omirl_adapter

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
CONFIG_PATH = CONFIG_ROOT / "meteo_config.yaml"


class RainFilters(BaseModel):
    """Filter parameters for rain data query."""
    zona_allerta: Optional[Literal["A", "B", "C", "D", "E"]] = None
    provincia: Optional[Literal["Genova", "Savona", "Imperia", "La Spezia"]] = None
    time_period: str = "1h"  # default to 1 hour


@lru_cache(maxsize=1)
def _load_thresholds() -> Dict[str, Any]:
    """Load precipitation threshold config from unified meteo_config.yaml (cached)."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
        return data['tools']['precipitazioni']


@lru_cache(maxsize=1)
def _load_geography() -> Dict[str, Any]:
    """Load geography config from unified meteo_config.yaml (cached)."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
        return data.get('geography', {})


def _normalize_time_period(period: str, config: Dict[str, Any]) -> str:
    """Normalize user input to config time period keys."""
    period_lower = period.lower().strip()
    
    # Direct match
    if period in config['time_periods']:
        return period
    
    # Match by labels
    for key, data in config['time_periods'].items():
        if period_lower in [label.lower() for label in data.get('labels', [])]:
            return key
    
    # Default fallback
    return config.get('default_time_period', '1h')


def _enrich_rain_data(raw: RawRainData, time_period: str) -> list[EnrichedRainData]:
    """
    Expand raw data into enriched entries - one per time period.
    Returns list because raw has multiple time periods.
    """
    config = _load_thresholds()
    enriched = []
    
    # If specific time period requested, only process that one
    periods_to_process = [time_period] if time_period else raw.accumulation_mm.keys()
    
    for period in periods_to_process:
        accumulation = raw.accumulation_mm.get(period)
        if accumulation is None:
            continue
        
        # Get thresholds for this period
        period_config = config['time_periods'].get(period, {})
        thresholds = period_config.get('thresholds', {})
        
        yellow_min = thresholds.get('yellow', {}).get('min')
        red_min = thresholds.get('red', {}).get('min')
        
        # Determine alert level
        if red_min and accumulation >= red_min:
            alert_level = "rossa"
            percentuale = round((accumulation / yellow_min) * 100, 1) if yellow_min and yellow_min > 0 else None
        elif yellow_min and accumulation >= yellow_min:
            alert_level = "gialla"
            percentuale = round((accumulation / yellow_min) * 100, 1) if yellow_min and yellow_min > 0 else None
        else:
            alert_level = "verde"
            percentuale = round((accumulation / yellow_min) * 100, 1) if yellow_min and yellow_min > 0 else None
        
        enriched.append(EnrichedRainData(
            location=raw.location,
            location_type=raw.location_type,
            accumulation_mm=accumulation,
            time_period=period,
            alert_level=alert_level,
            soglia_gialla=yellow_min,
            soglia_rossa=red_min,
            percentuale_soglia=percentuale
        ))
    
    return enriched


def _apply_filters(data: list[EnrichedRainData], filters: RainFilters) -> list[EnrichedRainData]:
    """Apply user filters."""
    result = data
    
    # Filter by zona (zones are named A, B, C, D, E)
    if filters.zona_allerta:
        result = [d for d in result if d.location_type == "zona" and d.location.upper() == filters.zona_allerta.upper()]
    
    # Filter by provincia (full names: Genova, Savona, Imperia, La Spezia)
    if filters.provincia:
        result = [d for d in result if d.location_type == "provincia" and filters.provincia.lower() in d.location.lower()]
    
    return result


def _build_summary(data: list[EnrichedRainData], time_period: str) -> str:
    """Template-based summary - no LLM."""
    if not data:
        return f"✅ Nessun dato disponibile per il periodo {time_period}"
    
    critical = [d for d in data if d.alert_level == "rossa"]
    warning = [d for d in data if d.alert_level == "gialla"]
    
    if critical:
        locations = ', '.join(d.location for d in critical[:3])
        max_val = max(d.accumulation_mm for d in critical)
        return f"🚨 CRITICITÀ ROSSA ({time_period}): {len(critical)} zone - max {max_val}mm in {locations}"
    elif warning:
        locations = ', '.join(d.location for d in warning[:3])
        max_val = max(d.accumulation_mm for d in warning)
        return f"⚠️  ALLERTA GIALLA ({time_period}): {len(warning)} zone - max {max_val}mm in {locations}"
    else:
        max_entry = max(data, key=lambda d: d.accumulation_mm)
        return f"✅ Situazione normale ({time_period}) - max {max_entry.accumulation_mm}mm in {max_entry.location}"


async def fetch_rain_stations(filters: RainFilters) -> RainStationsResult:
    """
    Main tool function - scrape, enrich, filter, summarize.
    No v1 dependencies.
    """
    print(f"\n{'='*60}")
    print(f"🌧️  RAIN STATIONS TOOL")
    print(f"{'='*60}")
    print(f"Filters: {filters.model_dump(exclude_none=True)}")
    
    # Normalize time period
    config = _load_thresholds()
    time_period = _normalize_time_period(filters.time_period, config)
    print(f"📅 Time period: {time_period}")
    
    # 1. Scrape data
    print("🔄 Scraping OMIRL...")
    adapter = get_omirl_adapter()
    raw_data = await adapter.fetch_precipitazioni()
    print(f"📊 Loaded {len(raw_data)} locations")
    
    # 2. Enrich with thresholds - expand to individual time periods
    enriched = []
    for raw in raw_data:
        enriched.extend(_enrich_rain_data(raw, time_period))
    
    # 3. Apply filters
    filtered = _apply_filters(enriched, filters)
    print(f"🎯 Filtered to {len(filtered)} entries")
    
    # 4. If generic query (no location filters), show only at-risk
    is_generic = not any([filters.zona_allerta, filters.provincia])
    
    if is_generic:
        filtered = [d for d in filtered if d.alert_level in ["gialla", "rossa"]]
        print(f"🔍 Generic query - showing {len(filtered)} at-risk locations")
    
    # 5. Build summary
    summary = _build_summary(filtered, time_period)
    
    # 6. Calculate stats
    critical = sum(1 for d in filtered if d.alert_level == "rossa")
    warning = sum(1 for d in filtered if d.alert_level == "gialla")
    
    max_entry = max(filtered, key=lambda d: d.accumulation_mm) if filtered else None
    max_accumulation = max_entry.accumulation_mm if max_entry else 0.0
    max_location = max_entry.location if max_entry else "N/A"
    
    print(f"✅ {summary}")
    print(f"{'='*60}\n")
    
    return RainStationsResult(
        data=filtered,
        summary=summary,
        critical_count=critical,
        warning_count=warning,
        max_accumulation_mm=max_accumulation,
        max_location=max_location,
        time_period=time_period,
        filters_applied=filters.model_dump(exclude_none=True)
    )
