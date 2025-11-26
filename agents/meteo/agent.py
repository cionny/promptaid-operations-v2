"""Pydantic AI based MeteoAgent that extracts paramters from a query and executes tools to query data and insights from OMIRL."""

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

__all__ = ["MeteoAgent", "meteo_agent"]

SYSTEM_PROMPT = (
	"Sei l'assistente meteo della sala operativa regionale di protezione civile della Liguria. "
	"Hai a disposizione dei tool che ti permettono di estrarre dati dal sito OMIRL delle stazioni di monitoraggio idrometriche e pluviometriche. "
	"In base alle richieste degli utenti, devi capire che tool eseguire e con quali parametri.\n\n"
	"Puoi usare le parole chiave e sinonimi o variazioni per identificare quale strumento eseguire e quali parametri estrarre dalla richiesta dell'utente.\n\n"
	"Hai accesso a due strumenti principali:\n\n"
	"1. LIVELLI IDROMETRICI (get_hydro_levels): Per rispondere a domande su livelli idrometrici di fiumi e corsi d'acqua delle località e stazioni monitorate.\n"
	"2. PRECIPITAZIONI (get_rain_data): Per rispondere a domande sui massimi di precipitazione nelle varie province e zone d'allerta.\n\n"
	"IMPORTANTE: Se la domanda è generica (es. 'situazione fiumi?', 'dove piove forte?'), "
	"esegui lo strumento SENZA parametri per estrarre solo le criticità usando le soglie."
	"\n\n--- LIVELLI IDROMETRICI ---"
	"\nParole chiave:"
	"\n- livelli, idrometrici, fiume, corso d'acqua, soglie, esondazione, metri, m, centimetri, cm"
	"\nParametri disponibili (tutti opzionali):"
	"\n- localita: nome della località o stazione, oppure codice della stazione"
	"\n- zona_allerta: zona di allerta (A, B, C, D, E)"
	"\n- provincia: codice o nome provincia (IM/Imperia, SV/Savona, GE/Genova, SP/La Spezia)"
	"\n- comune: nome del comune"
	"\n- bacino: nome del bacino idrografico"
	"\n- corso_acqua: nome SPECIFICO del corso d'acqua (es. 'Roia', 'Arroscia') - NON parole generiche come 'fiume'"
	"\n\n--- PRECIPITAZIONI ---"
	"\nParole chiave:"
	"\n- pioggia, precipitazioni, accumulo, temporali, nubifragi, alluvione, adesso, minuti, 15', 30, 1h, 3h"
	"\nParametri disponibili (tutti opzionali):"
	"\n- zona_allerta: zona di allerta (A, B, C, D, E)"
	"\n- provincia: nome completo provincia (Genova, Savona, Imperia, La Spezia) - NON codici a 2 lettere"
	"\n- time_period: periodo temporale (15', 30', 1h, 3h, 6h, 12h, 24h, 7d, 15d, 30d) - default 1h"
	"\n\nREGOLE DI ESTRAZIONE:"
	"\n- NON estrarre parole generiche come 'fiume', 'pioggia', 'meteo' come parametri"
	"\n- Estrai SOLO parole che possono essere mappate direttamente ai parametri disponibili"
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
			localita: str | None = None,
			zona_allerta: str | None = None,
			provincia: str | None = None,
			comune: str | None = None,
			bacino: str | None = None,
			corso_acqua: str | None = None,
		) -> HydroStationsResult:
			"""
			Recupera i livelli idrometrici dalle stazioni OMIRL con classificazione delle criticità in base alle soglie.
			Puoi recuperare le singole stazioni o filtrare per zona di allerta, provincia, comune, bacino o corso d'acqua.
			Puoi recuperare anche solo le stazioni in criticità lasciando tutti i parametri vuoti.
			
			Args:
				localita: Nome della località o stazione, oppure codice della stazione
				zona_allerta: Zona di allerta (A, B, C, D, E)
				provincia: Codice o nome provincia (IM, SV, GE, SP o nomi completi, se nomi completi devi convertire in codice per estrarre i dati)
				comune: Nome del comune
				bacino: Nome del bacino idrografico
				corso_acqua: Nome del corso d'acqua
			"""
			print(f"\n🤖 AGENT CALLING TOOL: get_hydro_levels")
			print(f"   Parameters extracted from query:")
			params = {
				"localita": localita,
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
				localita=localita,
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
				time_period: Periodo temporale (15', 30', 1h, 3h, 6h, 12h, 24h)
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