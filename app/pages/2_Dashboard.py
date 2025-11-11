"""
Dashboard Page - Geographic visualization and monitoring
"""

import streamlit as st

st.set_page_config(
    page_title="Dashboard - PromptAId Operations",
    page_icon="🗺️",
    layout="wide"
)

st.title("Dashboard")
st.info("📊 Sezione in sviluppo - Visualizzazione geografica stazioni e metriche operative")

st.markdown("""
### Funzionalità previste:
- Mappa interattiva Liguria con stazioni monitorate
- Grafici serie temporali (livelli, precipitazioni)
- Filtri geografici avanzati
- Tabelle dati stazioni OMIRL
- Metadati repository RAG
- Stato viabilità
""")
