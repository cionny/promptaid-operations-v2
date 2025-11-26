"""Rain stations tool for MeteoAgent - native v2 implementation."""

from pathlib import Path
from typing import Dict, Any
from functools import lru_cache

import yaml

from agents.meteo.models import (
    RainFilters,
    RawRainData,
    EnrichedRainData,
    RainStationsResult
)
from services.web.adapters.omirl_adapter import get_omirl_adapter

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
CONFIG_PATH = CONFIG_ROOT / "meteo_config.yaml"


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


def _enrich_rain_data(raw: RawRainData) -> EnrichedRainData:
    """
    Add threshold analysis to raw rain data.
    RawRainData is already per time period, so this is 1:1 enrichment.
    """
    config = _load_thresholds()
    
    # Get thresholds for this time period
    period_config = config['time_periods'].get(raw.time_period, {})
    thresholds = period_config.get('thresholds', {})
    
    yellow_config = thresholds.get('yellow', {})
    red_config = thresholds.get('red', {})
    
    yellow_min = yellow_config.get('min')
    yellow_max = yellow_config.get('max')
    red_min = red_config.get('min')
    
    # Determine criticality
    if red_min and raw.max_mm >= red_min:
        criticita = "elevata"
        above_yellow = True
        above_red = True
    elif yellow_min and raw.max_mm >= yellow_min:
        criticita = "moderata"
        above_yellow = True
        above_red = False
    else:
        criticita = "nessuna"
        above_yellow = False
        above_red = False
    
    return EnrichedRainData(
        **raw.model_dump(),
        criticita=criticita,
        soglia_gialla_min=yellow_min,
        soglia_gialla_max=yellow_max,
        soglia_rossa_min=red_min,
        above_yellow=above_yellow,
        above_red=above_red
    )


def _apply_filters(data: list[EnrichedRainData], filters: RainFilters) -> list[EnrichedRainData]:
    """Apply user filters."""
    result = data
    
    # Filter by zona (zones are named A, B, C, D, E)
    if filters.zona_allerta:
        result = [d for d in result 
                  if d.location_type == "zona" 
                  and d.location.upper() == filters.zona_allerta.upper()]
    
    # Filter by provincia (full names: Genova, Savona, Imperia, La Spezia)
    if filters.provincia:
        result = [d for d in result 
                  if d.location_type == "provincia" 
                  and filters.provincia.lower() in d.location.lower()]
    
    # Note: time_period already filtered before enrichment in fetch_rain_stations()
    return result


def _build_summary(data: list[EnrichedRainData], time_period: str) -> str:
    """Template-based summary - no LLM."""
    if not data:
        return f"✅ Situazione normale - nessuna criticità rilevata nelle ultime {time_period}"
    
    critical = [d for d in data if d.criticita == "elevata"]
    warning = [d for d in data if d.criticita == "moderata"]
    
    if critical:
        locations = ', '.join(d.location for d in critical[:3])
        more = f" (e altre {len(critical)-3})" if len(critical) > 3 else ""
        max_val = max(d.max_mm for d in critical)
        return f"🚨 CRITICITÀ ELEVATA ({time_period}): {len(critical)} località in allerta - max {max_val}mm in {locations}{more}"
    elif warning:
        locations = ', '.join(d.location for d in warning[:3])
        more = f" (e altre {len(warning)-3})" if len(warning) > 3 else ""
        max_val = max(d.max_mm for d in warning)
        return f"⚠️ CRITICITÀ MODERATA ({time_period}): {len(warning)} località in allerta - max {max_val}mm in {locations}{more}"
    else:
        max_entry = max(data, key=lambda d: d.max_mm)
        return f"✅ Situazione normale ({time_period}) - max {max_entry.max_mm}mm in {max_entry.location}"


async def fetch_rain_stations(filters: RainFilters) -> RainStationsResult:
    """
    Main tool function - scrape, enrich, filter, summarize.
    Direct Pydantic pipeline: RawRainData → EnrichedRainData → RainStationsResult
    """
    print(f"\n{'='*60}")
    print(f"🌧️  RAIN STATIONS TOOL")
    print(f"{'='*60}")
    print(f"Filters: {filters.model_dump(exclude_none=True)}")
    
    # Normalize time period
    config = _load_thresholds()
    time_period = _normalize_time_period(filters.time_period, config)
    print(f"📅 Time period: {time_period}")
    
    # 1. Scrape data (already returns one RawRainData per cell/time period)
    print("🔄 Scraping OMIRL...")
    adapter = get_omirl_adapter()
    raw_data = await adapter.fetch_precipitazioni()
    print(f"📊 Loaded {len(raw_data)} rain data entries")
    
    # 2. Filter by requested time period first
    raw_filtered = [r for r in raw_data if r.time_period == time_period]
    print(f"📅 Filtered to {len(raw_filtered)} entries for {time_period}")
    
    # 3. Enrich with thresholds (1:1 enrichment)
    enriched = [_enrich_rain_data(raw) for raw in raw_filtered]
    
    # 4. Apply location filters
    filtered = _apply_filters(enriched, filters)
    print(f"🎯 Filtered to {len(filtered)} entries")
    
    # 5. If generic query (no location filters), show only at-risk
    is_generic = not any([filters.zona_allerta, filters.provincia])
    
    if is_generic:
        filtered = [d for d in filtered if d.criticita != "nessuna"]
        print(f"🔍 Generic query - showing {len(filtered)} at-risk locations")
    
    # 6. Build summary
    summary = _build_summary(filtered, time_period)
    
    # 7. Calculate stats
    critical_count = sum(1 for d in filtered if d.above_red)
    warning_count = sum(1 for d in filtered if d.above_yellow and not d.above_red)
    
    max_entry = max(filtered, key=lambda d: d.max_mm) if filtered else None
    max_accumulation = max_entry.max_mm if max_entry else 0.0
    max_location = max_entry.location if max_entry else "N/A"
    max_station = max_entry.max_station if max_entry else "N/A"
    max_time = max_entry.max_time if max_entry else "N/A"
    
    print(f"✅ {summary}")
    print(f"{'='*60}\n")
    
    return RainStationsResult(
        data=filtered,
        summary=summary,
        critical_count=critical_count,
        warning_count=warning_count,
        max_accumulation_mm=max_accumulation,
        max_location=max_location,
        max_station=max_station,
        max_time=max_time,
        time_period=time_period,
        filters_applied=filters.model_dump(exclude_none=True)
    )
