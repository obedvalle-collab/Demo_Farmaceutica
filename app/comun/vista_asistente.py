"""Vista 8 · Asistente regulatorio: chat con citas obligatorias (código compartido por Snowflake y Databricks)."""
import pandas as pd
import streamlit as st

from modelo_semantico import PREGUNTAS_EJEMPLO
from ui import encabezado

MOTOR = {"Snowflake": "Cortex Agent (Claude Sonnet 4.5) · Cortex Analyst + Cortex Search",
         "Databricks": "gpt-oss-120b con herramientas · Genie + Vector Search"}


def _mostrar(r):
    st.markdown(r["texto"] or "_(sin respuesta)_")
    for tb in r["tablas"][:2]:
        st.dataframe(pd.DataFrame(tb["filas"], columns=tb["columnas"]), hide_index=True, use_container_width=True)
    if r["fuentes"]:
        st.caption("**Fuentes:** " + " · ".join(f"{'📘' if f['tipo'] == 'norma' else '🗄️'} {f['etiqueta']}" for f in r["fuentes"]))
    with st.expander(f"Cómo lo resolvió · {r['segundos']} s" + (f" · {r['tokens']:,} tokens" if r.get("tokens") else "")):
        for p in r["pasos"]:
            st.markdown(f"- {p}")
        for q in r["sql"]:
            st.code(q, language="sql")


def pagina(datos, plataforma, usuario="demo"):
    nombre = plataforma.split(" · ")[0]
    encabezado("💬 Asistente regulatorio", plataforma, MOTOR.get(nombre, ""))
    st.caption("Responde sobre el expediente, los plazos y las normas. Siempre cita la tabla o la norma y el numeral; "
               "si la información no está, lo dice.")
    if "chat" not in st.session_state:
        st.session_state.chat = []
    sugerida = None
    if not st.session_state.chat:
        cols = st.columns(len(PREGUNTAS_EJEMPLO))
        for c, q in zip(cols, PREGUNTAS_EJEMPLO):
            if c.button(q, use_container_width=True):
                sugerida = q
    for m in st.session_state.chat:
        with st.chat_message("user" if m["rol"] == "user" else "assistant"):
            if m["rol"] == "user":
                st.markdown(m["texto"])
            else:
                _mostrar(m["respuesta"])
    pregunta = st.chat_input("Escribe tu pregunta…") or sugerida
    if pregunta:
        with st.chat_message("user"):
            st.markdown(pregunta)
        with st.chat_message("assistant"):
            with st.spinner("Consultando datos y normas…"):
                historial = [{"rol": m["rol"], "texto": m["texto"]} for m in st.session_state.chat]
                try:
                    r = datos.preguntar(pregunta, historial)
                except Exception as e:
                    st.error(f"El asistente no respondió: {str(e)[:300]}")
                    return
            _mostrar(r)
        st.session_state.chat += [{"rol": "user", "texto": pregunta},
                                  {"rol": "assistant", "texto": r["texto"], "respuesta": r}]
    if st.session_state.chat and st.button("🧹 Nueva conversación"):
        st.session_state.chat = []
        st.rerun()
