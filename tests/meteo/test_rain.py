"""
Test suite for RainStationsTool - v2 Native Implementation

This test suite demonstrates the complete v2 flow for precipitation data:
1. User query in natural language
2. Pydantic AI Agent extracts parameters via LLM
3. Tool scrapes OMIRL precipitation tables (zones and provinces)
4. Pydantic models built from DOM (RawRainData -> EnrichedRainData)
5. Template-based summaries (no LLM overhead)
6. Structured RainStationsResult returned

Run with:
  python tests/meteo/test_rain.py
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

import asyncio
from agents.meteo.models import RainFilters
from agents.meteo.tools.rain_stations import fetch_rain_stations


async def test_direct_tool():
    """Test 1: Direct tool call with specific filters."""
    print("\n" + "="*80)
    print("TEST 1: Direct tool call - Genova 3h accumulation")
    print("="*80)
    
    filters = RainFilters(provincia="Genova", time_period="3h")
    result = await fetch_rain_stations(filters)
    
    print(f"\n📋 Results:")
    print(f"   Entries found: {len(result.data)}")
    print(f"   Critical: {result.critical_count}")
    print(f"   Warning: {result.warning_count}")
    print(f"   Max: {result.max_accumulation_mm}mm in {result.max_location}")
    print(f"   Max station: {result.max_station} at {result.max_time}")
    print(f"   Period: {result.time_period}")
    print(f"   Summary: {result.summary}")
    
    # Assertions
    assert result is not None, "Result should not be None"
    assert isinstance(result.data, list), "Data should be a list"
    assert result.filters_applied["provincia"] == "Genova", "Filter should be applied"
    assert result.time_period == "3h", "Time period should be 3h"
    
    if result.data:
        print(f"\n🌧️  Sample data:")
        for entry in result.data[:3]:
            print(f"   - {entry.location} ({entry.location_type})")
            print(f"     Accumulo: {entry.max_mm}mm | Criticità: {entry.criticita}")
            print(f"     Stazione: {entry.max_station} alle {entry.max_time}")
            if entry.soglia_gialla_min:
                print(f"     Soglie: gialla {entry.soglia_gialla_min}-{entry.soglia_gialla_max}mm | rossa {entry.soglia_rossa_min}mm")
            
            # Validate data structure
            assert entry.location, "Entry should have location"
            assert entry.criticita in ["nessuna", "moderata", "elevata"], "Valid criticita level"
            assert entry.time_period == "3h", "Time period should match"


async def test_generic_query():
    """Test 2: Generic query (no location filters) - should show only at-risk."""
    print("\n" + "="*80)
    print("TEST 2: Generic query (regional precipitation monitoring)")
    print("="*80)
    
    filters = RainFilters(time_period="1h")  # No location filters
    result = await fetch_rain_stations(filters)
    
    print(f"\n📋 Regional Monitoring (1h):")
    print(f"   At-risk locations: {len(result.data)}")
    print(f"   Critical: {result.critical_count}")
    print(f"   Warning: {result.warning_count}")
    print(f"   Max: {result.max_accumulation_mm}mm in {result.max_location}")
    print(f"   Summary: {result.summary}")
    
    # Assertions
    assert result is not None, "Result should not be None"
    assert isinstance(result.data, list), "Data should be a list"
    assert result.time_period == "1h", "Time period should be 1h"
    
    # Generic query should only show at-risk (moderata or elevata)
    if result.data:
        for entry in result.data:
            assert entry.criticita in ["moderata", "elevata"], "Generic query should filter to at-risk only"
        
        print(f"\n🌧️  At-risk locations:")
        for entry in result.data[:5]:
            print(f"   - {entry.location}: {entry.max_mm}mm ({entry.criticita})")


async def test_time_periods():
    """Test 3: Different time periods with same location."""
    print("\n" + "="*80)
    print("TEST 3: Time period comparison - Zona A")
    print("="*80)
    
    periods = ["1h", "3h", "12h", "24h"]
    
    for period in periods:
        filters = RainFilters(zona_allerta="A", time_period=period)
        result = await fetch_rain_stations(filters)
        
        print(f"\n{period:4s}: {result.max_accumulation_mm:5.1f}mm - {result.summary}")
        
        assert result is not None, f"Result should not be None for {period}"
        assert result.time_period == period, f"Period should be {period}"


async def test_province_vs_zone():
    """Test 4: Compare province and zone aggregations."""
    print("\n" + "="*80)
    print("TEST 4: Province vs Zone aggregation")
    print("="*80)
    
    # Province filter
    prov_filters = RainFilters(provincia="Imperia", time_period="1h")
    prov_result = await fetch_rain_stations(prov_filters)
    
    print(f"\n📍 Provincia Imperia:")
    print(f"   Accumulation: {prov_result.max_accumulation_mm}mm")
    print(f"   Criticità: {prov_result.data[0].criticita if prov_result.data else 'N/A'}")
    
    # Zone filter (A = Ponente, includes Imperia)
    zone_filters = RainFilters(zona_allerta="A", time_period="1h")
    zone_result = await fetch_rain_stations(zone_filters)
    
    print(f"\n🗺️  Zona Allerta A:")
    print(f"   Accumulation: {zone_result.max_accumulation_mm}mm")
    print(f"   Criticità: {zone_result.data[0].criticita if zone_result.data else 'N/A'}")
    
    # Both should have data
    assert prov_result.data, "Province data should exist"
    assert zone_result.data, "Zone data should exist"


async def main():
    """Run all tests sequentially."""
    await test_direct_tool()
    await test_generic_query()
    await test_time_periods()
    await test_province_vs_zone()
    
    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED SUCCESSFULLY")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
