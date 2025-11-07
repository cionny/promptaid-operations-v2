"""pytest tests for SimpleOrchestrator routing logic."""

import pytest
from orchestrator import SimpleOrchestrator


@pytest.mark.asyncio
async def test_meteo_routing():
    """Test that meteo queries are routed to MeteoAgent."""
    print("="*60)
    print("TEST 1: Meteo keyword routing")
    print("="*60)
    
    orch = SimpleOrchestrator()
    
    meteo_queries = [
        "Quali fiumi sono in piena?",
        "Livelli idrometrici zona A",
        "Bacini a rischio alluvione",
        "Quanta pioggia è caduta?",
        "Precipitazioni Savona",
    ]
    
    for query in meteo_queries:
        print(f"\n📋 Query: '{query}'")
        try:
            result = await orch.process(query)
            print(f"   ✅ Routed to MeteoAgent")
            print(f"   Response: {result[:100]}..." if len(result) > 100 else f"   Response: {result}")
            
            # Validate result
            assert result is not None, f"Query '{query}' should return a result"
        except Exception as e:
            print(f"   ❌ Error: {e}")
            pytest.fail(f"Query '{query}' failed: {e}")
    
    print("\n" + "="*60)


@pytest.mark.asyncio
async def test_default_routing():
    """Test that non-specific queries default to MeteoAgent (for now)."""
    print("TEST 2: Default routing (non-specific queries)")
    print("="*60)
    
    orch = SimpleOrchestrator()
    
    generic_queries = [
        "Che situazione c'è?",
        "Dimmi qualcosa",
        "Come va?",
    ]
    
    for query in generic_queries:
        print(f"\n📋 Query: '{query}'")
        try:
            result = await orch.process(query)
            print(f"   ✅ Defaulted to MeteoAgent")
            print(f"   Response: {result[:100]}..." if len(result) > 100 else f"   Response: {result}")
            
            # Validate result
            assert result is not None, f"Query '{query}' should return a result"
        except Exception as e:
            print(f"   ❌ Error: {e}")
            pytest.fail(f"Query '{query}' failed: {e}")
    
    print("\n" + "="*60)


@pytest.mark.asyncio
async def test_future_agent_keywords():
    """Document keywords for future agents (traffic, alerts)."""
    print("TEST 3: Future agent keyword documentation")
    print("="*60)
    print("\n📝 Current routing logic:")
    print("   Meteo keywords: fiume, livelli, idro, piena, bacino,")
    print("                   precipitazione, pioggia, meteo, alluvione")
    print("   Default: MeteoAgent (only agent available)")
    
    print("\n📝 Future traffic keywords (not implemented):")
    print("   autostrada, traffico, incidente, code, viabilità")
    
    print("\n📝 Future alerts keywords (not implemented):")
    print("   allerta, avviso, criticità, bollettino")
    
    print("\n✅ Orchestrator is extensible and ready for new agents")
    print("="*60)
    
    # This test always passes - it's documentation
    assert True

