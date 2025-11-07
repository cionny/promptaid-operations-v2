# AI Coding Agent Instructions - PromptAid Operations v2

## Project Context

This is **v2** - a complete rewrite from v1 that eliminates over-engineered abstractions and LLM routing overhead. The v1 workspace exists for reference only - **never import or deploy v1 code in production**.

**Core Architecture Change:**
- v1: `LLM routing → validator → tool execution` (slow, complex)
- v2: `Orchestrator → Pydantic AI Agents → Tools → Structured Results` (fast, simple)

## Critical Principles

### 1. Documentation is Directional, Not Prescriptive

The README and docs provide **possibilities, not requirements**. When implementing:
- Analyze the problem first - understand the actual requirement
- Evaluate suggested approaches - propose improvements if you see better ways
- Stay pragmatic - prefer simple, maintainable code over clever abstractions
- Challenge assumptions - examples might not cover your specific case

**Always prioritize:** code clarity, performance, testability, real-world usage patterns.

### 2. Direct Pydantic Model Pipeline

Build Pydantic models **directly from data sources** - never use intermediate dicts:

```python
# ❌ WRONG: Dict → Model conversion
raw_data = scraper.get_data()  # Returns dict
station = HydroStation(**raw_data)  # Wasteful conversion

# ✅ CORRECT: Direct Pydantic construction
RawHydroStation → _enrich() → EnrichedHydroStation → HydroStationsResult
```

See `agents/meteo/tools/hydro_stations.py` for the pattern.

### 3. Template-Based Summaries (Not LLM)

Default to template-based summaries for speed and determinism. Only use LLM summarization when explicitly needed:

```python
# Default approach (fast, free, predictable)
summary = f"🔴 Criticità rilevate: {critical_count}\n🟡 Allerta: {warning_count}"

# LLM summarization is Phase 7 future work
```

## Architecture Map

### Execution Modes (Orchestrator)

1. **Single Agent** (current): `orchestrator/simple_orchestrator.py` - keyword routing to one agent
2. **Parallel** (planned): Multiple agents run concurrently, results aggregated
3. **Conditional** (planned): Agent chains with declarative rules → LLM fallback for complex queries

### Agent Structure (Pydantic AI)

Each agent in `agents/*/agent.py` follows this pattern:

```python
from pydantic_ai import Agent

SYSTEM_PROMPT = "Specific task instructions + parameter extraction guidance"

class MeteoAgent:
    def __init__(self, model: str = "google-gla:gemini-2.0-flash-lite"):
        self.agent = Agent(model, system_prompt=SYSTEM_PROMPT, retries=2)
        
        @self.agent.tool
        async def tool_name(ctx, param1: str | None = None) -> ResultModel:
            """Docstring used by LLM to understand when to call this tool."""
            return await fetch_data(filters=Filters(param1=param1))
```

**Key Points:**
- System prompt tells LLM **when** to use tools and **what parameters** to extract
- Tool docstrings describe **capabilities** for LLM decision-making
- LLM extracts parameters, not routing decisions
- Tools return structured Pydantic models

### Service Layer Patterns

#### Web Scraping (`services/web/`)

**3-layer separation:**
- `base.py`: Abstract interfaces (`IBrowserManager`, `ITableScraper`)
- `generic_*.py`: Reusable implementations (browser lifecycle, table extraction)
- `adapters/*_adapter.py`: Site-specific logic (OMIRL selectors, data mappings)

**Configuration-driven:** OMIRL adapter uses `configs/omirl_config.py` for all selectors, timeouts, and locale settings.

#### Caching (`services/data/cache.py`)

File-based TTL cache for scraping results:
- Default 15-minute TTL (emergency management needs freshness)
- Cache keys: `md5(tool|task|params)`
- Atomic writes, automatic cleanup
- See extensive docstring for web scraping considerations

### Configuration Strategy

**YAML configs in `agents/*/config/`:**
- `geography.yaml`: Province codes, comuni mappings, alert zones (shared constants)
- `*_thresholds.yaml`: Alert level thresholds (normal/yellow/red) for each station
- `precipitazioni.yaml`: Rain accumulation thresholds by time period

**Province handling example:** Users say "Savona" or "SV", configs normalize to "SV" code:
```python
geo = _load_geography()
mapping = geo['provinces']['name_to_code_mapping']
prov_code = mapping.get(prov_input, prov_input).upper()
```

## Development Workflows

### Running Tests

Tests use direct execution (no pytest framework yet):

```bash
cd /home/jeanbaptistebove/projects/operations-v2
python tests/meteo/test_meteo_agent.py           # Demo tests
python tests/meteo/test_orchestrator.py          # Routing tests
```

See `tests/meteo/test_meteo_agent.py` for the 3-test pattern:
1. Direct tool call with filters
2. Agent with natural language query
3. Generic query (no filters)

### Environment Setup

```bash
# Required API keys in .env:
GEMINI_API_KEY=...  # Auto-mapped to GOOGLE_API_KEY for Pydantic AI

# Dependencies (no requirements.txt yet - infer from imports):
pydantic-ai, playwright, pyyaml, python-dotenv
```

### Adding New Tools

1. **Create models** in `agents/*/models.py`:
   - `RawModel` (direct from scraper)
   - `EnrichedModel` (with threshold/alert analysis)
   - `ResultModel` (final tool output with summary, counts, filters)

2. **Implement tool** in `agents/*/tools/*.py`:
   - Load configs with `@lru_cache` decorated loaders
   - `_enrich()` function: RawModel → EnrichedModel
   - `_apply_filters()`: Filter enriched data
   - `fetch_*()` main function returning ResultModel

3. **Register in agent** via `@self.agent.tool` decorator with clear docstring

## Avoid These Mistakes

1. ❌ Don't import from v1 workspace (`operations/`) - rewrite or adapt concepts only
2. ❌ Don't create intermediate dicts when building Pydantic models - go direct from source
3. ❌ Don't prioritize LLM for routing - orchestrator uses keyword matching, and llm routing will be added later for complex cases
4. ❌ Don't use LLM for summaries (yet) - templates first, LLM is Phase 7
5. ❌ Don't treat README examples as strict specs - analyze and propose better approaches
7. VERY IMPORTANT: keep the code lean and maintainable; avoid over-engineering.

## Reference Files

**Start here for patterns:**
- `agents/meteo/agent.py` - Pydantic AI agent structure

### For MeteoAgent
- `agents/meteo/tools/hydro_stations.py` - Complete tool implementation
- `services/web/adapters/omirl_adapter.py` - Web scraping pattern
- `services/data/cache.py` - Extensive caching documentation
- `docs/agents.md` - Tool specifications and threshold configs

### For other agents
- always ask before starting new agents

**Current implementation status:** Single agent mode with MeteoAgent's HydroStationsTool working end-to-end. Orchestrator is simple but ready for future multi-agent modes.
