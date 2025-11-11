# PromptAId Operations - Front-End Specification

## Application Overview

**Title**: PromptAId Operations: Dai Dati alla Decisione (From Data to Decision)

**Purpose**: Operational tool for Liguria's Regional Emergency Operations Center (EOC) analysts. Supports decision-makers (mayors, coordinators) during emergencies by aggregating multi-source data through AI agents with full transparency.

**Framework**: Streamlit (Python-native, rapid prototyping, simple deployment for emergency environments)

### Three-Section Structure

```
┌─────────────────────────────────────────────────┐
│  PromptAId Operations: Dai Dati alla Decisione  │
│  [Logo]                                          │
├─────────────────────────────────────────────────┤
│  [Tab: Chat] [Tab: Dashboard] [Tab: Valutazione]│
└─────────────────────────────────────────────────┘
```

- **Phase 1**: Chat interface with transparency metadata
- **Phase 2**: Geographic dashboard with maps and time series
- **Phase 3**: Evaluation section for quality feedback

---

## Design System - Civil Protection Colors

```css
--primary-blue: #004070;      /* Headers, titles, toggle OFF */
--primary-orange: #EF7D00;    /* Action buttons, toggle ON */
--alert-green: #2E7D32;       /* Normal status */
--alert-yellow: #F9A825;      /* Warning status */
--alert-red: #C62828;         /* Critical status */
```

**Color Usage**: Blue for institutional UI, Orange for active states, Red/Yellow/Green exclusively for alert levels.

---

## Chat Section

### Sidebar Control Panel (Italian labels)

**1. Agent Selector** ("Agenti Disponibili")
- Checkboxes: MeteoAgent (ATTIVO), RAGAgent (In sviluppo), TrafficAgent (In sviluppo)
- Auto-disable unimplemented agents
- Tooltips explain each agent's data sources

**2. Execution Mode Toggles** ("Modalità Esecuzione")
- **Tool Calling LLM**: OFF (keyword routing, fast) | ON (LLM routing, flexible)
- **Riassunti LLM**: OFF (template summaries, instant) | ON (LLM summaries, contextual)
- Default: Both OFF for operational speed

**3. Architecture Info** ("Architettura Sistema")
- Collapsible expander showing current pipeline
- Updates dynamically based on toggle states

### Main Chat Interface

**Message Structure**:
- **User query**: Italian natural language input ("Interagisci con gli agenti di monitoraggio...")
- **System response** :
  1. **Execution Metadata** (expandable blue box): Agente, Tool, Modalità, Parametri estratti, Timestamp, Cache status (HIT/MISS + TTL)
  2. **Results**: Response in natural language, following the tool templates or the llm base summary when activated
  3. **Artifacts**: artifacts such as tables scraped, screenshots, or extracts from RAG should be consultabl via a link

**Transparency Goal**: Every response shows full execution trace for decision accountability

### Result Display Patterns

---

## Dashboard Section (Phase 2)

Simple dashboard that shows data pulled from the sources connected to the agents:
- OMIRL station monitoring
- metadata on RAG repository
- traffic website
- etc.

---

## Evaluation Section (Phase 3)

**Purpose**: Continuous improvement loop - operators evaluate query-response pairs to inform model fine-tuning and feature development

**Evaluation Interface**:
- **Filters**: Periodo (Ultime 24 ore/7 giorni/mese), Agente, Stato valutazione, Modalità
- **Conversation Card**: Shows query, extracted params, result summary, full metadata
- **3 Criteria** (1-5 sliders, Italian labels):
  - **Spiegabilità**: Metadata clarity, routing transparency, data source visibility
  - **Usabilità**: did they actually use it for decision making?
  - **Accuratezza**: Parameter correctness, result relevance, data freshness
- **Free Text**: "Note Aggiuntive" for edge cases and suggestions

**Statistics Dashboard**:
- Overall averages with trend deltas
- Time series charts
- Breakdown by agent
- Recent feedback highlights

**Use Cases**:
1. **Daily Quality Check**: Operators review previous shift's conversations
2. **Model Improvement**: Admins analyze trends to prioritize fixes (low scores → action items)
3. **Feature Prioritization**: Product team mines free-text for common requests
4. **Compliance**: Track decision-support quality for audits

**Storage**: File-based JSON initially → SQLite → PostgreSQL for multi-user

**Integration**: "Valuta questa risposta" button in chat triggers immediate evaluation

---

---

## UI Development Roadmap

### Phase 1: MVP Chat Interface (Week 1-2) **← PRIORITY**
- [ ] Base Streamlit setup with PC colors and the three main sections (dashboard and evaluation are just placeholders)
- [ ] Header with logo and title
- [ ] Sidebar control panel (agents + toggles)
- [ ] Chat interface 

### Phase 2: Geographic Dashboard (Week 6-8)
- [ ] Interactive Liguria map with stations
- [ ] Tables with stations
- [ ] Metadata on RAG repository

### Phase 3: Evaluation Section (Week 9-10)
- [ ] Conversation list with filters
- [ ] Evaluation form (3 criteria + free text)
- [ ] File-based evaluation storage
- [ ] Statistics dashboard with trends
- [ ] "Valuta questa risposta" button in chat
- [ ] Export evaluation reports

---

## Key Implementation Notes

**Why Streamlit**: Python-native, rapid prototyping (hours not days), built-in reactivity, simple deployment, rich data viz ecosystem

**Deployment**: `streamlit run app/main.py --server.port 8501` + `.streamlit/config.toml` for PC colors theme
