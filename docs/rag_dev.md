# RAG Agent Development Guide

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
## Overview

The RAG (Retrieval-Augmented Generation) agent provides semantic search over civil protection documents indexed with Unstructured. It follows the same Pydantic AI pattern as MeteoAgent but queries a vector database instead of scraping live data.

**Architecture:**
```
User Query → Orchestrator → RagAgent → Vector Tools → Qdrant → Cited Results
                                    ↓
                              Figure/Table Decoder (optional)
```

## What We're Building

### Agent Capabilities

The RagAgent will answer questions by searching through:
- **Procedures** (`procedure`): Alert protocols, operational procedures, emergency response workflows
- **Plans** (`piani`): Municipal and provincial civil protection plans, evacuation plans
- **Event Reports** (`analisi`): Post-event analysis, historical reports, lessons learned
- **Quantitative Data** (`quantitative`): Statistical reports, risk assessments

### Core Tools

1. **search_procedures** - Find operational protocols and alert procedures
2. **search_plans** - Query civil protection plans by municipality/province
3. **search_event_reports** - Search historical event analysis
4. **search_all** - Generic semantic search across all categories
5. **get_figure_or_table** - Extract images/tables from chunks that contain them

## Data Pipeline

### 1. Unstructured Processing (One-Time Setup)

Documents are processed through Unstructured with these settings:

**Partition Strategy:**
- `hi_res` mode for accurate layout detection
- Extract coordinates for bounding boxes
- Capture images and tables as separate elements

**Chunking Strategy:**
- `by_title` chunker (respects document structure)
- ~900 chars per chunk (balances context vs. precision)
- **Contextual chunking and enrichment enabled** - prepends section context to each chunk (critical for quality)
- Combine small text blocks to avoid fragmentation

**Output:** `chunker.jsonl` file with one chunk per line

### 2. Indexing Workflow

A script (`scripts/index_chunks.py`) will:
1. Read chunks from `data/rag/chunker.jsonl`
2. Infer `doc_category` from filepath (e.g., `data/documents/piani/` → `"piani"`)
3. Embed `chunk.text` using OpenAI `text-embedding-3-small` or another embedding model (TBD)
4. Store in Qdrant collection `liguria_civil_protection` with full metadata

### 3. What Gets Stored

Each chunk in the vector DB contains:
- **element_id**: Unique chunk identifier
- **text**: Chunk content with contextual prefix from parent sections
- **metadata**:
  - filename, page_number
  - doc_category (for filtering)
  - orig_elements (Base64+Gzip JSON of atomic elements - for figure/table extraction)
  - bbox (bounding box coordinates - optional)

## Pydantic Models

### RagChunk
Represents a single search result with text, metadata, and similarity score.

### RagResult
Tool output containing:
- Original query
- List of matching chunks
- Template-based summary (not LLM - just citations)
- Optional figure/table payload

### FigurePayload
Decoded image or table from a chunk's `orig_elements`:
- Image: base64-encoded image data
- Table: HTML representation

## Implementation Strategy

### Vector Service (`services/data/vector.py`)

A thin wrapper around Qdrant client:
```python
def search(query: str, k: int = 6, category: str | None = None) -> list[RagChunk]:
    # If category provided, add filter to query
    # Return top-k chunks with scores
```

No caching needed - Qdrant is fast enough for real-time queries.

### Search Tools (`agents/rag/tools/search.py`)

Each tool follows the pattern:
1. Call `VectorService.search()` with appropriate category filter
2. Build template summary from results (filenames + pages + scores)
3. Return `RagResult` with chunks and summary

**Template summary example:**
```
Trovati 3 risultati da procedure operative:
• allerta_meteo_protocollo.pdf p.5 (rilevanza: 0.89)
• gestione_emergenze.pdf p.12 (rilevanza: 0.76)
• procedure_operative_PC.pdf p.8 (rilevanza: 0.71)
```

### Figure Tool (`agents/rag/tools/figures.py`)

For chunks that contain images or tables:
1. Load chunk payload from in-memory store (populated at startup)
2. Decode `orig_elements` (Base64+Gzip → JSON)
3. Find first Image or Table element
4. Return structured payload for rendering

**When to use:** Agent detects keywords like "figura", "mappa", "tabella" in query or in chunk context or chunk has image or table.

### Agent Definition (`agents/rag/agent.py`)

Standard Pydantic AI agent structure:

**System Prompt:**
- Explains available document categories
- Describes each tool's purpose
- Instructions for citation format
- Rule: always call figure tool if query mentions visual elements

**Tool Registration:**
```python
@self.agent.tool
async def tool_search_procedures(ctx, query: str, k: int = 6):
    """Cerca protocolli e procedure operative"""
    return await search_procedures(query, k)
```

**Agent Flow:**
1. LLM analyzes query to determine category
2. Calls appropriate search tool
3. If query mentions figures/tables, calls `get_figure_or_table` on top chunks
4. Synthesizes answer with citations

## Configuration

### Category Keywords (`agents/rag/config/rag_config.yaml`)

```yaml
categories:
  procedure:
    keywords: ["procedura", "protocollo", "allerta", "livello"]
  piani:
    keywords: ["piano", "evacuazione", "comune", "provincia"]
  analisi:
    keywords: ["evento", "post-event", "analisi", "storico"]
```

These help the orchestrator route queries to RagAgent (keyword matching before LLM routing).

### Vector DB Settings

```yaml
vector:
  collection: liguria_civil_protection
  embedding_model: text-embedding-3-small
  default_k: 6
```

## Orchestrator Integration

Add RAG routing to `orchestrator/simple_orchestrator.py`:

```python
# Keyword-based routing
if any(kw in query_lower for kw in ["piano", "procedura", "documento", "evento", "analisi"]):
    return await RagAgent().run(query)
```

Eventually this becomes part of the declarative routing rules for conditional orchestration mode.

## Testing Pattern

Follow the 3-test structure from MeteoAgent:

### Test 1: Direct Tool Call
```python
async def test_direct_tool():
    result = await search_plans("piano evacuazione Savona", k=3)
    assert result.chunks[0].metadata.doc_category == "piani"
```

### Test 2: Agent Natural Language
```python
async def test_agent_query():
    agent = RagAgent()
    response = await agent.run("Quali sono le procedure per allerta rossa?")
    assert "procedure" in response.lower()
```

### Test 3: Figure Extraction
```python
async def test_figure():
    fig = await get_figure_or_table("known_chunk_id_with_image")
    assert fig.ok and fig.kind == "image"
```

## Development Workflow

### Phase 1: Core Search (MVP)
1. Set up Qdrant locally (Docker)
2. Implement `VectorService` wrapper
3. Create search tools (procedures, plans, reports, all)
4. Build RagAgent with tool registration
5. Test with sample queries

### Phase 2: Figure/Table Extraction
1. Implement `orig_elements` decoder
2. Build in-memory chunk store (loaded at startup)
3. Add `get_figure_or_table` tool
4. Update system prompt to detect visual content queries

### Phase 3: Orchestrator Integration
1. Add RAG keyword patterns to orchestrator
2. Test end-to-end routing
3. Handle edge cases (no results, ambiguous queries)

### Phase 4: Evaluation (Future)
1. Create gold query set (10-20 questions with expected chunks)
2. Measure Hit@K and MRR
3. Manual relevance scoring
4. Tune chunking strategy if needed

## Critical Design Decisions

### Why Template Summaries (Not LLM)?
- **Speed**: Instant vs. 2-3 second LLM call
- **Cost**: Free vs. API costs per query
- **Determinism**: Always same format for same results
- **Transparency**: User sees exactly what was found

LLM summarization is Phase 7 future work.

### Why Direct Pydantic Models?
Chunks flow directly from Qdrant results to `RagChunk` models - no intermediate dicts. Cleaner code, better type safety.

### Why Category-Specific Tools?
- Better LLM tool selection (clear semantic boundaries)
- Enables precise filtering without over-retrieval
- Matches user mental model ("search plans" vs "search everything")

### Why In-Memory Chunk Store for Figures?
- Total corpus ~100MB uncompressed
- Faster than round-trip to Qdrant for payload retrieval
- Loaded once at startup, zero overhead at query time

### TBD
- embeddings model
- vector DB (Qdrant for now but maybe other options are better)
- chunking strategy

## Known Constraints & Gotchas

### Image Retrieval Requires Text Context
Images without captions or nearby text won't be found semantically. If this is a problem, run Unstructured's captioning enrichment before chunking.

### Category Tagging at Index Time
The `doc_category` field must be set during indexing based on folder structure:
```
data/documents/piani/*.pdf → category="piani"
data/documents/procedure/*.pdf → category="procedure"
```

### Contextual Chunking is Non-Negotiable
Without it, chunks lose section context and retrieval quality degrades significantly. Always enable in Unstructured workflow.

### JSONL vs JSON
Always ingest from JSONL (streaming-friendly, handles large corpora). Pretty JSON is only for manual inspection.

## File Structure

```
agents/rag/
  agent.py              # RagAgent with Pydantic AI
  models.py             # RagChunk, RagResult, FigurePayload
  config/
    rag_config.yaml     # Categories, vector settings
  tools/
    search.py           # Category-specific search tools
    figures.py          # Figure/table extraction

services/data/
  vector.py             # VectorService (Qdrant wrapper)

scripts/
  index_chunks.py       # One-time indexing script

data/rag/
  chunker.jsonl         # Unstructured export (not in git)

tests/rag/
  test_rag_agent.py     # 3-test pattern
```

## Future Enhancements

### Neo4j Knowledge Graph (Phase 7)
- Extract entities from chunks (EvacuationSite, Procedure, Risk, Organization)
- Link chunks to entity nodes with provenance
- Add `kg_query` tool for graph traversal
- Enable questions like "Show me all evacuation sites in Savona with capacity > 100"

### Answer Synthesis with Snippets
Instead of just citations, quote exact matching text from chunks in the answer.

### Cross-Encoder Reranking
After vector retrieval, rerank top-K chunks with a cross-encoder model for better precision.

### Evaluation Harness
Automated testing with gold queries, metrics, and regression detection.

## Anti-Patterns (Do NOT Do)

❌ **LLM for summaries** - Templates are faster, free, deterministic  
❌ **Dict intermediaries** - Build Pydantic models directly from Qdrant results  
❌ **Re-embed at query time** - Embed once during indexing  
❌ **Skip provenance** - Always return chunk_id + filename + page  
❌ **Ignore contextual chunking** - Quality depends on it  
❌ **Store embeddings in JSON** - Use proper vector DB

## Quick Start

```bash
# 1. Start Qdrant
docker run -p 6333:6333 qdrant/qdrant

# 2. Place chunker.jsonl in data/rag/

# 3. Index chunks
python scripts/index_chunks.py

# 4. Test
python tests/rag/test_rag_agent.py
```

## Example Query Flow

```
User: "Qual è la procedura per allerta rossa a Savona?"
  ↓
Orchestrator: keyword "procedura" → RagAgent
  ↓
RagAgent LLM: detects procedure search → calls search_procedures tool
  ↓
VectorService: query="procedura allerta rossa Savona", category="procedure"
  ↓
Qdrant: returns top 6 chunks with scores
  ↓
search_procedures: builds RagResult with template summary
  ↓
RagAgent: synthesizes final answer citing chunks
  ↓
Output: "In base al documento 'protocollo_allerta.pdf' (p.12), 
         la procedura per allerta rossa prevede..."
```

---

**Remember:** This is a conceptual guide. Implementation details will emerge during development. Stay pragmatic, test incrementally, and prioritize working code over perfect abstractions.
