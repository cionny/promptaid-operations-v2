"""
Interactive test for MeteoAgent - v2 Native Implementation

This script demonstrates the complete v2 flow:
1. User query in natural language
2. Pydantic AI Agent extracts parameters via LLM
3. Tool scrapes OMIRL directly (no v1 dependencies)
4. Pydantic models built from DOM (RawHydroStation → EnrichedHydroStation)
5. Template-based summaries (no LLM overhead)
6. Structured HydroStationsResult returned

Run with: 
  cd /home/jeanbaptistebove/projects/operations-v2
  python tests/meteo/test_meteo_agent.py
  python tests/meteo/test_meteo_agent.py --interactive
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.meteo.agent import meteo_agent
from agents.meteo.tools.hydro_stations import HydroFilters, fetch_hydro_stations


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
    
    if result.stations:
        print(f"\n🏞️  Sample stations:")
        for station in result.stations[:3]:
            print(f"   - {station.localita} ({station.station_code})")
            print(f"     Livello: {station.current_level}m | Alert: {station.alert_level}")
            if station.soglia_gialla:
                print(f"     Soglia gialla: {station.soglia_gialla}m | {station.percentuale_soglia}%")


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
    
    if result.stations:
        print(f"\n⚠️  At-risk stations:")
        for station in result.stations[:5]:
            print(f"   - {station.localita} ({station.provincia})")
            print(f"     {station.alert_level.upper()}: {station.current_level}m")
            if station.soglia_gialla:
                print(f"     Soglia gialla: {station.soglia_gialla}m ({station.percentuale_soglia}%)")
    else:
        print(f"\n✅ No at-risk stations - all green!")


async def interactive_mode():
    """Interactive mode - ask questions."""
    print("\n" + "="*80)
    print("🤖 INTERACTIVE MODE - MeteoAgent v2")
    print("="*80)
    print("Ask questions about river levels in Liguria (or 'quit' to exit)")
    print("\nExamples:")
    print("  - Quali fiumi sono in piena?")
    print("  - Quali fiumi sono in piena a Savona?")
    print("  - Livelli idrometrici zona A")
    print("  - Bacino del Bisagno a rischio?")
    print("  - Stazione GEFER")
    
    while True:
        query = input("\n➤ Query: ").strip()
        
        if query.lower() in ["quit", "exit", "q"]:
            print("👋 Ciao!")
            break
            
        if not query:
            continue
        
        try:
            result = await meteo_agent.run(query)
            
            print(f"\n📊 Agent Response:")
            print(result)
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Run all tests."""
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        await interactive_mode()
    else:
        # Run automated tests
        await test_direct_tool()
        await test_generic_query()
        await test_agent_query("Quali fiumi sono in piena in zona A?")
        
        print("\n" + "="*80)
        print("✅ All tests completed!")
        print("="*80)
        print("\n💡 Tips:")
        print("  • Run with --interactive for interactive mode")
        print("  • All data scraped directly from OMIRL (no v1 dependencies)")
        print("  • Pydantic models built directly from DOM")
        print("  • Template summaries (no LLM overhead)")
        print(f"\nCommand: python {Path(__file__).name} --interactive")


if __name__ == "__main__":
    asyncio.run(main())
