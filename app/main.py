"""
PromptAId Operations - Main Application Entry Point
Chat interface for multi-agent emergency operations system
"""

import streamlit as st
import sys
from pathlib import Path
import asyncio
import os

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.backend_client import get_backend_client

# Load API keys from Streamlit secrets and set as env vars
if "GEMINI_API_KEY" in st.secrets:
    os.environ["GEMINI_API_KEY"] = st.secrets["GEMINI_API_KEY"]
if "GOOGLE_API_KEY" in st.secrets:
    os.environ["GOOGLE_API_KEY"] = st.secrets["GOOGLE_API_KEY"]
if "OLLAMA_BASE_URL" in st.secrets:
    os.environ["OLLAMA_BASE_URL"] = st.secrets["OLLAMA_BASE_URL"]

# Page configuration
st.set_page_config(
    page_title="PromptAId Operations",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for Civil Protection colors
def load_custom_css():
    """Apply custom CSS with Civil Protection brand colors
    
    Civil Protection Official Colors:
    - BLU: PANTONE 7694 C - #004070 (R:0 G:64 B:112)
    - ARANCIO: PANTONE 1505 C - #EF7D00 (R:239 G:125 B:0)
    """
    st.markdown("""
        <style>
        /* Main app background */
        .stApp {
            background-color: #F5F5F5;
        }
        
        /* Headers - Civil Protection Blue */
        h1, h2, h3 {
            color: #004070 !important;
        }
        
        /* Sidebar styling */
        [data-testid="stSidebar"] {
            background-color: #FFFFFF;
        }
        
        [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
            color: #004070 !important;
        }
        
        /* Toggle switches - Orange when ON */
        .stCheckbox label {
            color: #212121;
        }
        
        /* Expander for metadata - Blue border */
        .streamlit-expanderHeader {
            background-color: #E3F2FD !important;
            border-left: 4px solid #004070 !important;
            color: #004070 !important;
            font-weight: 600;
        }
        
        /* Button styling - Orange primary */
        .stButton > button[kind="primary"] {
            background-color: #EF7D00 !important;
            color: white !important;
            border: none !important;
        }
        
        .stButton > button[kind="primary"]:hover {
            background-color: #D66D00 !important;
        }
        
        /* Chat input styling */
        .stChatInput {
            border-color: #004070 !important;
        }
        
        /* Dividers */
        hr {
            border-color: #E0E0E0 !important;
        }
        
        /* Alert colors for badges */
        .alert-critical {
            background-color: #C62828;
            color: white;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: bold;
        }
        
        .alert-warning {
            background-color: #F9A825;
            color: white;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: bold;
        }
        
        .alert-normal {
            background-color: #2E7D32;
            color: white;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-weight: bold;
        }
        </style>
    """, unsafe_allow_html=True)

load_custom_css()

# Header with logo and title
col1, col2 = st.columns([1, 6])
with col1:
    # Logo is in app/logo/ directory
    logo_path = Path(__file__).parent / "logo" / "PromptAId Logo.svg"
    if logo_path.exists():
        st.image(str(logo_path), width=120)
    else:
        # Fallback if logo not found
        st.markdown("🛡️", unsafe_allow_html=True)
with col2:
    st.markdown(
        "<h1 style='color: #004070;'>PromptAId Operations: Dai Dati alla Decisione</h1>",
        unsafe_allow_html=True
    )

# Sidebar - Control Panel
with st.sidebar:
    st.header("Pannello di Controllo")
    
    # Agent Selection
    st.subheader("Agenti Disponibili")
    
    agents = {
        "MeteoAgent": {
            "active": True, 
            "status": "ATTIVO",
            "description": "Dati meteorologici da OMIRL (livelli idrometrici, precipitazioni, sensori)"
        },
        "RAGAgent": {
            "active": False, 
            "status": "In sviluppo",
            "description": "Procedure di protezione civile, eventi storici, hotspot critici"
        },
        "TrafficAgent": {
            "active": False, 
            "status": "In sviluppo",
            "description": "Viabilità, chiusure stradali, incidenti autostradali"
        }
    }
    
    enabled_agents = []
    for agent_name, config in agents.items():
        if config["active"]:
            enabled = st.checkbox(
                f"{agent_name} ({config['status']})",
                value=True,
                key=f"agent_{agent_name}",
                help=config["description"]
            )
            if enabled:
                enabled_agents.append(agent_name)
        else:
            st.checkbox(
                f"{agent_name} ({config['status']})",
                value=False,
                disabled=True,
                key=f"agent_{agent_name}",
                help=config["description"]
            )
    
    st.divider()
    
    # Execution Mode Toggles
    st.subheader("Modalità Esecuzione")
    
    llm_tool_calling = st.toggle(
        "Tool Calling LLM",
        value=True,
        help="OFF: routing deterministico via keyword (veloce) | ON: routing via LLM (flessibile)"
    )
    
    llm_summaries = st.toggle(
        "Riassunti LLM",
        value=False,
        help="OFF: riassunti template (immediato) | ON: riassunti generati da LLM (contestuale)"
    )
    
    st.divider()
    
    # Architecture Info
    with st.expander("Architettura Sistema", expanded=False):
        if llm_tool_calling:
            pipeline = "Query → LLM Planner → Agente → Tool → Risultato"
            mode = "LLM-based"
        else:
            pipeline = "Query → Orchestrator (keyword) → Agente → Tool → Risultato"
            mode = "Deterministico"
        
        st.code(pipeline, language=None)
        st.caption(f"Modalità attuale: {mode}")

# Main Chat Interface
st.subheader("Conversazione")

# Initialize session state for messages
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "assistant":
            # Expandable metadata (like ChatGPT reasoning)
            if "metadata" in message:
                with st.expander("🔍 Metadati Esecuzione", expanded=False):
                    metadata = message["metadata"]
                    st.markdown(f"**Agente**: {metadata.get('agent', 'N/A')}")
                    st.markdown(f"**Tool**: {metadata.get('tool', 'N/A')}")
                    st.markdown(f"**Modalità**: {metadata.get('mode', 'N/A')}")
                    st.markdown(f"**Timestamp**: {metadata.get('timestamp', 'N/A')}")
                    if metadata.get('extracted_params'):
                        st.json(metadata['extracted_params'])
                    cache_status = "HIT" if metadata.get('cache_hit') else "MISS"
                    st.markdown(f"**Cache**: {cache_status}")
            
            # Main response (natural language)
            st.markdown(message["content"])
            
            # Artifacts section (if present)
            if "artifacts" in message and message["artifacts"]:
                st.markdown("---")
                st.markdown("**📎 Artifacts Disponibili:**")
                for artifact in message["artifacts"]:
                    if artifact["type"] == "table":
                        with st.expander(f"📊 {artifact['name']}"):
                            st.dataframe(artifact["data"], use_container_width=True)
                    elif artifact["type"] == "link":
                        st.markdown(f"🔗 [{artifact['name']}]({artifact['url']})")
                    elif artifact["type"] == "image":
                        with st.expander(f"🖼️ {artifact['name']}"):
                            st.image(artifact["path"])
        else:
            st.markdown(message["content"])

# Chat input
if prompt := st.chat_input("Interagisci con gli agenti di monitoraggio..."):
    # Add user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)
    
    # Process query with real backend
    with st.chat_message("assistant"):
        metadata_placeholder = st.empty()
        response_placeholder = st.empty()
        artifacts_placeholder = st.empty()
        
        # Get backend client
        backend = get_backend_client()
        
        # Use a container to hold results (avoids nonlocal issues)
        results = {
            "metadata": {},
            "response": "",
            "artifacts": []
        }
        
        try:
            # Define async processing function
            async def process_stream():
                
                async for chunk in backend.process_query_stream(
                    query=prompt,
                    enabled_agents=enabled_agents,
                    llm_tool_calling=llm_tool_calling,
                    llm_summaries=llm_summaries
                ):
                    if chunk["type"] == "metadata":
                        results["metadata"] = chunk["data"]
                        # Display metadata in expander
                        with metadata_placeholder.container():
                            with st.expander("🔍 Metadati Esecuzione", expanded=False):
                                st.markdown(f"**Agente**: {results['metadata']['agent']}")
                                st.markdown(f"**Tool**: {results['metadata']['tool']}")
                                st.markdown(f"**Timestamp**: {results['metadata']['timestamp']}")
                                
                                # Show extracted parameters
                                if results['metadata']['extracted_params']:
                                    st.markdown("**Parametri**:")
                                    for key, value in results['metadata']['extracted_params'].items():
                                        st.markdown(f"- {key}: `{value}`")
                                
                                cache_status = "HIT" if results['metadata']['cache_hit'] else "MISS"
                                st.markdown(f"**Cache**: {cache_status}")
                    
                    elif chunk["type"] == "response_chunk":
                        # Stream response character by character
                        results["response"] += chunk["data"]["text"]
                        response_placeholder.markdown(results["response"] + "▌")
                    
                    elif chunk["type"] == "response_end":
                        # Remove cursor
                        response_placeholder.markdown(results["response"])
                    
                    elif chunk["type"] == "artifacts":
                        results["artifacts"] = chunk["data"]
                    
                    elif chunk["type"] == "error":
                        st.error(chunk["data"]["message"])
                        return
            
            # Run async function
            asyncio.run(process_stream())
            
            # Display artifacts
            if results["artifacts"]:
                with artifacts_placeholder.container():
                    st.markdown("---")
                    st.markdown("**📎 Artifacts Disponibili:**")
                    for artifact in results["artifacts"]:
                        if artifact["type"] == "table":
                            with st.expander(f"📊 {artifact['name']}"):
                                st.dataframe(artifact["data"], use_container_width=True)
                        elif artifact["type"] == "link":
                            st.markdown(f"🔗 [{artifact['name']}]({artifact['url']})")
                        elif artifact["type"] == "image":
                            with st.expander(f"🖼️ {artifact['name']}"):
                                st.image(artifact["path"])
            
            # Store assistant message in session
            st.session_state.messages.append({
                "role": "assistant",
                "content": results["response"],
                "metadata": results["metadata"],
                "artifacts": results["artifacts"]
            })
        
        except Exception as e:
            st.error(f"Errore durante l'elaborazione: {str(e)}")
            st.exception(e)
