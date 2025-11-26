"""
Phase 1 Tests - Single Agent (MeteoAgent with Hydro Stations Tool)

Tests the hydro stations tool and MeteoAgent integration with real OMIRL data.
Following the testing strategy from docs/tests.md.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.meteo.models import HydroFilters
from agents.meteo.tools.hydro_stations import fetch_hydro_stations


async def test_hydro_tool_zona_a():
    """Test hydro stations tool with zona filter (Phase 1)."""
    filters = HydroFilters(zona_allerta="A")
    result = await fetch_hydro_stations(filters)
    
    # Should return stations in zona A
    assert isinstance(result.stations, list)
    
    print(f"\n📊 Zona A stations at risk: {len(result.stations)}")
    print(f"Summary: {result.summary}")
    
    # All returned stations should be in zona A
    for station in result.stations:
        assert station.zona_allerta == "A"


async def test_hydro_tool_provincia_savona():
    """Test hydro stations tool with provincia filter (Phase 1)."""
    filters = HydroFilters(provincia="Savona")
    result = await fetch_hydro_stations(filters)
    
    assert isinstance(result.stations, list)
    
    print(f"\n📊 Savona stations: {len(result.stations)}")
    print(f"Summary: {result.summary}")
    
    # All returned stations should be in provincia SV
    for station in result.stations:
        assert station.provincia == "SV"


async def test_hydro_tool_specific_station():
    """Test hydro stations tool with specific localita (Phase 1)."""
    filters = HydroFilters(localita="Tiglieto")
    result = await fetch_hydro_stations(filters)
    
    assert len(result.stations) <= 1
    
    if result.stations:
        station = result.stations[0]
        assert "tiglieto" in station.localita.lower()
        assert station.criticita in ["nessuna", "moderata", "elevata"]
        
        print(f"\n📊 Station Tiglieto:")
        print(f"  Località: {station.localita}")
        print(f"  Livello attuale: {station.last_level}m")
        print(f"  Criticità: {station.criticita}")


async def test_hydro_tool_bacino_bisagno():
    """Test hydro stations tool with bacino filter (Phase 1)."""
    filters = HydroFilters(bacino="Bisagno")
    result = await fetch_hydro_stations(filters)
    
    print(f"\n📊 Bacino Bisagno stations: {len(result.stations)}")
    print(f"Summary: {result.summary}")
    
    # All returned stations should be in Bisagno basin
    for station in result.stations:
        assert station.bacino and "bisagno" in station.bacino.lower()


async def test_hydro_tool_generic_query():
    """Test hydro stations tool with no filters (Phase 1)."""
    filters = HydroFilters()
    result = await fetch_hydro_stations(filters)
    
    # Generic query should only return at-risk stations
    print(f"\n📊 Regional monitoring:")
    print(f"  Critical (elevata): {result.critical_count}")
    print(f"  Warning (moderata): {result.warning_count}")
    print(f"  Watch (near yellow): {result.watch_count}")
    print(f"\nSummary: {result.summary}")
    
    # All returned stations should be at-risk
    for station in result.stations:
        assert station.criticita != "nessuna" or station.near_yellow


if __name__ == "__main__":
    # Run tests directly for quick debugging
    import asyncio
    
    print("=" * 60)
    print("Phase 1 Tests - MeteoAgent Hydro Stations Tool")
    print("=" * 60)
    
    async def run_all():
        await test_hydro_tool_generic_query()
        await test_hydro_tool_zona_a()
        await test_hydro_tool_provincia_savona()
        await test_hydro_tool_specific_station()
        await test_hydro_tool_bacino_bisagno()
    
    asyncio.run(run_all())
