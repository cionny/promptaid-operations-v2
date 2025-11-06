"""
Phase 1 Tests - Single Agent (MeteoAgent with Hydro Stations Tool)

Tests the hydro stations tool and MeteoAgent integration with real OMIRL data.
Following the testing strategy from docs/tests.md.
"""

import pytest
from agents.meteo.agent import meteo_agent
from agents.meteo.tools.hydro_stations import HydroFilters, fetch_hydro_stations


@pytest.mark.asyncio
async def test_hydro_tool_zona_a():
    """Test hydro stations tool with zona filter (Phase 1)."""
    filters = HydroFilters(zona_allerta="A")
    result = await fetch_hydro_stations(filters)
    
    # Should return stations in zona A with alert status
    assert result.query_type == "generic"
    assert isinstance(result.stations, list)
    
    # Generic query should only return at-risk stations
    # In normal conditions, this may be 0
    print(f"\n📊 Zona A stations at risk: {result.at_risk_count}")
    print(f"Summary: {result.summary_text}")
    
    # All returned stations should be in zona A
    for station in result.stations:
        assert station.zona_allerta == "A"


@pytest.mark.asyncio
async def test_hydro_tool_provincia_savona():
    """Test hydro stations tool with provincia filter (Phase 1)."""
    filters = HydroFilters(provincia="Savona")
    result = await fetch_hydro_stations(filters)
    
    assert result.query_type == "specific"
    assert isinstance(result.filters, dict)
    assert result.filters.get("provincia") == "SV"
    assert result.filters.get("provincia_nome") == "Savona"
    
    print(f"\n📊 Savona stations: {len(result.stations)}")
    print(f"Summary: {result.summary_text}")
    
    # All returned stations should be in provincia SV
    for station in result.stations:
        assert station.provincia == "SV"


@pytest.mark.asyncio
async def test_hydro_tool_specific_station():
    """Test hydro stations tool with specific station code (Phase 1)."""
    filters = HydroFilters(station_code="GEFER")
    result = await fetch_hydro_stations(filters)
    
    assert result.query_type == "specific"
    assert len(result.stations) <= 1
    
    if result.stations:
        station = result.stations[0]
        assert station.station_code == "GEFER"
        assert station.localita
        assert station.alert_level in ["verde", "pre-soglia", "gialla", "rossa"]
        
        print(f"\n📊 Station GEFER:")
        print(f"  Località: {station.localita}")
        print(f"  Livello: {station.livello_attuale_m}m")
        print(f"  Alert: {station.alert_level} - {station.criticita}")


@pytest.mark.asyncio
async def test_hydro_tool_bacino_bisagno():
    """Test hydro stations tool with bacino filter (Phase 1)."""
    filters = HydroFilters(bacino="Bisagno")
    result = await fetch_hydro_stations(filters)
    
    assert result.query_type == "specific"
    
    print(f"\n📊 Bacino Bisagno stations: {len(result.stations)}")
    print(f"Summary: {result.summary_text}")
    
    # All returned stations should be in Bisagno basin
    for station in result.stations:
        assert station.bacino and "bisagno" in station.bacino.lower()


@pytest.mark.asyncio
async def test_meteo_agent_hydro_query():
    """Test MeteoAgent with natural language query (Phase 1)."""
    # This will use the agent's LLM to extract parameters
    result = await meteo_agent.run("Quali fiumi sono in piena in zona A?")
    
    print(f"\n🤖 Agent response:")
    print(result.data)
    
    # The agent should have called the hydro_stations_tool
    assert result.data is not None


@pytest.mark.asyncio
async def test_hydro_tool_generic_query():
    """Test hydro stations tool with no filters (Phase 1)."""
    filters = HydroFilters()
    result = await fetch_hydro_stations(filters)
    
    assert result.query_type == "generic"
    
    # Generic query should only return at-risk stations
    print(f"\n📊 Regional monitoring:")
    print(f"  Critical (rossa): {result.critical_count}")
    print(f"  Warning (gialla): {result.warning_count}")
    print(f"  Watch (pre-soglia): {result.watch_count}")
    print(f"  Total at risk: {result.at_risk_count}")
    print(f"\nSummary: {result.summary_text}")
    
    # All returned stations should be at-risk
    for station in result.stations:
        assert station.alert_level in ["pre-soglia", "gialla", "rossa"]


if __name__ == "__main__":
    # Run tests directly for quick debugging
    import asyncio
    
    print("=" * 60)
    print("Phase 1 Tests - MeteoAgent Hydro Stations Tool")
    print("=" * 60)
    
    asyncio.run(test_hydro_tool_generic_query())
    asyncio.run(test_hydro_tool_zona_a())
    asyncio.run(test_hydro_tool_provincia_savona())
    asyncio.run(test_hydro_tool_specific_station())
    asyncio.run(test_hydro_tool_bacino_bisagno())
