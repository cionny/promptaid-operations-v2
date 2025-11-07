# MeteoAgent Development Plan

## 🎯 Goal
Build a truly independent v2 MeteoAgent that eliminates ALL v1 dependencies and implements the promised simplifications.

**Status:** ✅ Phases 1-5 Complete | ✅ Phase 7 Complete | ❌ Phase 6 Rolled Back | 📝 Phase 8 Reconsidered

**Current State:**
- ✅ Native OMIRL scraping (no v1 dependencies)
- ✅ Direct Pydantic pipeline (Raw → Enriched → Result)
- ✅ Template-based summaries
- ✅ Simple orchestrator with keyword routing
- ✅ Two working tools: HydroStationsTool, RainStationsTool
- ✅ Unified configuration (meteo_config.yaml)
- ✅ Standalone tools (Phase 6 base class rollback - premature abstraction)
- � Test simplification deferred (ensure it adds value first)

---

## 📋 Phase 1: Native OMIRL Scraping (No v1 Dependency) ✅ COMPLETE

### 1.1 Rewrite `fetch_livelli_idrometrici()` in `services/web/adapters/omirl_adapter.py`

**Current (v1 dependency):**
```python
def fetch_livelli_idrometrici(self) -> List[Dict[str, Any]]:
    from tools.omirl.tables.livelli_idro import LivelliIdrometriciTask  # ❌ v1
    task = LivelliIdrometriciTask()
    return task.scrape_all_zones()
```

**Target (native v2):**
```python
async def fetch_livelli_idrometrici(self) -> List[RawHydroStation]:
    """Scrape OMIRL directly, return Pydantic models immediately."""
    # 1. Navigate to https://omirl.regione.liguria.it/idrotable.php
    # 2. Extract table rows using Playwright + table scraper
    # 3. Build RawHydroStation(località, provincia, bacino, current_level, max_24h, ...) 
    #    directly from DOM - NO intermediate dicts
    # 4. Return List[RawHydroStation]
```

**Implementation:**
- Reuse `services/web/browser/browser_manager.py` (already exists)
- Reuse `services/web/scrapers/table_scraper.py` (already exists)
- Create `RawHydroStation` Pydantic model in `agents/meteo/models.py`
- Map table columns → Pydantic fields in one step

**Files to modify:**
- `services/web/adapters/omirl_adapter.py` - native scraping
- `agents/meteo/models.py` - new file with `RawHydroStation`, `EnrichedHydroStation`, `HydroStationsResult`

**Implementation Notes:**
- ✅ `services/web/adapters/omirl_adapter.py` - native scraping for hydro and rain
- ✅ Builds `RawHydroStation` and `RawRainData` directly from DOM
- ✅ No intermediate dicts
- ✅ Uses Playwright + generic browser/table scrapers

---

## 📋 Phase 2: Direct Pydantic Model Pipeline ✅ COMPLETE

### 2.1 Eliminate Dict → Model Mapping

**Current flow (wasteful):**
```
Scraper → Dict → _map_station() → HydroStation → _to_result() → HydroStationsResult
```

**Target flow (direct):**
```
Scraper → RawHydroStation → _enrich() → EnrichedHydroStation → HydroStationsResult
```

### 2.2 New Model Architecture

**File: `agents/meteo/models.py`**
```python
class RawHydroStation(BaseModel):
    """Direct mapping from OMIRL table DOM."""
    localita: str  # From column 0
    provincia: str  # From column 1
    comune: str  # From column 2
    bacino: str  # From column 3
    corso_acqua: str  # From column 4
    current_level: Optional[float]  # From column 5 (parse "2.34 m")
    current_time: Optional[str]  # From column 6
    max_24h: Optional[float]  # From column 7
    max_24h_time: Optional[str]  # From column 8

class EnrichedHydroStation(RawHydroStation):
    """Adds threshold analysis from livelli_idrometrici_thresholds.yaml."""
    alert_level: Literal["verde", "pre-soglia", "gialla", "rossa"]
    soglia_gialla: Optional[float]
    soglia_rossa: Optional[float]
    percentuale_soglia: Optional[float]

class HydroStationsResult(BaseModel):
    """Final tool output."""
    stations: List[EnrichedHydroStation]
    summary: str  # Template-based, NOT from v1
    critical_count: int
    warning_count: int
    filters_applied: Dict[str, Any]
```

**Benefits:**
- No dict → model conversion overhead
- Type-safe from scraping onward
- Single enrichment step (RawHydroStation → EnrichedHydroStation)

**Implementation Notes:**
- ✅ `agents/meteo/models.py` contains all models
- ✅ RawHydroStation, EnrichedHydroStation, HydroStationsResult
- ✅ RawRainData, EnrichedRainData, RainStationsResult
- ✅ Direct inheritance pattern (Enriched extends Raw)

---

## 📋 Phase 3: Template-Based Summaries (No LLM) ✅ COMPLETE

### 3.1 Replace v1's `formatted_output`

**File: `agents/meteo/tools/hydro_stations.py`**

```python
def _build_summary(stations: List[EnrichedHydroStation], filters: Dict) -> str:
    """Pure template logic - NO v1, NO LLM."""
    critical = [s for s in stations if s.alert_level == "rossa"]
    warning = [s for s in stations if s.alert_level == "gialla"]
    watch = [s for s in stations if s.alert_level == "pre-soglia"]
    
    if critical:
        return f"🚨 {len(critical)} stazioni in CRITICITÀ ROSSA: {', '.join(s.localita for s in critical[:3])}"
    elif warning:
        return f"⚠️ {len(warning)} stazioni in CRITICITÀ GIALLA: {', '.join(s.localita for s in warning[:3])}"
    elif watch:
        return f"👀 {len(watch)} stazioni da monitorare (pre-soglia)"
    else:
        return f"✅ Nessuna criticità ({len(stations)} stazioni monitorate)"
```

**Delete:**
- All references to `raw.get("formatted_output")`
- v1's `format_livelli_idro_simple()` calls

**Implementation Notes:**
- ✅ `_build_summary()` in both `hydro_stations.py` and `rain_stations.py`
- ✅ Fast, deterministic, emoji-based output
- ✅ No LLM overhead

---

## 📋 Phase 4: Simple Orchestrator (Multi-Agent Ready) ✅ COMPLETE

### 4.1 Create `orchestrator/simple_orchestrator.py`

**File: `orchestrator/simple_orchestrator.py`**
```python
class SimpleOrchestrator:
    """Route queries to agents - keyword-based (no LLM routing)."""
    
    def __init__(self):
        self.agents = {
            "meteo": MeteoAgent(),
            # "traffic": TrafficAgent(),  # Future
            # "alerts": AlertAgent(),      # Future
        }
    
    async def process(self, query: str) -> Dict[str, Any]:
        """Route query to appropriate agent(s)."""
        query_lower = query.lower()
        
        # Simple keyword matching (no LLM)
        if any(kw in query_lower for kw in ["fiume", "livelli", "idro", "piena"]):
            return await self.agents["meteo"].run(query)
        
        # Default: meteo agent
        return await self.agents["meteo"].run(query)
```

**Later expansion (ready for RAG agent):**
```python
# Multi-agent queries
if "documenti" in query_lower and "alluvione" in query_lower:
    # Parallel execution - MeteoAgent + RAGAgent
    meteo_task = self.agents["meteo"].run(query)
    rag_task = self.agents["rag"].run(query)
    results = await asyncio.gather(meteo_task, rag_task)
    return self._merge_results(results)
```

**Implementation Notes:**
- ✅ `orchestrator/simple_orchestrator.py` created
- ✅ Keyword-based routing (fast, deterministic)
- ✅ Foundation for multi-agent (MeteoAgent + future RAGAgent)

---

## 📋 Phase 5: Update MeteoAgent to Use New Pipeline ✅ COMPLETE

### 5.1 Simplify `agents/meteo/tools/hydro_stations.py`

**Delete:**
- `_get_raw_data()` - replaced by `OMIRLAdapter.fetch_livelli_idrometrici()`
- `_map_station()` - models built directly in scraper
- `_to_result()` - models built directly in enrichment

**Keep:**
- `_enrich_station()` - add thresholds to `RawHydroStation → EnrichedHydroStation`
- `_apply_filters()` - filter `List[EnrichedHydroStation]`
- `_build_summary()` - new template logic

**New flow:**
```python
async def fetch_hydro_stations(filters: HydroFilters) -> HydroStationsResult:
    # 1. Scrape → List[RawHydroStation] (native v2)
    raw_stations = await omirl_adapter.fetch_livelli_idrometrici()
    
    # 2. Enrich → List[EnrichedHydroStation]
    enriched = [_enrich_station(s) for s in raw_stations]
    
    # 3. Filter
    filtered = _apply_filters(enriched, filters)
    
    # 4. Template summary (no v1, no LLM)
    summary = _build_summary(filtered, filters)
    
    # 5. Return
    return HydroStationsResult(
        stations=filtered,
        summary=summary,
        critical_count=sum(1 for s in filtered if s.alert_level == "rossa"),
        ...
    )
```

**Implementation Notes:**
- ✅ `agents/meteo/agent.py` - Pydantic AI agent with two tools
- ✅ `get_hydro_levels` tool - extracts params from NL query
- ✅ `get_rain_data` tool - extracts params from NL query
- ✅ Direct methods: `hydro_levels()`, `rain_data()`
- ✅ Both tools follow same pattern (scrape → enrich → filter → summarize)

---

## 📋 Phase 6: Tool Framework Unification ❌ ROLLED BACK

### Attempted Abstraction
Created `BaseMeteoTool[RawT, EnrichedT, ResultT]` to eliminate duplication across tools.

### Why It Failed
**Metrics:**
- Original tools: 374 lines (hydro 174 + rain 200)
- With base class: 480 lines (hydro_v2 128 + rain_v2 171 + base 181)
- **Net increase: +106 lines (+28%)**

**Root Cause:**
Hydro and Rain have **fundamentally incompatible data models**:
- Hydro: Station-centric (1 station → 1 reading)
- Rain: Matrix structure (1 location → 8-10 time periods)

**Forced Abstractions:**
- `EnrichedRainData` polluted with `zona_allerta`/`provincia` fields just to satisfy base class
- `isinstance()` checks in `fetch()` for list vs single enrichment
- Rain tool overriding `_apply_filters()` anyway for time_period
- 5 abstract methods still requiring full implementation per tool

**Truly Shared Code:** Only ~25 lines (geography loading + province normalization)

**Lesson Learned:** 
Premature abstraction is worse than duplication when:
- Only 2 tools exist
- Data models are fundamentally different
- Shared code is <10% of total

**Resolution:**
Rolled back to standalone tools. Kept unified config (that WAS valuable).

### 6.1 Create Base Tool Framework

**File: `agents/meteo/tools/base_tool.py`**
```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Dict, Any, List, Optional
from functools import lru_cache
from pathlib import Path
import yaml

RawT = TypeVar('RawT')
EnrichedT = TypeVar('EnrichedT')
ResultT = TypeVar('ResultT')

class BaseMeteoTool(ABC, Generic[RawT, EnrichedT, ResultT]):
    """Shared framework for all MeteoAgent tools."""
    
    CONFIG_ROOT = Path(__file__).parent.parent / "config"
    
    def __init__(self):
        self._geography = self._load_geography()
        self._thresholds = self._load_thresholds()
    
    @lru_cache(maxsize=1)
    def _load_geography(self) -> Dict[str, Any]:
        """Load shared geography config."""
        with open(self.CONFIG_ROOT / "meteo_config.yaml") as f:
            return yaml.safe_load(f)['geography']
    
    @abstractmethod
    def _load_thresholds(self) -> Dict[str, Any]:
        """Load tool-specific thresholds from unified config."""
        pass
    
    @abstractmethod
    async def _scrape(self) -> List[RawT]:
        """Scrape raw data from OMIRL."""
        pass
    
    @abstractmethod
    def _enrich(self, raw: RawT) -> EnrichedT:
        """Add threshold analysis to raw data."""
        pass
    
    def _apply_filters(self, items: List[EnrichedT], **filters) -> List[EnrichedT]:
        """Shared filtering logic for provincia, zona_allerta, alert_level."""
        result = items
        
        # Zona filter
        if filters.get('zona_allerta'):
            result = [i for i in result if getattr(i, 'zona_allerta', None) == filters['zona_allerta']]
        
        # Provincia filter (handle both codes and full names)
        if filters.get('provincia'):
            prov = filters['provincia']
            # Normalize using shared geography
            prov_code = self._geography['provinces']['name_to_code'].get(prov, prov).upper()
            result = [i for i in result if self._normalize_province(getattr(i, 'provincia', '')) == prov_code]
        
        return result
    
    def _normalize_province(self, provincia: str) -> str:
        """Normalize province to 2-letter code."""
        mapping = self._geography['provinces']['name_to_code']
        return mapping.get(provincia.split('/')[0].strip(), provincia).upper()
    
    @abstractmethod
    def _build_summary(self, items: List[EnrichedT], **filters) -> str:
        """Template-based summary generation."""
        pass
    
    async def fetch(self, **filters) -> ResultT:
        """Main execution flow - same for all tools."""
        # 1. Scrape
        raw_items = await self._scrape()
        
        # 2. Enrich
        enriched = [self._enrich(item) for item in raw_items]
        
        # 3. Filter
        filtered = self._apply_filters(enriched, **filters)
        
        # 4. Apply generic query optimization
        if self._is_generic_query(**filters):
            filtered = self._filter_at_risk(filtered)
        
        # 5. Build result
        return self._build_result(filtered, **filters)
    
    def _is_generic_query(self, **filters) -> bool:
        """Detect if query has no location filters."""
        return not any([filters.get('zona_allerta'), filters.get('provincia'), filters.get('comune')])
    
    def _filter_at_risk(self, items: List[EnrichedT]) -> List[EnrichedT]:
        """Show only items with alert_level in [gialla, rossa]."""
        return [i for i in items if getattr(i, 'alert_level', 'verde') in ['gialla', 'rossa']]
    
    @abstractmethod
    def _build_result(self, items: List[EnrichedT], **filters) -> ResultT:
        """Build final result object."""
        pass
```

### 6.2 Refactor HydroStationsTool

**File: `agents/meteo/tools/hydro_stations.py`** (simplified to ~150 lines)
```python
from .base_tool import BaseMeteoTool
from agents.meteo.models import RawHydroStation, EnrichedHydroStation, HydroStationsResult
from services.web.adapters.omirl_adapter import get_omirl_adapter

class HydroStationsTool(BaseMeteoTool[RawHydroStation, EnrichedHydroStation, HydroStationsResult]):
    """Hydro stations tool - uses base framework."""
    
    def _load_thresholds(self) -> dict:
        """Load from unified config."""
        with open(self.CONFIG_ROOT / "meteo_config.yaml") as f:
            return yaml.safe_load(f)['tools']['hydro_stations']['thresholds']
    
    async def _scrape(self) -> List[RawHydroStation]:
        adapter = get_omirl_adapter()
        return await adapter.fetch_livelli_idrometrici()
    
    def _enrich(self, raw: RawHydroStation) -> EnrichedHydroStation:
        thresholds = self._thresholds.get(raw.station_code, {})
        # ... threshold logic (same as before)
        return EnrichedHydroStation(...)
    
    def _build_summary(self, stations: List[EnrichedHydroStation], **filters) -> str:
        # ... template logic (same as before)
        pass
    
    def _build_result(self, stations: List[EnrichedHydroStation], **filters) -> HydroStationsResult:
        return HydroStationsResult(
            stations=stations,
            summary=self._build_summary(stations, **filters),
            critical_count=sum(1 for s in stations if s.alert_level == 'rossa'),
            # ...
        )

# Public API
async def fetch_hydro_stations(filters: HydroFilters) -> HydroStationsResult:
    tool = HydroStationsTool()
    return await tool.fetch(**filters.model_dump(exclude_none=True))
```

**Impact:**
- 🎯 ~200 lines removed (350 → 150)
- ✅ Shared logic in base class
- ✅ Tool focuses on domain-specific enrichment only

### 6.3 Refactor RainStationsTool

Same pattern - ~200 lines removed by extending `BaseMeteoTool`.

---

## 📋 Phase 7: Configuration Consolidation � NEXT

### Problem Identified
Currently have 3 separate YAML files:
- `geography.yaml` - provinces, zones, comuni
- `livelli_idrometrici_thresholds.yaml` - hydro thresholds
- `precipitazioni.yaml` - rain thresholds

### 7.1 Create Unified Config

**File: `agents/meteo/config/meteo_config.yaml`**
```yaml
# Unified MeteoAgent Configuration
version: "2.0"

geography:
  provinces:
    name_to_code:
      Genova: GE
      Savona: SV
      Imperia: IM
      "La Spezia": SP
    
  alert_zones:
    A: Ponente
    B: Centro-Ponente
    C: Centro-Levante
    D: Levante
    E: Entroterra

tools:
  hydro_stations:
    thresholds:
      AIROL:
        yellow: 2.0
        red: 2.5
      GENOV_PONTE_CARREGA:
        yellow: 2.34
        red: 2.70
      # ... all stations
    
    analysis:
      near_threshold_percentage: 0.85
  
  precipitazioni:
    default_time_period: "1h"
    
    thresholds:
      "15'":
        green: { max: 10 }
        yellow: { min: 10, max: 16 }
        red: { min: 16 }
      "1h":
        green: { max: 25 }
        yellow: { min: 25, max: 40 }
        red: { min: 40 }
      # ... all periods
    
    time_period_labels:
      "1h": ["ultima ora", "ultimi 60 minuti"]
      "3h": ["ultime 3 ore", "ultime tre ore"]
      # ...
```

**Delete:**
- `geography.yaml`
- `livelli_idrometrici_thresholds.yaml`
- `precipitazioni.yaml`

**Benefits:**
- ✅ Single source of truth
- ✅ Easier versioning
- ✅ Clear tool boundaries
- ✅ Shared geography section

**Status:** ✅ COMPLETE - Unified config working with both tools

---

## 📋 Phase 8: Test Simplification � RECONSIDERED

### Deferred Pending Value Analysis
Before implementing parametrized test suite, need to ensure it actually:
- Reduces total lines of code (not just moves complexity)
- Improves test clarity (not obscures tool-specific behaviors)
- Doesn't force abstractions over incompatible test patterns

### Current Test Status
- Hydro: 5 tests covering direct calls, NL queries, filtering
- Rain: 5 tests covering direct calls, NL queries, time periods
- Tests are clear, domain-specific, and working

### Decision Criteria for Phase 8
Only proceed if parametrization:
- Reduces net lines by >20%
- Preserves test readability
- Doesn't require test base classes or fixtures for 2 tools

**Lesson from Phase 6:** Premature abstraction for 2 items is usually wrong.

---

## 📋 Summary: What Actually Simplified v2

### ✅ Wins (Keep These)
1. **LLM Layer Simplification**
   - v1: LLM routing → validator → tool execution
   - v2: Orchestrator keyword routing → Pydantic AI agents → tools
   - Result: Faster, clearer, fewer moving parts

2. **Direct Pydantic Pipeline**
   - No intermediate dicts
   - RawModel → EnrichedModel → ResultModel
   - Type-safe end-to-end

3. **Template Summaries**
   - No LLM calls for standard summaries
   - Faster, deterministic, free

4. **Unified Configuration** (Phase 7)
   - Single meteo_config.yaml
   - Clear tool boundaries
   - Shared geography section

### ❌ Mistakes (Learned From)
1. **BaseMeteoTool** (Phase 6 - Rolled Back)
   - Added 28% more code
   - Forced incompatible data models into same flow
   - Polluted models to satisfy base class
   - Lesson: 2 tools ≠ need for abstraction

### 📊 Final Metrics
- Total tool code: 377 lines (vs 374 original, +0.8%)
- Config: 579 lines unified (vs 3 separate files)
- Net change: Simpler architecture, marginally more lines
- Value: Configuration consolidation + architectural clarity

### 🎯 Key Principles Going Forward
1. **Challenge every abstraction** - Prove it saves >20% code
2. **Incompatible models stay separate** - Don't force unification
3. **Config consolidation ≠ code consolidation** - They're independent
4. **Measure net complexity** - Lines + clarity + maintainability
- Parameter variations
- Edge cases

This creates ~10 test functions (2 tools × 5 each) testing overlapping behavior.

### 8.1 Create Parametrized Test Suite

**File: `tests/meteo/test_tools_unified.py`**
```python
import pytest
from agents.meteo.tools.hydro_stations import fetch_hydro_stations, HydroFilters
from agents.meteo.tools.rain_stations import fetch_rain_stations, RainFilters
from agents.meteo.agent import meteo_agent

# Test data: (tool_name, fetch_func, filter_class, test_filters, nl_query)
TOOL_TEST_CASES = [
    (
        "hydro_stations",
        fetch_hydro_stations,
        HydroFilters,
        {"provincia": "Savona"},
        "Quali fiumi sono in piena a Savona?"
    ),
    (
        "rain_stations",
        fetch_rain_stations,
        RainFilters,
        {"provincia": "Genova", "time_period": "3h"},
        "Quanto ha piovuto a Genova nelle ultime 3 ore?"
    ),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,fetch_func,filter_class,filters,nl_query", TOOL_TEST_CASES)
async def test_direct_tool_call(tool_name, fetch_func, filter_class, filters, nl_query):
    """Test direct tool execution with filters."""
    filter_obj = filter_class(**filters)
    result = await fetch_func(filter_obj)
    
    assert result is not None
    assert hasattr(result, 'summary')
    assert hasattr(result, 'filters_applied')
    assert result.filters_applied == filters

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,fetch_func,filter_class,filters,nl_query", TOOL_TEST_CASES)
async def test_agent_nl_query(tool_name, fetch_func, filter_class, filters, nl_query):
    """Test agent parameter extraction from natural language."""
    result = await meteo_agent.run(nl_query)
    
    assert result is not None
    assert isinstance(result, str)  # Agent returns NL response

@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name,fetch_func,filter_class,filters,nl_query", TOOL_TEST_CASES)
async def test_generic_query_filtering(tool_name, fetch_func, filter_class, filters, nl_query):
    """Test that generic queries show only at-risk items."""
    # Generic query = no location filters
    filter_obj = filter_class()  # Empty filters
    result = await fetch_func(filter_obj)
    
    # All returned items should be at-risk (gialla or rossa)
    if hasattr(result, 'data'):  # Rain tool
        for item in result.data:
            assert item.alert_level in ['gialla', 'rossa']
    elif hasattr(result, 'stations'):  # Hydro tool
        for item in result.stations:
            assert item.alert_level in ['pre-soglia', 'gialla', 'rossa']
```

**Benefits:**
- ✅ Test the pattern, not every permutation
- ✅ Easy to add new tools (just add to TOOL_TEST_CASES)
- ✅ Reduced from ~10 functions to 3 parametrized tests
- ✅ Tests enforce consistency across tools

### 8.2 Keep Tool-Specific Tests Minimal

**File: `tests/meteo/test_hydro_specific.py`** (~30 lines)
```python
"""Hydro-specific edge cases only."""

@pytest.mark.asyncio
async def test_hydro_pre_soglia_detection():
    """Test that pre-soglia (85% of threshold) is detected."""
    # Tool-specific test for hydro's unique alert level
    pass

@pytest.mark.asyncio
async def test_hydro_station_code_extraction():
    """Test extraction of [AIROL] from 'Airole [AIROL]'."""
    pass
```

**File: `tests/meteo/test_rain_specific.py`** (~30 lines)
```python
"""Rain-specific edge cases only."""

@pytest.mark.asyncio
async def test_rain_time_period_normalization():
    """Test 'ultima ora' → '1h' mapping."""
    pass

@pytest.mark.asyncio
async def test_rain_province_full_names():
    """Test that rain uses full names (Genova) not codes (GE)."""
    pass
```

**Impact:**
- 🎯 Test count: 10 functions → 3 parametrized + 4 specific = ~70% reduction
- ✅ Easier maintenance
- ✅ New tools inherit test coverage automatically

---

## ✅ Updated Success Criteria

### Phases 1-5 (COMPLETE)
1. ✅ **Zero v1 imports** - `grep -r "from tools.omirl" agents/` returns nothing
2. ✅ **Direct Pydantic models** - no dict → model mapping overhead
3. ✅ **Template summaries** - no `formatted_output` from v1
4. ✅ **Native scraping** - `OMIRLAdapter` uses Playwright directly
5. ✅ **Orchestrator foundation** - ready for multi-agent expansion
6. ✅ **Two working tools** - HydroStations and RainStations operational

### Phases 6-8 (IN PROGRESS)
7. 🚧 **Unified tool framework** - BaseMeteoTool eliminates duplication
8. 🚧 **Consolidated config** - Single meteo_config.yaml
9. 🚧 **Simplified tests** - Parametrized test suite

### Future (After MeteoAgent Complete)
10. 📅 **RAG Agent** - Document search and Q&A
11. 📅 **Multi-agent orchestration** - Parallel execution, result merging
12. 📅 **Caching layer** - 15-min TTL for OMIRL data
13. 📅 **Additional tools** - Wind, temperature, alerts, forecasts

---

## 📁 Updated Files Checklist

### Phase 1-5 (Complete)
- ✅ `agents/meteo/models.py` - Pydantic models
- ✅ `agents/meteo/agent.py` - Pydantic AI agent
- ✅ `agents/meteo/tools/hydro_stations.py` - Hydro tool
- ✅ `agents/meteo/tools/rain_stations.py` - Rain tool
- ✅ `services/web/adapters/omirl_adapter.py` - Native scraping
- ✅ `orchestrator/simple_orchestrator.py` - Query routing
- ✅ `tests/meteo/test_rain.py` - Rain tests
- ✅ `tests/meteo/test_meteo_agent.py` - Hydro tests

### Phase 6-8 (Next)
- 🚧 `agents/meteo/tools/base_tool.py` - NEW: Shared framework
- 🚧 `agents/meteo/config/meteo_config.yaml` - NEW: Unified config
- 🚧 `tests/meteo/test_tools_unified.py` - NEW: Parametrized tests
- 🚧 `tests/meteo/test_hydro_specific.py` - NEW: Hydro edge cases
- 🚧 `tests/meteo/test_rain_specific.py` - NEW: Rain edge cases
- 🚧 `agents/meteo/tools/hydro_stations.py` - REFACTOR: Use base class
- 🚧 `agents/meteo/tools/rain_stations.py` - REFACTOR: Use base class

### To Delete
- 🗑️ `agents/meteo/config/geography.yaml` - merge into meteo_config.yaml
- 🗑️ `agents/meteo/config/livelli_idrometrici_thresholds.yaml` - merge
- 🗑️ `agents/meteo/config/precipitazioni.yaml` - merge
- 🗑️ `tests/meteo/test_rain_simple.py` - replaced by unified tests

---

## 🚀 Updated Implementation Order

### ✅ Completed (Phases 1-5)
1. ✅ Native OMIRL scraping
2. ✅ Direct Pydantic pipeline
3. ✅ Template summaries
4. ✅ Simple orchestrator
5. ✅ MeteoAgent with 2 tools

### 🚧 Next Steps (Phases 6-8) - Estimated 3-4 hours
1. **Create BaseMeteoTool framework** (1 hour)
   - Write base class with shared logic
   - Abstract methods for tool-specific parts
   
2. **Consolidate configuration** (45 min)
   - Merge 3 YAML files into meteo_config.yaml
   - Update all loaders to use unified config
   
3. **Refactor existing tools** (1 hour)
   - HydroStationsTool extends BaseMeteoTool
   - RainStationsTool extends BaseMeteoTool
   - Verify functionality unchanged
   
4. **Simplify test suite** (1.5 hours)
   - Create parametrized test suite
   - Extract tool-specific edge case tests
   - Delete redundant test files
   
5. **Validation** (30 min)
   - Run full test suite
   - Verify line count reduction
   - Check for regressions

### 📅 Future (Post-Simplification)
- RAG Agent implementation
- Multi-agent parallel execution
- Caching layer
- Production deployment

**Total remaining effort:** ~3-4 hours for Phases 6-8, then ready for RAG Agent development.
