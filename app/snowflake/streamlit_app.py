"""Entrada de la app en Streamlit in Snowflake (también corre local: streamlit run app/snowflake/streamlit_app.py)."""
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
for p in (AQUI, AQUI.parent / "comun", AQUI.parents[1] / "compartido"):
    if p.exists():
        sys.path.insert(0, str(p))

from datos_snowflake import DatosSnowflake  # noqa: E402
from vista_expediente import pagina  # noqa: E402


def sesion():
    try:
        from snowflake.snowpark.context import get_active_session
        return get_active_session()
    except Exception:   # ejecución local para pruebas
        from snowflake.snowpark import Session
        import streamlit as st
        if "sesion_local" not in st.session_state:
            st.session_state.sesion_local = Session.builder.config("connection_name", "obed_farma").create()
        return st.session_state.sesion_local


s = sesion()
try:
    usuario = s.sql("SELECT CURRENT_USER()").collect()[0][0]
except Exception:
    usuario = "demo"
pagina(DatosSnowflake(s), "Snowflake · Streamlit in Snowflake", usuario)
