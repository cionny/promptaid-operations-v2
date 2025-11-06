"""
Interactive test for MeteoAgent with full visibility into query processing.

This script demonstrates the complete flow:
1. User query in natural language
2. Agent extracts parameters via LLM
3. Tool fetches/caches OMIRL data
4. Results filtered and classified
5. Structured response returned

Run with: PYTHONPATH=. python scripts/test_meteo_agent.py
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.meteo.agent import meteo_agent
from agents.meteo.tools.hydro_stations import HydroFilters, fetch_hydro_stations


async def test_direct_tool():
    """Test the hydro tool directly with filters."""
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
    
    if result.stations:
        print(f"\n🏞️  Sample stations:")
        for station in result.stations[:3]:
            print(f"   - {station.localita} ({station.station_code})")
            print(f"     Livello: {station.livello_attuale_m}m | Alert: {station.alert_level}")


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
    
    filters = HydroFilters()
    result = await fetch_hydro_stations(filters)
    
    print(f"\n📋 Regional Monitoring:")
    print(f"   Total at-risk: {result.at_risk_count}")
    print(f"   Summary: {result.summary_text}")
    
    if result.stations:
        print(f"\n⚠️  At-risk stations:")
        for station in result.stations:
            print(f"   - {station.localita} ({station.provincia})")
            print(f"     {station.alert_level.upper()}: {station.livello_attuale_m}m")
            if station.soglia_gialla_m:
                print(f"     Soglia gialla: {station.soglia_gialla_m}m ({station.percentuale_soglia}%)")


async def interactive_mode():
    """Interactive mode - ask questions."""
    print("\n" + "="*80)
    print("🤖 INTERACTIVE MODE")
    print("="*80)
    print("Ask questions about river levels in Liguria (or 'quit' to exit)")
    print("\nExamples:")
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
            
            print(f"\n📊 Result:")
            if hasattr(result, 'summary_text'):
                print(f"   {result.summary_text}")
            else:
                print(result)
                
            if hasattr(result, 'stations') and result.stations:
                print(f"\n   Stations: {len(result.stations)}")
                for station in result.stations[:5]:
                    print(f"   • {station.localita}: {station.livello_attuale_m}m ({station.alert_level})")
                if len(result.stations) > 5:
                    print(f"   ... and {len(result.stations) - 5} more")
                    
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
        print("\nRun with --interactive for interactive mode:")
        print("  PYTHONPATH=. python scripts/test_meteo_agent.py --interactive")


if __name__ == "__main__":
    asyncio.run(main())
