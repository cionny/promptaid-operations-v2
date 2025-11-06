# Agent Specifications

---

## ⚠️ Important Note for GitHub Copilot

**The code examples in this README are illustrative possibilities, not prescriptive requirements.**

When implementing features:
1. **Analyze the problem first** - understand the actual requirement
2. **Evaluate the suggested approach** - is it the right solution?
3. **Propose improvements** - if you see a better way, use it
4. **Stay pragmatic** - prefer simple, maintainable code over clever abstractions
5. **Challenge assumptions** - the examples might not cover your specific case

**Examples of when to deviate:**
- If a simpler data structure works better than the proposed Pydantic model
- If a different execution pattern is more efficient
- If error handling needs a different approach
- If the suggested abstraction adds unnecessary complexity

**Always prioritize:**
- Code clarity and maintainability
- Performance and efficiency
- Testability
- Real-world usage patterns

The documentation provides direction, not a strict specification. Use your judgment.

---

## MeteoAgent

**Purpose**: Handle all meteorological data queries from OMIRL (hydro levels, precipitation, sensors, radar/satellite, maps).

**Architecture**: Pydantic AI agent with tool calling capabilities. One tool per type of data queried (hydro, precipitation, other sensors).

### Tools

Each tool corresponds to an OMIRL data section and reuses v1 scraping/caching services:

#### 1. HydroStationsTool
**Source**: [Livelli Idrometrici](https://omirl.regione.liguria.it/#/alertzones) (Tabelle section)

**What it does**:
- Scrapes 5 tables (zones A-E) with river levels
- Compares against thresholds (normal/yellow/red)
- Filters by provincia, comune, bacino, corso_acqua or by a specific station
- Responds to both generic queries ("che fiumi potrebbero esondare in Liguria") and specific ones ("dammi livello stazione Airole")

**Thresholds**: Loaded from `agents/meteo/config/livelli_idrometrici_thesholds.yaml`

**Filters**:
```python
class HydroFilters(BaseModel):
    provincia: Optional[Literal["GE", "SV", "IM", "SP"]] # uses province codes
    comune: Optional[str]
    zona_allerta: Optional[Literal["A", "B", "C", "D", "E"]]
    bacino: Optional[str]
    corso_acqua: Optional[str]
```

**Result**:
```python
class HydroStation(BaseModel):
    località: str
    provincia: str
    comune: str
    bacino: str
    corso_acqua: str
    massimo_24h_m: float
    ora_massimo: str # date and time
    valore_ora_riferimento_m: float
    ora_riferimento: str # date and time
    alert_level: Literal["verde", "gialla", "rossa"] # see config yaml
    
class HydroStationsResult(BaseModel):
    stations: List[HydroStation]
    critical_count: int  # red level
    warning_count: int   # yellow level
    timestamp: datetime
```

**Example queries**:
- "Quali fiumi sono in piena a Savona?"
- "Ci sono bacini a rischio nella zona A?"
- "Livelli del Bisagno sopra soglia?"

---

#### 2. RainStationsTool
**Source**: [Massimi di Precipitazione](https://omirl.regione.liguria.it/#/maxtable) (Tabelle section)

**What it does**:
- Scrapes 2 tables (by zone and by province)
- Provides rain accumulation by time unit (15', 30', 1h, 3h, 6h, 12h, 24h)
- Applies threshold-based severity classification (green/yellow/red)
- Filters by zona_allerta or provincia

**Thresholds**: Loaded from `agents/meteo/config/precipitazioni.yaml`

**Filters**:
```python
class RainFilters(BaseModel):
    aggregation: Literal["zona", "provincia"]  # which table
    zona_allerta: Optional[Literal["A", "B", "C", "D", "E"]]
    provincia: Optional[Literal["Genova", "Savona", "Imperia", "La Spezia"]] # uses full province names
    time_period: Literal["15'", "30'", "1h", "3h", "6h", "12h", "24h"] = "1h"
```

**Result**:
```python
class RainData(BaseModel):
    location: str  # zona or provincia
    accumulation_mm: float
    time_period: str
    severity: Literal["verde", "giallo", "rosso"]
    threshold_description: str  # e.g., "soglia gialla"
    timestamp: datetime

class RainStationsResult(BaseModel):
    data: List[RainData]
    max_accumulation_mm: float
    max_location: str
    critical_count: int  # red severity
    warning_count: int   # yellow severity
    timestamp: datetime
```
**Example queries**:
- "Quanto ha piovuto a Genova nell'ultima ora?"
- "Pioggia critica in zona A nelle ultime 3 ore"
- "Dove sta piovendo forte adesso?"

---

#### 3. SensorStationsTool
**Source**: [Valori Stazioni](https://omirl.regione.liguria.it/#/summarytable) (Tabelle section)

**What it does**:
- Scrapes table for specific sensor type (13 sensors: temperatura, vento, umidità, etc.)
- Filters by comune, provincia, bacino
- Returns current + min/max values

**Filters**:
```python
class SensorFilters(BaseModel):
    sensor_type: Literal[
        "Temperatura", "Livelli Idrometrici", "Vento", 
        "Umidità dell'aria", "Eliofanie", "Radiazione solare", "Bagnatura Fogliare", "Pressione Atmosferica", 
        "Tensione Batteria", "Stato del Mare", "Neve"
    ]
    comune: Optional[str]
    provincia: Optional[Literal["GE", "SV", "IM", "SP"]] # uses province code
    bacino: Optional[str]
    area: Optional[str]
```

**Result**:
```python
class SensorStation(BaseModel):
    nome: str
    codice: str
    comune: str
    provincia: str
    ultimo: float
    max: float
    min: float
    unita_misura: str

class SensorStationsResult(BaseModel):
    stations: List[SensorStation]
    sensor_type: str
    timestamp: datetime
```

**Example queries**:
- "Temperatura attuale a Imperia"
- "Velocità vento nei bacini di Savona"
- "Dove soffiano venti forti adesso?"

---

### Agent Implementation

```python
# agents/meteo/agent.py
from pydantic_ai import Agent
from .tools import HydroStationsTool, RainStationsTool, SensorStationsTool

class MeteoAgent:
    """
    Pydantic AI agent for meteorological data queries.
    
    Automatically routes to appropriate tool based on query context.
    LLM extracts parameters (provincia, comune, time_period, etc.)
    """
    
    def __init__(self):
        self.agent = Agent(
            model='gpt-oss:20b', # use local models by default with fallback to models/gemini-2.5-flash-lite
            system_prompt="""
            You are a meteorological data assistant for Liguria civil protection.
            
            Available tools:
            - HydroStationsTool: river levels, flood risk
            - RainStationsTool: precipitation accumulation with severity thresholds
            - SensorStationsTool: temperature, wind, humidity, etc.
            
            Extract location (provincia/comune/zona) and time parameters from user query.
            Always specify units in results (meters, mm, km/h, etc.).
            Flag critical situations (red/yellow alerts).
            """,
            tools=[
                HydroStationsTool(),
                RainStationsTool(),
                SensorStationsTool()
            ]
        )
    
    async def run(self, query: str) -> MeteoResponse:
        """
        Process query and return structured result.
        
        Examples:
        - "Fiumi in piena a Savona" → HydroStationsTool(provincia="SV")
        - "Pioggia a Genova ultime 6h" → RainStationsTool(comune="Genova", time_period="6h")
        - "Vento forte adesso" → SensorStationsTool(sensor_type="Vento")
        """
        result = await self.agent.run(query)
        return self._format_response(result)
```

**Key design choices**:
- **Pydantic AI handles tool selection** (no manual routing)
- **LLM extracts structured parameters** from natural language
- **Tools reuse v1 scrapers and caching, adapting if needed** (`services/scraper/omirl_adapter.py`)
- **Template summaries** (no LLM for text generation)
- **Caching** via `services/cache/` (10 min TTL)
- **Threshold-based severity** for hydro levels and rain tools (YAML config)

---

## RAGAgent

**Purpose**: Retrieve civil protection procedures, plans, and historical event data from vector DB.

**Status**: 🚧 To be designed in Phase 2

**Planned tools**:
- `ProcedureRetrievalTool`: Emergency procedures from CP plans
- `HistoricalEventsTool`: Past flood/weather events
- `HotspotRetrievalTool`: Critical monitoring locations

---

## TrafficAgent

**Purpose**: Monitor road conditions, closures, and traffic incidents.

**Status**: 🚧 To be designed in Phase 6

**Planned tools**:
- `RoadClosuresTool`: Current blocked roads
- `TrafficIncidentsTool`: Active incidents
- `HighwayStatusTool`: Autostrade conditions