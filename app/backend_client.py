"""
Backend Client - Interface between Streamlit UI and Orchestrator

Handles async communication with the orchestrator and formats responses
for the Streamlit UI with metadata, artifacts, and streaming support.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import AsyncIterator, Dict, Any, Optional
import pandas as pd

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator.simple_orchestrator import SimpleOrchestrator
from agents.meteo.tools.hydro_stations import HydroStationsResult
from agents.meteo.tools.rain_stations import RainStationsResult

try:
    from pydantic_ai.result import RunResult
    from pydantic_ai.run import AgentRunResult
except ImportError:
    RunResult = None
    AgentRunResult = None


class BackendClient:
    """Client for communicating with the orchestrator backend"""
    
    def __init__(self):
        self.orchestrator = SimpleOrchestrator()
    
    async def process_query_stream(
        self,
        query: str,
        enabled_agents: list[str],
        llm_tool_calling: bool = False,
        llm_summaries: bool = False
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Process query and yield results as they become available.
        
        Yields chunks in this order:
        1. Metadata (agent, tool, parameters)
        2. Response text (streamed if LLM summaries enabled)
        3. Artifacts (tables, links, etc.)
        
        Args:
            query: User's natural language query
            enabled_agents: List of enabled agent names
            llm_tool_calling: Whether to use LLM for tool calling (future)
            llm_summaries: Whether to use LLM for summaries (future)
        """
        start_time = datetime.now()
        
        try:
            # Call orchestrator (this runs the agent + tool)
            result = await self.orchestrator.process(query)
            
            # Extract metadata from result
            metadata = self._extract_metadata(result, start_time)
            yield {
                "type": "metadata",
                "data": metadata
            }
            
            # Generate response text (template or LLM-based)
            if llm_summaries:
                # Future: Stream LLM-generated summary
                response_text = self._generate_llm_summary(result)
            else:
                # Use template from tool result
                response_text = self._generate_template_summary(result)
            
            # Yield response text (simulate streaming)
            yield {
                "type": "response_start",
                "data": {}
            }
            
            # Simulate character-by-character streaming
            for char in response_text:
                yield {
                    "type": "response_chunk",
                    "data": {"text": char}
                }
                await asyncio.sleep(0.01)  # Smooth streaming effect
            
            yield {
                "type": "response_end",
                "data": {}
            }
            
            # Generate artifacts (tables, links, etc.) - use tool_result from metadata
            tool_result = metadata.get("tool_result")
            artifacts = self._extract_artifacts(tool_result if tool_result else result)
            if artifacts:
                yield {
                    "type": "artifacts",
                    "data": artifacts
                }
        
        except Exception as e:
            yield {
                "type": "error",
                "data": {
                    "message": f"Errore durante l'elaborazione: {str(e)}",
                    "timestamp": datetime.now().isoformat()
                }
            }
    
    def _extract_metadata(self, result: Any, start_time: datetime) -> Dict[str, Any]:
        """Extract execution metadata from agent result"""
        
        agent = "MeteoAgent"
        tool = "Unknown"
        extracted_params = {}
        tool_result = None
        
        # Check if result is a Pydantic AI result object
        if AgentRunResult is not None and isinstance(result, AgentRunResult):
            # Extract tool calls from messages
            for msg in result.all_messages():
                if hasattr(msg, 'parts'):
                    for part in msg.parts:
                        if hasattr(part, 'tool_name'):
                            # Found a tool call
                            if part.tool_name == "get_hydro_levels":
                                tool = "HydroStationsTool"
                            elif part.tool_name == "get_rain_data":
                                tool = "RainStationsTool"
                            
                            # Extract parameters
                            if hasattr(part, 'args'):
                                extracted_params = {k: v for k, v in part.args.items() if v is not None}
                        
                        # Check for tool return values
                        if hasattr(part, 'content') and isinstance(part.content, (HydroStationsResult, RainStationsResult)):
                            tool_result = part.content
        elif RunResult is not None and isinstance(result, RunResult):
            # Extract tool calls from messages
            for msg in result.all_messages():
                if hasattr(msg, 'parts'):
                    for part in msg.parts:
                        if hasattr(part, 'tool_name'):
                            # Found a tool call
                            if part.tool_name == "get_hydro_levels":
                                tool = "HydroStationsTool"
                            elif part.tool_name == "get_rain_data":
                                tool = "RainStationsTool"
                            
                            # Extract parameters
                            if hasattr(part, 'args'):
                                extracted_params = {k: v for k, v in part.args.items() if v is not None}
                        
                        # Check for tool return values
                        if hasattr(part, 'content') and isinstance(part.content, (HydroStationsResult, RainStationsResult)):
                            tool_result = part.content
        
        # Fallback: check if result itself is a tool result
        elif isinstance(result, HydroStationsResult):
            tool = "HydroStationsTool"
            tool_result = result
            extracted_params = result.filters_applied or {}
        elif isinstance(result, RainStationsResult):
            tool = "RainStationsTool"
            tool_result = result
            extracted_params = result.filters_applied or {}
        
        return {
            "agent": agent,
            "tool": tool,
            "extracted_params": extracted_params,
            "timestamp": start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "cache_hit": False,  # Future: implement cache checking
            "cache_ttl": None,
            "tool_result": tool_result  # Store for artifact generation
        }
    
    def _generate_template_summary(self, result: Any) -> str:
        """Generate summary using templates from tool results"""
        
        # Check if it has an 'output' attribute (Pydantic AI result)
        if hasattr(result, 'output'):
            print(f"[DEBUG] Has output, extracting...")
            result = result.output
            print(f"[DEBUG] After extraction, type: {type(result)}, value: {str(result)[:200]}")
        
        # Also check for old-style result objects
        if hasattr(result, 'data') and result.data is not None:
            result = result.data
        
        print(f"[DEBUG4] Final result type before check: {type(result)}")
        
        if isinstance(result, HydroStationsResult):
            print(f"[DEBUG5] Returning HydroStationsResult.summary")
            return result.summary
        elif isinstance(result, RainStationsResult):
            print(f"[DEBUG6] Returning RainStationsResult.summary")
            return result.summary
        elif isinstance(result, str):
            print(f"[DEBUG7] Returning string: {result[:100]}")
            return result
        else:
            print(f"[DEBUG8] Unknown type, returning default")
            return "Risultato elaborato con successo."
    
    def _generate_llm_summary(self, result: Any) -> str:
        """Generate LLM-based summary (future implementation)"""
        # Future: Use LLM to create contextual summaries
        # For now, fall back to template
        return self._generate_template_summary(result)
    
    def _extract_artifacts(self, result: Any) -> list[Dict[str, Any]]:
        """Extract artifacts (tables, links) from result"""
        artifacts = []
        
        # For string results (LLM response), just add OMIRL link
        if isinstance(result, str):
            artifacts.append({
                "type": "link",
                "name": "Visualizza dati completi su OMIRL",
                "url": "https://omirl.regione.liguria.it"
            })
            return artifacts
        
        if isinstance(result, HydroStationsResult):
            # Add link to OMIRL source
            artifacts.append({
                "type": "link",
                "name": "Visualizza dati completi su OMIRL",
                "url": "https://omirl.regione.liguria.it/#/alertzones"
            })
            
            # Add table if there are stations
            if result.stations:
                df = pd.DataFrame([
                    {
                        "Località": s.station,
                        "Provincia": s.provincia,
                        "Comune": s.comune,
                        "Bacino": s.bacino,
                        "Corso d'Acqua": s.corso_acqua,
                        "Massimo 24h (m)": f"{s.max_24h:.2f}" if s.max_24h is not None else "N/A",
                        "Valore Attuale (m)": f"{s.current_level:.2f}" if s.current_level is not None else "N/A",
                        "Ora Riferimento": s.current_time if s.current_time else "N/A",
                        "Livello Allerta": s.alert_level
                    }
                    for s in result.stations
                ])
                
                artifacts.append({
                    "type": "table",
                    "name": f"Dettaglio {len(result.stations)} stazioni monitorate",
                    "data": df
                })
        
        elif isinstance(result, RainStationsResult):
            # Add link to OMIRL precipitation data
            artifacts.append({
                "type": "link",
                "name": "Visualizza dati precipitazioni su OMIRL",
                "url": "https://omirl.regione.liguria.it/#/maxtable"
            })
            
            # Add table if there's data
            if result.data:
                df = pd.DataFrame([
                    {
                        "Località": d.location,
                        "Accumulo (mm)": f"{d.accumulation_mm:.1f}",
                        "Periodo": d.time_period,
                        "Severità": d.severity,
                        "Descrizione": d.threshold_description
                    }
                    for d in result.data
                ])
                
                artifacts.append({
                    "type": "table",
                    "name": f"Dettaglio precipitazioni ({len(result.data)} località)",
                    "data": df
                })
        
        return artifacts


# Singleton instance
_client: Optional[BackendClient] = None

def get_backend_client() -> BackendClient:
    """Get or create the backend client singleton"""
    global _client
    if _client is None:
        _client = BackendClient()
    return _client
