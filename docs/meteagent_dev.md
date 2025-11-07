# MeteoAgent Development Plan

## 🎯 Goal
Build a truly independent v2 MeteoAgent that eliminates ALL v1 dependencies and implements the promised simplifications.

---

## 📋 Phase 1: Native OMIRL Scraping (No v1 Dependency)

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

---

## 📋 Phase 2: Direct Pydantic Model Pipeline

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

---

## 📋 Phase 3: Template-Based Summaries (No LLM)

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

---

## 📋 Phase 4: Simple Orchestrator (Multi-Agent Ready)

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

**Later expansion:**
```python
# Multi-agent queries
if "autostrada" in query_lower and "pioggia" in query_lower:
    # Parallel execution
    traffic_task = self.agents["traffic"].run(query)
    meteo_task = self.agents["meteo"].run(query)
    results = await asyncio.gather(traffic_task, meteo_task)
    return self._merge_results(results)
```

---

## 📋 Phase 5: Update MeteoAgent to Use New Pipeline

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

---

## ✅ Success Criteria

After these phases, we should have:

1. **Zero v1 imports** - `grep -r "from tools.omirl" agents/` returns nothing
2. **Direct Pydantic models** - no dict → model mapping overhead
3. **Template summaries** - no `formatted_output` from v1
4. **Native scraping** - `OMIRLAdapter` uses Playwright directly
5. **Orchestrator foundation** - ready for multi-agent expansion

---

## 📁 Files Checklist

### New Files
- [ ] `agents/meteo/models.py` - Pydantic models
- [ ] `orchestrator/simple_orchestrator.py` - query routing
- [ ] `orchestrator/__init__.py`

### Modified Files
- [ ] `services/web/adapters/omirl_adapter.py` - native scraping
- [ ] `agents/meteo/tools/hydro_stations.py` - direct model pipeline
- [ ] `agents/meteo/agent.py` - cleaner interface
- [ ] `tests/meteo/test_hydro.py` - update for new models

### Deleted Code
- [ ] All v1 imports in v2 codebase
- [ ] Dict → model mapping functions
- [ ] `raw.get("formatted_output")` references

---

## 🚀 Implementation Order

1. **Phase 1.1** - Rewrite `fetch_livelli_idrometrici()` (native scraping)
2. **Phase 2** - Create Pydantic models, direct pipeline
3. **Phase 3** - Template summaries
4. **Phase 4** - Simple orchestrator
5. **Phase 5** - Update MeteoAgent
6. **Test** - Verify zero v1 dependencies

**Estimated effort:** 4-6 hours of focused work.
