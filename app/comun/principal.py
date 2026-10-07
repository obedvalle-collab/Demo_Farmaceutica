"""Navegación de la app: un menú lateral con las vistas construidas (mismo código en ambas plataformas)."""
import streamlit as st

import vista_expediente
import vista_prevenciones

VISTAS = {"📁 Expediente CTD": vista_expediente, "⏱️ Ciclo de prevenciones": vista_prevenciones}


def principal(datos, plataforma, usuario="demo"):
    st.set_page_config(page_title="Laboratorios Altamira · Regulatorio", page_icon="📁", layout="wide")
    vista = st.sidebar.radio("Vista", list(VISTAS), key="vista")
    st.sidebar.divider()
    VISTAS[vista].pagina(datos, plataforma, usuario)
