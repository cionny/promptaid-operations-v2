"""Hydro stations tool for PromptAid operations v2."""

from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple

import yaml
from pydantic import BaseModel, ConfigDict, Field

from services.data.cache import get_cache_service

CONFIG_ROOT = Path(__file__).resolve().parent.parent / "config"
HYDRO_CONFIG_PATH = CONFIG_ROOT / "livelli_idrometrici_thresholds.yaml"
GEOGRAPHY_CONFIG_PATH = CONFIG_ROOT / "geography.yaml"
DEFAULT_CACHE_TTL = 600
AT_RISK_LEVELS: Tuple[str, ...] = ("pre-soglia", "gialla", "rossa")
ALERT_DESCRIPTIONS: Dict[str, str] = {
	"rossa": "Criticità elevata",
	"gialla": "Criticità moderata",
	"pre-soglia": "Criticità ordinaria",
	"verde": "Criticità assente",
}

__all__ = [
	"HydroFilters",
	"HydroStation",
	"HydroStationsResult",
	"fetch_hydro_stations",
]


def _load_yaml(path: Path) -> Dict[str, Any]:
	with open(path, "r", encoding="utf-8") as handle:
		return yaml.safe_load(handle)


@dataclass(frozen=True)
class ThresholdCatalog:
	"""Collection of station thresholds and alert thresholds configuration."""

	thresholds: Dict[str, Dict[str, Optional[float]]]
	near_ratio: float

	@staticmethod
	def from_payload(payload: Dict[str, Any]) -> "ThresholdCatalog":
		analysis_cfg = payload.get("analysis_config", {})
		return ThresholdCatalog(
			thresholds=payload.get("thresholds", {}),
			near_ratio=float(analysis_cfg.get("near_threshold_percentage", 0.85)),
		)

	def get(self, station_code: str) -> Dict[str, Optional[float]]:
		return self.thresholds.get(station_code, {})


@dataclass(frozen=True)
class GeographyKnowledge:
	"""Geographic knowledge for the Liguria region."""

	name_to_code: Dict[str, str]
	code_to_name: Dict[str, str]
	zona_descriptions: Dict[str, str]

	@staticmethod
	def from_payload(payload: Dict[str, Any]) -> "GeographyKnowledge":
		resting = payload.get("regions", {}).get("liguria", {})
		mapping = resting.get("provinces", {}).get("name_to_code_mapping", {})
		name_to_code = {name.lower(): code.upper() for name, code in mapping.items()}
		code_to_name = {code.upper(): name for name, code in mapping.items()}
		zona_descriptions = {
			zona.upper(): desc for zona, desc in resting.get("alert_zones", {}).get("zone_descriptions", {}).items()
		}
		return GeographyKnowledge(name_to_code=name_to_code, code_to_name=code_to_name, zona_descriptions=zona_descriptions)

	def normalize_province(self, value: Optional[str]) -> Optional[str]:
		if not value:
			return None
		trimmed = value.strip()
		if not trimmed:
			return None
		upper = trimmed.upper()
		if upper in self.code_to_name:
			return upper
		return self.name_to_code.get(trimmed.lower())

	def province_name(self, code: Optional[str]) -> Optional[str]:
		if not code:
			return None
		return self.code_to_name.get(code.upper())

	def zone_description(self, zone: Optional[str]) -> Optional[str]:
		if not zone:
			return None
		return self.zona_descriptions.get(zone.upper())


@lru_cache(maxsize=1)
def get_threshold_catalog() -> ThresholdCatalog:
	return ThresholdCatalog.from_payload(_load_yaml(HYDRO_CONFIG_PATH))


@lru_cache(maxsize=1)
def get_geography() -> GeographyKnowledge:
	return GeographyKnowledge.from_payload(_load_yaml(GEOGRAPHY_CONFIG_PATH))


class HydroFilters(BaseModel):
	"""Filters accepted by the hydro stations tool."""

	model_config = ConfigDict(extra="forbid", populate_by_name=True, str_strip_whitespace=True)

	zona_allerta: Optional[Literal["A", "B", "C", "C+", "C-", "D", "E", "M"]] = Field(
		default=None, description="Zona di allerta (A, B, C, C±, D, E, M)"
	)
	provincia: Optional[str] = Field(default=None, description="Codice o nome provincia (IM, SV, GE, SP, MS)")
	comune: Optional[str] = Field(default=None, description="Filtro per comune (match parziale)")
	bacino: Optional[str] = Field(default=None, description="Filtro per bacino (match parziale)")
	corso_acqua: Optional[str] = Field(default=None, description="Filtro per corso d'acqua (match parziale)")
	station_code: Optional[str] = Field(default=None, description="Codice stazione OMIRL")


class HydroStation(BaseModel):
	"""Structured information for a single hydrometric station."""

	model_config = ConfigDict(extra="allow")

	station_code: str
	zona_allerta: Optional[str] = None
	zona_descrizione: Optional[str] = None
	localita: str
	provincia: Optional[str] = None
	provincia_nome: Optional[str] = None
	comune: Optional[str] = None
	bacino: Optional[str] = None
	corso_acqua: Optional[str] = None
	livello_attuale_m: Optional[float] = None
	ora_riferimento: Optional[str] = None
	massimo_24h_m: Optional[float] = None
	ora_massimo: Optional[str] = None
	soglia_gialla_m: Optional[float] = None
	soglia_rossa_m: Optional[float] = None
	percentuale_soglia: Optional[float] = None
	alert_level: Literal["verde", "pre-soglia", "gialla", "rossa"] = "verde"
	criticita: str = ALERT_DESCRIPTIONS["verde"]


class HydroStationsResult(BaseModel):
	"""Result payload returned by the hydro tool and the MeteoAgent."""

	model_config = ConfigDict(extra="allow")

	query_type: Literal["generic", "specific"]
	stations: List[HydroStation]
	summary_text: str = ""
	critical_count: int = 0
	warning_count: int = 0
	watch_count: int = 0
	at_risk_count: int = 0
	filters: Dict[str, Any] = Field(default_factory=dict)
	updated_at: Optional[datetime] = None


@dataclass
class HydroDataRepository:
	"""Loads hydrometric data with caching."""

	thresholds: ThresholdCatalog
	cache_ttl: int = DEFAULT_CACHE_TTL

	def __post_init__(self) -> None:
		self._cache = get_cache_service()

	def load(self) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
		entry = self._cache.get_cached(
			tool="omirl",
			task="livelli_idrometrici",
			data_fn=self._fetch_remote_data,
			ttl=self.cache_ttl,
		)
		return entry.get("data", []), entry.get("metadata", {})

	@staticmethod
	def _fetch_remote_data() -> List[Dict[str, Any]]:
		"""Fetch live OMIRL data via the web services adapter."""
		from services.web.adapters import get_omirl_adapter
		
		adapter = get_omirl_adapter()
		return adapter.fetch_livelli_idrometrici()


def _classify_alert(current_level: Optional[float], thresholds: Dict[str, Optional[float]], near_ratio: float) -> str:
	if current_level is None:
		return "verde"
	red = thresholds.get("red")
	yellow = thresholds.get("yellow")
	if isinstance(red, (int, float)) and current_level >= red:
		return "rossa"
	if isinstance(yellow, (int, float)):
		if current_level >= yellow:
			return "gialla"
		if current_level >= yellow * near_ratio:
			return "pre-soglia"
	return "verde"


def _clean_localita(value: Optional[str], station_code: str) -> str:
	if not value:
		return ""
	cleaned = value.strip()
	if station_code and f"[{station_code}]" in cleaned:
		return cleaned.replace(f"[{station_code}]", "").strip()
	return cleaned


def _build_station(
	raw: Dict[str, Any],
	thresholds: ThresholdCatalog,
	geography: GeographyKnowledge,
) -> HydroStation:
	station_code = (raw.get("station_code") or "").strip().upper()
	threshold_values = thresholds.get(station_code)
	current_level = raw.get("current_level")
	alert_level = _classify_alert(current_level, threshold_values, thresholds.near_ratio)
	yellow_raw = threshold_values.get("yellow")
	yellow = yellow_raw if isinstance(yellow_raw, (int, float)) else None
	percentuale = None
	if yellow is not None and yellow > 0 and isinstance(current_level, (int, float)):
		percentuale = round((current_level / yellow) * 100, 1)
	province_code = geography.normalize_province(raw.get("provincia"))
	zona = (raw.get("zona_allerta") or "").strip().upper() or None
	red_raw = threshold_values.get("red")
	red = red_raw if isinstance(red_raw, (int, float)) else None
	return HydroStation(
		station_code=station_code,
		zona_allerta=zona,
		zona_descrizione=geography.zone_description(zona),
		localita=_clean_localita(raw.get("località") or raw.get("localita"), station_code),
		provincia=province_code,
		provincia_nome=geography.province_name(province_code),
		comune=raw.get("comune"),
		bacino=raw.get("bacino"),
		corso_acqua=raw.get("corso_acqua"),
		livello_attuale_m=current_level,
		ora_riferimento=raw.get("time_current") or raw.get("current_time"),
		massimo_24h_m=raw.get("max_24h"),
		ora_massimo=raw.get("time_max_24h") or raw.get("max_24h_time"),
		soglia_gialla_m=yellow,
		soglia_rossa_m=red,
		percentuale_soglia=percentuale,
		alert_level=alert_level,
		criticita=ALERT_DESCRIPTIONS.get(alert_level, ALERT_DESCRIPTIONS["verde"]),
	)


def _normalize_filters(filters: HydroFilters, geography: GeographyKnowledge) -> Dict[str, Any]:
	zone = filters.zona_allerta.strip().upper() if filters.zona_allerta else None
	province_code = geography.normalize_province(filters.provincia)
	comune = filters.comune.strip().lower() if filters.comune else None
	bacino = filters.bacino.strip().lower() if filters.bacino else None
	corso = filters.corso_acqua.strip().lower() if filters.corso_acqua else None
	station_code = filters.station_code.strip().upper() if filters.station_code else None
	is_generic = not any([zone, province_code, comune, bacino, corso, station_code])
	result_filters: Dict[str, Any] = {}
	if zone:
		result_filters["zona_allerta"] = zone
		result_filters["zona_descrizione"] = geography.zone_description(zone)
	if province_code:
		result_filters["provincia"] = province_code
		result_filters["provincia_nome"] = geography.province_name(province_code)
	if filters.comune:
		result_filters["comune"] = filters.comune.strip()
	if filters.bacino:
		result_filters["bacino"] = filters.bacino.strip()
	if filters.corso_acqua:
		result_filters["corso_acqua"] = filters.corso_acqua.strip()
	if station_code:
		result_filters["station_code"] = station_code
	return {
		"zona_allerta": zone,
		"provincia": province_code,
		"comune": comune,
		"bacino": bacino,
		"corso_acqua": corso,
		"station_code": station_code,
		"is_generic": is_generic,
		"result_filters": result_filters,
	}


def _apply_filters(stations: List[HydroStation], normalized_filters: Dict[str, Any]) -> List[HydroStation]:
	def matches(station: HydroStation) -> bool:
		f = normalized_filters
		if f["station_code"] and station.station_code != f["station_code"]:
			return False
		if f["zona_allerta"] and station.zona_allerta != f["zona_allerta"]:
			return False
		if f["provincia"] and station.provincia != f["provincia"]:
			return False
		if f["comune"] and (not station.comune or f["comune"] not in station.comune.lower()):
			return False
		if f["bacino"] and (not station.bacino or f["bacino"] not in station.bacino.lower()):
			return False
		if f["corso_acqua"] and (not station.corso_acqua or f["corso_acqua"] not in station.corso_acqua.lower()):
			return False
		return True

	return [station for station in stations if matches(station)]


def _describe_filters(result_filters: Dict[str, Any]) -> str:
	if not result_filters:
		return "generale"
	parts: List[str] = []
	if "zona_allerta" in result_filters:
		desc = result_filters.get("zona_descrizione")
		parts.append(
			f"zona {result_filters['zona_allerta']}"
			+ (f" – {desc}" if desc else "")
		)
	if "provincia" in result_filters:
		name = result_filters.get("provincia_nome")
		parts.append(
			f"provincia {result_filters['provincia']}"
			+ (f" ({name})" if name else "")
		)
	for key in ("comune", "bacino", "corso_acqua", "station_code"):
		if key in result_filters:
			label = key.replace("_", " ")
			parts.append(f"{label} {result_filters[key]}")
	return ", ".join(parts)


def _build_summary(
	stations: List[HydroStation],
	counts: Counter,
	normalized_filters: Dict[str, Any],
	query_type: Literal["generic", "specific"],
) -> str:
	if not stations:
		if query_type == "generic":
			return "Nessuna stazione OMIRL presenta criticità idrometriche al momento."
		return "Nessuna stazione soddisfa i filtri richiesti."
	segments: List[str] = []
	if counts.get("rossa"):
		segments.append(f"{counts['rossa']} in criticità elevata (rossa)")
	if counts.get("gialla"):
		segments.append(f"{counts['gialla']} in criticità moderata (gialla)")
	if counts.get("pre-soglia"):
		segments.append(f"{counts['pre-soglia']} in pre-soglia")
	if not segments:
		if query_type == "generic":
			return "Monitoraggio regionale: nessuna criticità idrometrica rilevata."
		filters_text = _describe_filters(normalized_filters["result_filters"])
		return f"Filtri {filters_text}: nessuna criticità idrometrica rilevata."
	body = "; ".join(segments)
	if query_type == "generic":
		return f"Monitoraggio regionale: {body}."
	filters_text = _describe_filters(normalized_filters["result_filters"])
	return f"Filtri {filters_text}: {body}."


def _parse_metadata_datetime(metadata: Dict[str, Any]) -> Optional[datetime]:
	value = metadata.get("datetime") or metadata.get("timestamp")
	if isinstance(value, str):
		try:
			return datetime.fromisoformat(value)
		except ValueError:
			return None
	if isinstance(value, (int, float)):
		try:
			return datetime.fromtimestamp(value)
		except (ValueError, OSError):
			return None
	return None


async def fetch_hydro_stations(filters: HydroFilters) -> HydroStationsResult:
	"""Fetch hydrometric data and map it into Pydantic models."""

	print(f"\n{'='*60}")
	print(f"🔍 HYDRO STATIONS TOOL - Processing request")
	print(f"{'='*60}")
	print(f"Filters: {filters.model_dump(exclude_none=True)}")
	
	thresholds = get_threshold_catalog()
	geography = get_geography()
	repository = HydroDataRepository(thresholds=thresholds)
	
	print(f"\n📦 Loading data (cache TTL: {repository.cache_ttl}s)...")
	raw_stations, metadata = await asyncio.to_thread(repository.load)
	print(f"✅ Loaded {len(raw_stations)} stations")
	print(f"   Cache metadata: {metadata.get('cache_hit', False) and 'HIT' or 'MISS'}")
	if metadata.get("datetime"):
		print(f"   Data timestamp: {metadata['datetime']}")
	
	print(f"\n🔧 Enriching stations with thresholds & geography...")
	enriched = [_build_station(raw, thresholds, geography) for raw in raw_stations]
	
	print(f"\n🎯 Applying filters...")
	normalized_filters = _normalize_filters(filters, geography)
	filtered = _apply_filters(enriched, normalized_filters)
	query_type: Literal["generic", "specific"] = "generic" if normalized_filters["is_generic"] else "specific"
	print(f"   Query type: {query_type}")
	print(f"   Matched {len(filtered)} stations before alert filtering")
	
	if query_type == "generic":
		filtered = [station for station in filtered if station.alert_level in AT_RISK_LEVELS]
		print(f"   After filtering for at-risk stations: {len(filtered)}")
	
	counts: Counter = Counter(station.alert_level for station in filtered)
	print(f"\n📊 Alert counts:")
	print(f"   🔴 Rossa (critical): {counts.get('rossa', 0)}")
	print(f"   🟡 Gialla (warning): {counts.get('gialla', 0)}")
	print(f"   🟠 Pre-soglia (watch): {counts.get('pre-soglia', 0)}")
	print(f"   🟢 Verde (normal): {counts.get('verde', 0)}")
	
	summary_text = _build_summary(filtered, counts, normalized_filters, query_type)
	updated_at = _parse_metadata_datetime(metadata)
	at_risk_total = sum(counts.get(level, 0) for level in AT_RISK_LEVELS)
	
	result = HydroStationsResult(
		query_type=query_type,
		stations=filtered,
		summary_text=summary_text,
		critical_count=counts.get("rossa", 0) + counts.get("gialla", 0),
		warning_count=counts.get("gialla", 0),
		watch_count=counts.get("pre-soglia", 0),
		at_risk_count=at_risk_total,
		filters=normalized_filters["result_filters"],
		updated_at=updated_at,
	)
	
	print(f"\n✅ Result summary: {summary_text}")
	print(f"{'='*60}\n")
	
	return result


# Pydantic AI tool function - returns the fetch function for agent registration
def hydro_stations_tool():
	"""Tool function for Pydantic AI agent."""
	return fetch_hydro_stations
