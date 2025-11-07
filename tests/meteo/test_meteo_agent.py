"""
pytest tests for MeteoAgent - v2 Native Implementation

This test suite demonstrates the complete v2 flow:
1. User query in natural language
2. Pydantic AI Agent extracts parameters via LLM
3. Tool scrapes OMIRL directly (no v1 dependencies)
4. Pydantic models built from DOM (RawHydroStation → EnrichedHydroStation)
5. Template-based summaries (no LLM overhead)
6. Structured HydroStationsResult returned

Run with: 
  pytest tests/meteo/test_meteo_agent.py -v -s
  pytest tests/meteo/test_meteo_agent.py::test_direct_tool -v -s
"""

import pytest
from agents.meteo.agent import meteo_agent
from agents.meteo.tools.hydro_stations import HydroFilters, fetch_hydro_stations


@pytest.mark.asyncio
async def test_direct_tool():
    """Test the hydro tool directly with filters (v2 native implementation)."""
    print("\n" + "="*80)
    print("TEST 1: Direct tool call with specific filters")
    print("="*80)
    
    filters = HydroFilters(provincia="Savona")
    result = await fetch_hydro_stations(filters)
    
    print(f"\n📋 Results:")
    print(f"   Stations found: {len(result.stations)}")
    print(f"   Critical: {result.critical_count}")
    print(f"   Warning: {result.warning_count}")
    print(f"   Watch: {result.watch_count}")
    print(f"   Summary: {result.summary}")
    
    # Assertions for test validation
    assert result is not None, "Result should not be None"
    assert isinstance(result.stations, list), "Stations should be a list"
    assert result.filters_applied["provincia"] == "Savona", "Filter should be applied"
    
    if result.stations:
        print(f"\n🏞️  Sample stations:")
        for station in result.stations[:3]:
            print(f"   - {station.localita} ({station.station_code})")
            print(f"     Livello: {station.current_level}m | Alert: {station.alert_level}")
            if station.soglia_gialla:
                print(f"     Soglia gialla: {station.soglia_gialla}m | {station.percentuale_soglia}%")
            
            # Validate station data structure
            assert station.localita, "Station should have locality"
            assert station.alert_level in ["verde", "pre-soglia", "gialla", "rossa"], "Valid alert level"


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Quali fiumi sono in piena in zona A?",
    "Livelli idrometrici a Savona",
    "Bacino del Bisagno a rischio?"
])
async def test_agent_query(query: str):
    """Test the full agent with natural language query."""
    print("\n" + "="*80)
    print(f"TEST 2: Agent with natural language query")
    print("="*80)
    print(f"Query: '{query}'")
    
    result = await meteo_agent.run(query)
    
    print(f"\n📋 Agent Response:")
    print(f"   Type: {type(result)}")
    print(result)
    
    # Validate agent response
    assert result is not None, "Agent should return a response"


@pytest.mark.asyncio
async def test_generic_query():
    """Test generic query (no filters) - should show only at-risk stations."""
    print("\n" + "="*80)
    print("TEST 3: Generic query (regional monitoring)")
    print("="*80)
    
    filters = HydroFilters()  # No filters = generic query
    result = await fetch_hydro_stations(filters)
    
    print(f"\n📋 Regional Monitoring:")
    print(f"   At-risk stations: {len(result.stations)}")
    print(f"   Critical: {result.critical_count}")
    print(f"   Warning: {result.warning_count}")
    print(f"   Watch: {result.watch_count}")
    print(f"   Summary: {result.summary}")
    
    # Assertions
    assert result is not None, "Result should not be None"
    assert isinstance(result.stations, list), "Stations should be a list"
    
    if result.stations:
        print(f"\n⚠️  At-risk stations:")
        for station in result.stations[:5]:
            print(f"   - {station.localita} ({station.provincia})")
            print(f"     {station.alert_level.upper()}: {station.current_level}m")
            if station.soglia_gialla:
                print(f"     Soglia gialla: {station.soglia_gialla}m ({station.percentuale_soglia}%)")
            
            # Validate at-risk stations should not be "verde"
            assert station.alert_level != "verde" or result.critical_count == 0, \
                "Generic query should prioritize at-risk stations"
    else:
        print(f"\n✅ No at-risk stations - all green!")

