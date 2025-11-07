"""Pydantic AI based MeteoAgent with OMIRL hydro stations tool."""

from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext

from .tools.hydro_stations import (
	HydroFilters,
	HydroStationsResult,
	fetch_hydro_stations,
)

# Load environment variables
load_dotenv()

# Map GEMINI_API_KEY to GOOGLE_API_KEY for Pydantic AI
if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

__all__ = ["MeteoAgent", "meteo_agent"]

SYSTEM_PROMPT = (
	"Sei l'assistente meteo della Protezione Civile Liguria. "
	"Quando la domanda riguarda fiumi, livelli idrometrici, bacini a rischio o esondazioni, "
	"usa lo strumento `get_hydro_levels` per recuperare i dati aggiornati OMIRL. "
	"\n\nParametri disponibili:"
	"\n- zona_allerta: zona di allerta (A, B, C, D, E)"
	"\n- provincia: codice o nome provincia (IM/Imperia, SV/Savona, GE/Genova, SP/La Spezia)"
	"\n- comune: nome del comune"
	"\n- bacino: nome del bacino idrografico"
	"\n- corso_acqua: nome del corso d'acqua"
	"\n\nEstrai i parametri dalla domanda e chiama lo strumento. "
	"Le query generiche (senza filtri) mostrano solo stazioni a rischio."
)


class MeteoAgent:
	"""High-level entry point for meteo-related queries."""

	def __init__(self, model: str = "google-gla:gemini-2.0-flash-lite") -> None:
		self.agent = Agent(
			model,
			system_prompt=SYSTEM_PROMPT,
			retries=2,
		)
		
		# Register the hydro levels tool
		@self.agent.tool
		async def get_hydro_levels(
			ctx: RunContext[None],
			zona_allerta: str | None = None,
			provincia: str | None = None,
			comune: str | None = None,
			bacino: str | None = None,
			corso_acqua: str | None = None,
		) -> HydroStationsResult:
			"""
			Recupera i livelli idrometrici dalle stazioni OMIRL con classificazione delle allerte.
			
			Args:
				zona_allerta: Zona di allerta (A, B, C, D, E)
				provincia: Codice o nome provincia (IM, SV, GE, SP o nomi completi)
				comune: Nome del comune
				bacino: Nome del bacino idrografico
				corso_acqua: Nome del corso d'acqua
			"""
			print(f"\n🤖 AGENT CALLING TOOL: get_hydro_levels")
			print(f"   Parameters extracted from query:")
			params = {
				"zona_allerta": zona_allerta,
				"provincia": provincia,
				"comune": comune,
				"bacino": bacino,
				"corso_acqua": corso_acqua,
			}
			for k, v in params.items():
				if v:
					print(f"      {k}: {v}")
			
			filters = HydroFilters(
				zona_allerta=zona_allerta,
				provincia=provincia,
				comune=comune,
				bacino=bacino,
				corso_acqua=corso_acqua,
			)
			return await fetch_hydro_stations(filters)

	async def run(self, query: str) -> Any:
		"""Process a natural-language query and return structured hydrometric data."""
		
		print(f"\n{'='*60}")
		print(f"🚀 METEO AGENT - Starting query processing")
		print(f"{'='*60}")
		print(f"Query: {query}")
		print(f"Model: {self.agent.model}")
		
		run_result = await self.agent.run(query)
		
		print(f"\n{'='*60}")
		print(f"✅ METEO AGENT - Query completed")
		print(f"{'='*60}")
		print(f"Result type: {type(run_result.output)}")
		print(f"All messages: {len(run_result.all_messages())} total")
		
		return run_result.output

	async def hydro_levels(self, **filters: Any) -> HydroStationsResult:
		"""Direct access to the hydro levels tool with structured filters."""

		filter_model = HydroFilters(**filters)
		return await fetch_hydro_stations(filter_model)


# Global singleton instance
meteo_agent = MeteoAgent()
