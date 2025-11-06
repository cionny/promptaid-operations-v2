# PromptAid Operations v2

## 🎯 What Changed from v1

**v1 Problems:**
- LLM routing → validator → tool execution = too many steps
- LangGraph state management = hard to debug
- LLM summaries = slow and expensive
- Over-engineered abstractions

**v2 Solution:**
- **Pydantic AI agents** with built-in tool calling
- **LLM for parameter extraction** (not routing decisions)
- **Smart orchestrator** supporting parallel + conditional execution
- **Template-based summaries** (no LLM needed)
- **Simpler architecture**: Query → Orchestrator → Agent(s) → Tools → Result

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

## 🏗️ Architecture

### Simple Query (Single Agent)
```
User: "Quali fiumi sono in piena a Savona?"
    ↓
Orchestrator (keyword: "fiumi" → MeteoAgent)
    ↓
MeteoAgent (Pydantic AI extracts: {provincia: "SV"})
    ↓
HydroStationsTool.run(provincia="SV")
    ↓
Result: HydroStationsResult
```

### Parallel Query (Multiple Agents)
```
User: "Quali sono i fiumi in piena e le strade bloccate nella regione?"
    ↓
Orchestrator (keywords: "fiumi" + "strade")
    ↓
├─→ MeteoAgent.run("fiumi in piena")     [parallel]
└─→ TrafficAgent.run("strade bloccate")  [parallel]
    ↓
Orchestrator.aggregate([meteo_result, traffic_result])
    ↓
Result: UnifiedOperationalResponse
```

### Conditional Query (Agent Chain)
```
User: "Quali comuni hanno livelli di pioggia critici e gli hotspot da monitorare?"
    ↓
Orchestrator (keyword: "pioggia" + "e hotspot" → conditional mode)
    ↓
MeteoAgent.run("livelli di pioggia critici")
    ↓
Result: critical_count = 2, comuni_critici = ["Genova", "Savona"]
    ↓
Orchestrator evaluates conditional rules:
    - Rule: if critical_count > 0 → trigger RAGAgent
    ↓
RAGAgent.run(task="retrieve_hotspots", comuni=["Genova", "Savona"])
    ↓
Orchestrator.aggregate([meteo_result, rag_result])
    ↓
Result: UnifiedOperationalResponse
```

**Conditional Execution Strategy** (2-phase approach):

**Phase 1 (Week 4-5): Declarative Rules**
```python
# orchestrator/conditional_rules.py
CONDITIONAL_RULES = [
    ConditionalRule(
        trigger_agent="MeteoAgent",
        condition=lambda r: r.critical_count > 0,
        then_execute="RAGAgent",
        context_builder=lambda r: {
            "comuni": [s.comune for s in r.stations if s.alert_level == "red"],
            "task": "retrieve_hotspots"
        },
        description="Retrieve hotspots when critical stations detected"
    )
]
```

**Phase 2 (Week 6+): LLM-Based Planning** (for complex queries declarative rules can't handle)
```python
# When declarative rules don't match, fall back to LLM planner
planner = Agent(
    model='openai:gpt-4o-mini',
    result_type=ExecutionPlan,
    system_prompt="Analyze query and determine conditional execution logic..."
)
plan = await planner.run(query)
# Plan specifies: primary agent, condition to check, secondary agent to trigger
```

Why both approaches?
- **Declarative rules** = fast, deterministic, auditable (cover 80% of cases)
- **LLM planning** = handles novel queries, complex multi-step logic (remaining 20%)

---

## 🎯 Orchestrator Design

### Agent Selection Strategy

```python
class Orchestrator:
    """
    Smart orchestrator supporting:
    - Single agent execution
    - Parallel multi-agent execution
    - Conditional agent chaining (declarative rules + LLM fallback)
    """
    
    def analyze_query(self, query: str) -> ExecutionPlan:
        """
        Returns execution plan with:
        - agents: List of agents to run
        - mode: "single" | "parallel" | "conditional"
        - conditional_rules: Optional rules for conditional mode when the execution of an agent depends on the results of another
        """
        
        # Keyword-based agent mapping
        agents = []
        if any(kw in query for kw in ["fiumi", "pioggia", "livelli", "piena"]):
            agents.append("MeteoAgent")
        if any(kw in query for kw in ["strade", "autostrade", "traffico"]):
            agents.append("TrafficAgent")
        if any(kw in query for kw in ["procedura", "piano", "hotspot"]):
            agents.append("RAGAgent")
        
        # Determine execution mode
        if len(agents) == 1:
            return ExecutionPlan(agents=agents, mode="single")
        
        # Check for conditional keywords
        conditional_keywords = ["e hotspot", "e procedure", "e monitorare", 
                               "poi", "quindi", "se", "in caso di"]
        if any(kw in query.lower() for kw in conditional_keywords):
            return ExecutionPlan(
                agents=agents,
                mode="conditional",
                conditional_rules=self.find_matching_rules(agents)
            )
        
        # Multiple independent tasks → parallel
        return ExecutionPlan(agents=agents, mode="parallel")
    
    def find_matching_rules(self, agents: List[str]) -> List[ConditionalRule]:
        """Find declarative rules matching the agent combination"""
        return [
            rule for rule in CONDITIONAL_RULES 
            if rule.trigger_agent in agents
        ]
```

### Execution Modes

#### 1. Single Agent (Week 1-2 focus)
```python
result = await meteo_agent.run("fiumi in piena a Savona")
return MeteoResponse(data=result)
```

#### 2. Parallel Execution (Week 3-4)
```python
results = await asyncio.gather(
    meteo_agent.run("fiumi in piena"),
    traffic_agent.run("strade bloccate")
)
return UnifiedOperationalResponse(
    meteo_data=results[0],
    traffic_data=results[1]
)
```

#### 3. Conditional Chaining (Week 4-6)

**Phase 1: Declarative (Week 4-5)**
```python
# Execute primary agent
meteo_result = await meteo_agent.run("livelli pioggia critici")

# Check declarative rules
for rule in matching_rules:
    if rule.condition(meteo_result):
        context = rule.context_builder(meteo_result)
        secondary_result = await self.get_agent(rule.then_execute).run(**context)

return self.aggregate([meteo_result, secondary_result])
```

**Phase 2: LLM Fallback (Week 6+)**
```python
# If no declarative rules match complex query, use LLM planner
if not matching_rules:
    plan = await self.llm_planner.run(query)
    
    # Execute based on LLM-generated plan
    primary_result = await self.get_agent(plan.primary_agent).run(query)
    
    if self.evaluate_llm_condition(primary_result, plan.condition):
        secondary_result = await self.get_agent(plan.secondary_agent).run(
            **plan.context_mapping
        )
        return self.aggregate([primary_result, secondary_result])
```

---

## 📂 Workspace Usage

**operations-v1**: Reference only - study patterns, reuse logic concepts, but never import or deploy v1 code in production.

**operations-v2**: Production codebase - all new development happens here. Adapt v1 patterns where useful, but write fresh, simplified code.

---

## 📁 Repository Structure

```
operations-v2/
├── orchestrator/
│   ├── orchestrator.py           # Smart orchestrator with execution modes
│   ├── conditional_rules.py      # Declarative conditional rules
│   ├── llm_planner.py            # LLM-based planner (Phase 2)
│   ├── summarizer.py             # LLM-based summarizer (Phase 3)
│   ├── execution_plan.py         # ExecutionPlan model
│   └── aggregator.py             # Result aggregation logic
│
├── agents/
│   ├── meteo/
│   │   ├── agent.py              # MeteoAgent (Pydantic AI)
│   │   └── tools/
│   │       ├── hydro_stations.py # HydroStationsTool, corresponds to livelli_idro.py in v1
│   │       └── rain_stations.py  # RainStationsTool corresponds to massimi_precipitazione in v1
│   │
│   ├── traffic/                  # (Future - Week 3-4)
│   │   └── agent.py
│   │
│   └── rag/                      # (Future - Week 4-5)
│       └── agent.py
│
├── models/
│   ├── base.py                   # BaseFilters, BaseResult
│   ├── meteo.py                  # MeteoFilters, MeteoResponse
│   ├── traffic.py                # (Future)
│   ├── rag.py                    # (Future)
│   └── unified.py                # UnifiedOperationalResponse
│
├── services/                     # Adapted from v1
│   ├── cache/                    # Redis/file cache
│   └── scraper/                  # OMIRL scraper
│
└── tests/
    ├── orchestrator/
    │   ├── test_single_agent.py
    │   ├── test_parallel.py
    │   ├── test_conditional_declarative.py
    │   ├── test_conditional_llm.py
    │   └── test_llm_summarizer.py
    └── agents/meteo/
        └── test_hydro_tool.py
```

---

## 🚀 Implementation Phases

### ✅ Phase 1: Single Agent - MeteoAgent (Week 1-2) **← START HERE**
- [ ] Copy v1 scraper to `services/scraper/`
- [ ] Create `models/meteo.py` (HydroFilters, HydroStationsResult)
- [ ] Implement `HydroStationsTool`, corresponds to `livelli_idro.py` in v1
- [ ] Create `MeteoAgent` with Pydantic AI 
- [ ] Implement `RainStationsTool` corresponds to `massimi_precipitazione.py` in v1
- [ ] Implement `OtherSensorTool` corresponds to `valori_stazioni.py` in v1
- [ ] Simple orchestrator (single agent mode only)
- [ ] Test: "Quali fiumi sono in piena in zona A?"

### 📋 Phase 2: Implement RAG Agent
- [ ] Implement `RAGAgent` (vector DB + retrieval)
- [ ] Create CP plans retrieval tools
- [ ] Create past events and historic data retrieval tools
- [ ] Create one tool per source and type of documents

### 📋 Phase 3: Parallel Execution (Week 3-4)
- [ ] Add parallel execution to orchestrator
- [ ] Implement `aggregator.py` for combining results
- [ ] Test: "Fiumi in piena e procedure evacuazione?"

### 🔗 Phase 4: Conditional Chaining - Declarative (Week 4-5)
- [ ] Create `conditional_rules.py` with declarative rules
- [ ] Add conditional logic to orchestrator
- [ ] Test: "Livelli pioggia critici e hotspot da monitorare?"
- [ ] Identify cases where declarative rules are insufficient

### 🧠 Phase 5: Conditional Chaining - LLM Planner (Week 6)
- [ ] Implement `llm_planner.py` for complex conditional logic
- [ ] Add LLM fallback when declarative rules don't match
- [ ] Test complex multi-step queries
- [ ] Compare declarative vs LLM accuracy and latency

### 🎨 Phase 6: Implement Traffic Agent (Week 7)
- [ ] Implement traffic agent
- [ ] Test: "Fiumi in piena e strade bloccate?"

### 📝 Phase 7: LLM-Based Summarization (Week 8+)
- [ ] Implement `orchestrator/summarizer.py`
- [ ] Add intelligent summary generation for multi-agent responses
- [ ] Compare template vs LLM summary quality
- [ ] Add configuration for summary verbosity levels

---

### 6. Reuse v1 Services
```python
# In agents/meteo/tools/hydro_stations.py
from services.scraper.omirl_adapter import scrape_livelli_idrometrici
from services.cache.cache_service import get_cached

async def run(self, filters: HydroFilters):
    # Try cache first (10 min TTL)
    cached = await get_cached(f"hydro_{filters.zona_allerta}", ttl=600)
    if cached:
        return HydroStationsResult.model_validate(cached)
    
    # Scrape fresh data (reuse v1 logic)
    raw_data = await scrape_livelli_idrometrici(zona=filters.zona_allerta)
    # ... process and return
```