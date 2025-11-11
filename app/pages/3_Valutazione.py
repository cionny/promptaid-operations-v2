"""
Evaluation Page - System quality assessment and feedback
"""

import streamlit as st

st.set_page_config(
    page_title="Valutazione - PromptAId Operations",
    page_icon="📋",
    layout="wide"
)

st.title("Valutazione Sistema")
st.info("📋 Sezione in sviluppo - Valutazione qualità risposte e feedback operatori")

st.markdown("""
### Funzionalità previste:
- Elenco conversazioni passate (filtrabile)
- Valutazione su 3 criteri: Spiegabilità, Usabilità, Accuratezza
- Note aggiuntive in testo libero
- Dashboard statistiche e trend
- Export report valutazioni
""")
