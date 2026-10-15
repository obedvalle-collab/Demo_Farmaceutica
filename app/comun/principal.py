"""Navegación de la app: un menú lateral con las vistas construidas (mismo código en ambas plataformas)."""
import streamlit as st

import vista_analitica
import vista_asistente
import vista_biblioteca
import vista_expediente
import vista_gobierno
import vista_portafolio
import vista_preauditoria
import vista_prevenciones
import vista_versiones

# en el orden del plan (PLAN.md §3); la bandeja de carga (Vista 3) vive dentro del Expediente CTD
VISTAS = {"📊 Portafolio": vista_portafolio, "📁 Expediente CTD": vista_expediente,
          "🕵️ Pre-auditoría": vista_preauditoria, "⏱️ Ciclo de prevenciones": vista_prevenciones,
          "🔀 Versiones": vista_versiones, "📚 Biblioteca normativa": vista_biblioteca, "💬 Asistente": vista_asistente,
          "📈 Analítica": vista_analitica,
          "🛡️ Gobierno y bitácora": vista_gobierno}


def principal(datos, plataforma, usuario="demo"):
    st.set_page_config(page_title="Laboratorios Altamira · Regulatorio", page_icon="📁", layout="wide")
    vista = st.sidebar.radio("Vista", list(VISTAS), key="vista")
    with st.sidebar.popover("🔄 Reiniciar demo"):
        st.write("Borra envíos, prevenciones, alertas, pre-auditorías y evaluaciones, y regresa el expediente a su versión "
                 "inicial. El robot vacía también el portal simulado en cuanto ve la orden (debe estar encendido).")
        if st.button("Sí, reiniciar", type="primary"):
            datos.reiniciar_demo()
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()
    st.sidebar.divider()
    VISTAS[vista].pagina(datos, plataforma, usuario)
