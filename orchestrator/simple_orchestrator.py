"""
Simple Orchestrator for PromptAid Operations v2

Keyword-based routing to agents - no LLM needed for routing.
Designed to be simple now, extensible for multi-agent queries later.
"""

from typing import Any, Dict
from agents.meteo.agent import MeteoAgent


class SimpleOrchestrator:
    """Route queries to agents using simple keyword matching."""
    
    def __init__(self):
        self.agents = {
            "meteo": MeteoAgent(),
            # Future agents:
            # "traffic": TrafficAgent(),
            # "alerts": AlertAgent(),
        }
    
    async def process(self, query: str) -> Any:
        """
        Route query to appropriate agent.
        
        Args:
            query: Natural language query
            
        Returns:
            Agent response (format depends on agent)
        """
        query_lower = query.lower()
        
        # Meteo keywords
        if any(kw in query_lower for kw in [
            "fiume", "livelli", "idro", "piena", "bacino",
            "precipitazione", "pioggia", "meteo", "alluvione"
        ]):
            return await self.agents["meteo"].run(query)
        
        # Default to meteo for now (only agent available)
        return await self.agents["meteo"].run(query)
    
    # Future: Multi-agent parallel execution
    # async def process_multi(self, query: str) -> Dict[str, Any]:
    #     """Execute multiple agents in parallel and merge results."""
    #     if "autostrada" in query_lower and "pioggia" in query_lower:
    #         traffic_task = self.agents["traffic"].run(query)
    #         meteo_task = self.agents["meteo"].run(query)
    #         results = await asyncio.gather(traffic_task, meteo_task)
    #         return self._merge_results(results)
