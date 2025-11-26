"""Hydro stations tool for MeteoAgent - native v2 implementation."""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any
from functools import lru_cache

import yaml

from agents.meteo.models import (
    HydroFilters,
    RawHydroStation,
    EnrichedHydroStation,
    HydroStationsResult
)
from services.web.adapters.omirl_adapter import get_omirl_adapter

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
CONFIG_PATH = CONFIG_ROOT / "meteo_config.yaml"


@lru_cache(maxsize=1)
def _load_thresholds() -> Dict[str, Dict[str, Any]]:
    """Load threshold config from unified meteo_config.yaml (cached)."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
        return data['tools']['hydro_stations']['thresholds']


@lru_cache(maxsize=1)
def _load_geography() -> Dict[str, Any]:
    """Load geography config from unified meteo_config.yaml (cached)."""
    with open(CONFIG_PATH) as f:
        data = yaml.safe_load(f)
        return data.get('geography', {})


def _enrich_station(raw: RawHydroStation) -> EnrichedHydroStation:
    """Add threshold analysis to raw station data."""
    thresholds = _load_thresholds()
    
    # Extract station code from localita: "Tiglieto [TIGLT]" → "TIGLT"
    station_code = None
    if '[' in raw.localita and ']' in raw.localita:
        station_code = raw.localita.split('[')[1].split(']')[0].strip()
    
    station_thresholds = thresholds.get(station_code, {}) if station_code else {}
    
    yellow = station_thresholds.get('soglia_gialla')
    red = station_thresholds.get('soglia_rossa')
    current = raw.last_level
    
    # Determine criticality
    if current is None or yellow is None:
        criticita = "nessuna"
        above_yellow = False
        above_red = False
        near_yellow = False
    elif red and current >= red:
        criticita = "elevata"
        above_yellow = True
        above_red = True
        near_yellow = False
    elif current >= yellow:
        criticita = "moderata"
        above_yellow = True
        above_red = False
        near_yellow = False
    elif yellow > 0 and current >= (yellow * 0.9):  # Within 10% of yellow
        criticita = "nessuna"
        above_yellow = False
        above_red = False
        near_yellow = True
    else:
        criticita = "nessuna"
        above_yellow = False
        above_red = False
        near_yellow = False
    
    return EnrichedHydroStation(
        **raw.model_dump(),
        criticita=criticita,
        soglia_gialla=yellow,
        soglia_rossa=red,
        above_yellow=above_yellow,
        above_red=above_red,
        near_yellow=near_yellow
    )


def _apply_filters(stations: list[EnrichedHydroStation], filters: HydroFilters) -> list[EnrichedHydroStation]:
    """Apply user filters."""
    result = stations
    
    if filters.localita:
        result = [s for s in result if filters.localita.lower() in s.localita.lower()]
    
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
    """Template-based summary - no LLM."""
    if not stations:
        return "❌ Nessuna stazione trovata con i filtri specificati"
    
    critical = [s for s in stations if s.criticita == "elevata"]
    warning = [s for s in stations if s.criticita == "moderata"]
    watch = [s for s in stations if s.near_yellow]
    
    # Build summary based on criticality
    if critical:
        names = ', '.join(s.localita.split('[')[0].strip() for s in critical[:3])
        summary = f"🚨 {len(critical)} stazioni in CRITICITÀ ELEVATA: {names}"
    elif warning:
        names = ', '.join(s.localita.split('[')[0].strip() for s in warning[:3])
        summary = f"⚠️ {len(warning)} stazioni in CRITICITÀ MODERATA: {names}"
    elif watch:
        summary = f"👀 {len(watch)} stazioni da monitorare (vicino alla soglia gialla)"
    else:
        summary = f"✅ Tutti i livelli idrometrici sono nella norma"
    
    # If specific stations requested (1-3), add details
    if len(stations) <= 3:
        summary += "\n\n**Dettagli stazioni:**\n"
        for s in stations:
            emoji = {"nessuna": "✅", "moderata": "⚠️", "elevata": "🚨"}.get(s.criticita, "")
            station_name = s.localita.split('[')[0].strip()
            summary += f"\n{emoji} **{station_name}** ({s.corso_acqua})"
            
            if s.max_24h is not None:
                summary += f"\n- Massimo 24h: {s.max_24h:.2f} m alle {s.max_24h_time}"
            
            if s.last_level is not None:
                summary += f"\n- Livello attuale: {s.last_level:.2f} m ({s.reference_time})"
            
            summary += f"\n- Criticità: {s.criticita}"
            
            if s.soglia_gialla:
                summary += f"\n- Soglia gialla: {s.soglia_gialla:.2f} m"
            if s.soglia_rossa:
                summary += f", Soglia rossa: {s.soglia_rossa:.2f} m"
    
    return summary


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
        filters.localita, filters.zona_allerta, filters.provincia, 
        filters.comune, filters.bacino, filters.corso_acqua
    ])
    
    if is_generic:
        filtered = [s for s in filtered if s.criticita != "nessuna" or s.near_yellow]
        print(f"🔍 Generic query - showing {len(filtered)} at-risk stations")
    
    # 5. Build summary
    summary = _build_summary(filtered)
    
    # 6. Count alerts
    critical_count = sum(1 for s in filtered if s.above_red)
    warning_count = sum(1 for s in filtered if s.above_yellow and not s.above_red)
    watch_count = sum(1 for s in filtered if s.near_yellow)
    
    print(f"✅ {summary}")
    print(f"{'='*60}\n")
    
    return HydroStationsResult(
        stations=filtered,
        summary=summary,
        critical_count=critical_count,
        warning_count=warning_count,
        watch_count=watch_count,
        filters_applied=filters.model_dump(exclude_none=True)
    )
