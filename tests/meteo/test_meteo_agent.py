"""Tests for MeteoAgent - v2 Native Implementation

This test suite demonstrates the complete v2 flow:
1. User query in natural language
2. Pydantic AI Agent extracts parameters via LLM
3. Tool scrapes OMIRL directly (no v1 dependencies)
4. Pydantic models built from DOM (RawHydroStation -> EnrichedHydroStation)
5. Template-based summaries (no LLM overhead)
6. Structured HydroStationsResult returned

Run with: 
  python tests/meteo/test_meteo_agent.py
"""

import sys
from pathlib import Path
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from agents.meteo.agent import meteo_agent
from agents.meteo.models import HydroFilters
from agents.meteo.tools.hydro_stations import fetch_hydro_stations


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
    assert result.filters_applied.provincia == "Savona", "Filter should be applied"
    
    if result.stations:
        print(f"\n🏞️  Sample stations:")
        for station in result.stations[:3]:
            # Extract clean name from localita ("Tiglieto [TIGLT]" -> "Tiglieto")
            clean_name = station.localita.split('[')[0].strip() if '[' in station.localita else station.localita
            print(f"   - {clean_name} ({station.provincia})")
            print(f"     Livello: {station.last_level}m | Criticita: {station.criticita}")
            print(f"     Riferimento: {station.reference_time}")
            if station.soglia_gialla:
                percent = (station.last_level / station.soglia_gialla * 100) if station.soglia_gialla > 0 else 0
                print(f"     Soglia gialla: {station.soglia_gialla}m ({percent:.1f}%)")
            
            # Validate station data structure
            assert station.localita, "Station should have locality"
            assert station.criticita in ["nessuna", "moderata", "elevata"], "Valid criticita level"


async def test_agent_query():
    """Test the full agent with natural language query."""
    print("\n" + "="*80)
    print(f"TEST 2: Agent with natural language query")
    print("="*80)
    
    query = "Quali fiumi sono in piena in zona A?"
    print(f"Query: '{query}'")
    
    result = await meteo_agent.run(query)
    
    print(f"\n📋 Agent Response:")
    print(f"   Type: {type(result)}")
    print(result)
    
    # Validate agent response
    assert result is not None, "Agent should return a response"


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
            clean_name = station.localita.split('[')[0].strip() if '[' in station.localita else station.localita
            print(f"   - {clean_name} ({station.provincia})")
            print(f"     {station.criticita.upper()}: {station.last_level}m")
            if station.soglia_gialla:
                percent = (station.last_level / station.soglia_gialla * 100) if station.soglia_gialla > 0 else 0
                print(f"     Soglia gialla: {station.soglia_gialla}m ({percent:.1f}%)")
            
            # Validate at-risk stations should not be "nessuna" (unless only near_yellow)
            assert station.criticita != "nessuna" or station.near_yellow or result.critical_count == 0, \
                "Generic query should prioritize at-risk stations"
    else:
        print(f"\n✅ No at-risk stations - all green!")


async def run_all_tests():
    """Run all tests in a single event loop."""
    print("\n" + "#" * 80)
    print("# METEO AGENT TESTS - v2 Native Implementation")
    print("#" * 80)
    
    await test_direct_tool()
    await test_agent_query()
    await test_generic_query()
    
    print("\n" + "#" * 80)
    print("# ALL TESTS COMPLETED")
    print("#" * 80)


if __name__ == "__main__":
    asyncio.run(run_all_tests())

