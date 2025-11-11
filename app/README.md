# PromptAId Operations v2 - Streamlit UI

## Quick Start

### 1. Install Dependencies

```bash
# Activate your conda environment
conda activate promptaid_ops

# Install Streamlit and required packages
pip install streamlit pandas
```

### 2. Run the Application

```bash
cd /home/jeanbaptistebove/projects/operations-v2
streamlit run app/main.py
```

The app will open at `http://localhost:8501`

### 3. Test Backend Connection (Optional)

Before running the full app, you can test the backend connection:

```bash
python tests/test_backend_connection.py
```

## Application Structure

```
app/
├── main.py              # Main Streamlit app (Chat interface)
├── backend_client.py    # Backend orchestrator connection
├── logo/                # PromptAId logo
├── pages/
│   ├── 2_Dashboard.py   # Dashboard (placeholder)
│   └── 3_Valutazione.py # Evaluation (placeholder)
└── assets/
    └── styles.css       # Custom CSS (future)
```

## Features

### ✅ Phase 1 (Current)
- Chat interface with real-time streaming
- MeteoAgent integration (hydro levels, precipitation data)
- Expandable metadata display (like ChatGPT reasoning)
- Artifacts section (tables, links to OMIRL)
- Civil Protection color theme
- Sidebar controls:
  - Agent selector (MeteoAgent active)
  - Toggle LLM tool calling (OFF by default)
  - Toggle LLM summaries (OFF by default)
  - Architecture info expander

### 🚧 Phase 2 (Planned)
- Dashboard with OMIRL station monitoring
- Geographic visualizations
- RAG repository metadata

### 🚧 Phase 3 (Planned)
- Evaluation section
- Quality metrics tracking
- Feedback collection

## Configuration

### Colors
Civil Protection official colors are configured in `.streamlit/config.toml`:
- **Blu (Blue)**: #004070 - Headers, institutional UI
- **Arancio (Orange)**: #EF7D00 - Active states, primary actions
- **Alert colors**: Green #2E7D32, Yellow #F9A825, Red #C62828

### API Keys Setup

Streamlit loads API keys from `.streamlit/secrets.toml`. The file should contain:

```toml
GEMINI_API_KEY = "your-key-here"
GOOGLE_API_KEY = "your-key-here"
```

The app automatically loads these as environment variables for the agents to use.

**Note**: `.streamlit/secrets.toml` is in `.gitignore` - never commit API keys!

## Troubleshooting

### "command not found: streamlit"
```bash
pip install streamlit
```

### Port already in use
```bash
streamlit run app/main.py --server.port 8502
```

### Browser doesn't open automatically
Navigate manually to: `http://localhost:8501`

### Backend connection issues
1. Verify Playwright is installed: `playwright install chromium`
2. Check API keys are set in `.env`
3. Run the test script: `python tests/test_backend_connection.py`
