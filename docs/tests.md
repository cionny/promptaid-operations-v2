## 🧪 Testing Strategy

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

### Single Agent Tests (Phase 1)
```python
@pytest.mark.asyncio
async def test_meteo_agent_hydro():
    orchestrator = Orchestrator()
    result = await orchestrator.run("Fiumi in piena in zona A?")
    
    assert result.execution_mode == "single"
    assert result.meteo_data is not None
    assert result.template_summary.startswith("Monitoraggio")
```

### Parallel Execution Tests (Phase 2)
```python
@pytest.mark.asyncio
async def test_parallel_meteo_traffic():
    orchestrator = Orchestrator()
    result = await orchestrator.run("Fiumi in piena e strade bloccate?")
    
    assert result.execution_mode == "parallel"
    assert result.meteo_data is not None
    assert result.traffic_data is not None
```

### Conditional - Declarative Tests (Phase 3)
```python
@pytest.mark.asyncio
async def test_conditional_declarative():
    orchestrator = Orchestrator()
    result = await orchestrator.run("Pioggia critica e hotspot da monitorare?")
    
    assert result.execution_mode == "conditional"
    assert result.conditional_method == "declarative"
    
    if result.meteo_data.critical_count > 0:
        assert result.rag_data is not None
```

### Conditional - LLM Fallback Tests (Phase 4)
```python
@pytest.mark.asyncio
async def test_conditional_llm_complex_query():
    orchestrator = Orchestrator()
    result = await orchestrator.run(
        "Se pioggia supera 80mm in qualsiasi stazione costiera, "
        "recupera procedure evacuazione per comuni limitrofi"
    )
    
    assert result.execution_mode == "conditional"
    assert result.conditional_method == "llm"
```

### LLM Summarizer Tests (Phase 6)
```python
@pytest.mark.asyncio
async def test_llm_summary_generation():
    orchestrator = Orchestrator(use_llm_summary=True)
    result = await orchestrator.run(
        "Fiumi in piena e strade bloccate a Genova",
        verbosity="detailed"
    )
    
    assert result.llm_summary is not None
    assert result.template_summary is not None
    
    # LLM summary should be more coherent than template
    assert len(result.llm_summary) > len(result.template_summary)
    assert "Genova" in result.llm_summary

@pytest.mark.asyncio
async def test_template_vs_llm_summary():
    """Compare template and LLM summary quality"""
    orchestrator_template = Orchestrator(use_llm_summary=False)
    orchestrator_llm = Orchestrator(use_llm_summary=True)
    
    query = "Livelli critici e procedure emergenza"
    
    result_template = await orchestrator_template.run(query)
    result_llm = await orchestrator_llm.run(query)
    
    # Template should be fast
    assert result_template.total_execution_time_ms < 3000
    
    # LLM summary should add latency but be more readable
    assert result_llm.total_execution_time_ms > result_template.total_execution_time_ms
    assert result_llm.llm_summary is not None
```

---

## 💡 Example Queries by Phase

### Phase 1 (Single Agent)
- ✅ "Quali fiumi sono in piena in zona A?"
- ✅ "Livelli idrometrici provincia di Savona"
- ✅ "Stazioni critiche bacino del Bisagno"

### Phase 2 (Parallel)
- ✅ "Fiumi in piena e strade bloccate nella regione"
- ✅ "Situazione meteo e traffico autostrade"

### Phase 3 (Conditional - Declarative)
- ✅ "Comuni con pioggia critica e hotspot da monitorare"
- ✅ "Livelli sopra soglia e procedure da attivare"

### Phase 4 (Conditional - LLM)
- ✅ "Se accumulo pioggia > 80mm in zone costiere, trova rifugi più vicini"
- ✅ "Quando temperatura sotto 0°C e vento > 50km/h, procedure ghiaccio stradale"

### Phase 5 (Advanced)
- ✅ "Quanto ha piovuto a Genova nelle ultime 6 ore?"
- ✅ "Accumuli oltre 50mm e rischio frane associate"

### Phase 6 (LLM Summaries)
- ✅ "Situazione complessiva emergenza idrogeologica Liguria" (detailed summary)
- ✅ "Brief sulla situazione corrente per coordinatore protezione civile" (brief summary)

---

## 🎯 Success Criteria

### Phase 1 Complete When:
- [ ] Query "Fiumi in piena in zona A" returns HydroStationsResult
- [ ] Pydantic AI extracts zona_allerta="A"
- [ ] Results cached for 10 minutes
- [ ] Template summary works
- [ ] Unit tests >80% coverage

### Phase 3 Complete When:
- [ ] Declarative rules correctly trigger RAGAgent when critical_count > 0
- [ ] Context properly extracted from MeteoAgent result
- [ ] Tests show RAG not triggered when no critical stations

### Phase 4 Complete When:
- [ ] LLM planner handles complex conditional queries
- [ ] Comparison shows declarative covers 80%+ of common cases
- [ ] LLM fallback adds <500ms latency

### Phase 6 Complete When:
- [ ] LLM summarizer generates coherent multi-agent summaries
- [ ] Verbosity levels (brief/standard/detailed) work correctly
- [ ] Template vs LLM summary comparison shows clear quality improvement
- [ ] LLM summary latency < 1000ms
- [ ] User feedback confirms summaries are actionable for operators
