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
from .tools.rain_stations import (
	RainFilters,
	RainStationsResult,
	fetch_rain_stations,
)

# Load environment variables
load_dotenv()

# Map GEMINI_API_KEY to GOOGLE_API_KEY for Pydantic AI
if "GEMINI_API_KEY" in os.environ and "GOOGLE_API_KEY" not in os.environ:
	os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]

__all__ = ["MeteoAgent", "meteo_agent"]

SYSTEM_PROMPT = (
	"Sei l'assistente meteo della Protezione Civile Liguria. "
	"Hai accesso a due strumenti principali:\n\n"
	"1. LIVELLI IDROMETRICI (get_hydro_levels): Per domande su fiumi, livelli idrometrici, bacini a rischio, esondazioni.\n"
	"2. PRECIPITAZIONI (get_rain_data): Per domande su pioggia, accumuli, precipitazioni.\n\n"
	"IMPORTANTE: Se la domanda è generica (es. 'situazione fiumi?', 'dove piove forte?'), "
	"chiama lo strumento SENZA parametri per vedere automaticamente solo le criticità."
	"\n\n--- LIVELLI IDROMETRICI ---"
	"\nParametri disponibili (tutti opzionali):"
	"\n- zona_allerta: zona di allerta (A, B, C, D, E)"
	"\n- provincia: codice o nome provincia (IM/Imperia, SV/Savona, GE/Genova, SP/La Spezia)"
	"\n- comune: nome del comune"
	"\n- bacino: nome del bacino idrografico"
	"\n- corso_acqua: nome SPECIFICO del corso d'acqua (es. 'Roia', 'Arroscia') - NON parole generiche come 'fiume'"
	"\n\n--- PRECIPITAZIONI ---"
	"\nParametri disponibili (tutti opzionali):"
	"\n- zona_allerta: zona di allerta (A, B, C, D, E)"
	"\n- provincia: nome completo provincia (Genova, Savona, Imperia, La Spezia) - NON codici a 2 lettere"
	"\n- time_period: periodo temporale (15', 30', 1h, 3h, 6h, 12h, 24h, 7d, 15d, 30d) - default 1h"
	"\n\nREGOLE DI ESTRAZIONE:"
	"\n- NON estrarre parole generiche come 'fiume', 'pioggia', 'meteo' come parametri"
	"\n- Estrai SOLO nomi specifici di luoghi (comuni, corsi d'acqua, bacini, stazioni e località)"
	"\n- Se la domanda è generica, NON passare parametri (per vedere solo criticità)"
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
		
		# Register the rain data tool
		@self.agent.tool
		async def get_rain_data(
			ctx: RunContext[None],
			zona_allerta: str | None = None,
			provincia: str | None = None,
			time_period: str = "1h",
		) -> RainStationsResult:
			"""
			Recupera i dati di precipitazione dalle stazioni OMIRL con classificazione delle allerte.
			
			Args:
				zona_allerta: Zona di allerta (A, B, C, D, E)
				provincia: Nome completo della provincia (Genova, Savona, Imperia, La Spezia)
				time_period: Periodo temporale (15', 30', 1h, 3h, 6h, 12h, 24h, 7d, 15d, 30d)
			"""
			print(f"\n🤖 AGENT CALLING TOOL: get_rain_data")
			print(f"   Parameters extracted from query:")
			params = {
				"zona_allerta": zona_allerta,
				"provincia": provincia,
				"time_period": time_period,
			}
			for k, v in params.items():
				if v:
					print(f"      {k}: {v}")
			
			filters = RainFilters(
				zona_allerta=zona_allerta,
				provincia=provincia,
				time_period=time_period,
			)
			return await fetch_rain_stations(filters)

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
		
		# Debug: Show all messages (safe attribute access)
		for i, msg in enumerate(run_result.all_messages()):
			print(f"\n--- Message {i+1} ---")
			print(f"Type: {type(msg).__name__}")
			if hasattr(msg, 'role'):
				print(f"Role: {msg.role}")
			if hasattr(msg, 'content'):
				content = msg.content
				if isinstance(content, str):
					print(f"Content: {content[:200]}")
				else:
					print(f"Content: {content}")
		
		# Return the full run_result for metadata extraction
		return run_result

	async def hydro_levels(self, **filters: Any) -> HydroStationsResult:
		"""Direct access to the hydro levels tool with structured filters."""

		filter_model = HydroFilters(**filters)
		return await fetch_hydro_stations(filter_model)
	
	async def rain_data(self, **filters: Any) -> RainStationsResult:
		"""Direct access to the rain data tool with structured filters."""

		filter_model = RainFilters(**filters)
		return await fetch_rain_stations(filter_model)


# Global singleton instance
meteo_agent = MeteoAgent()
