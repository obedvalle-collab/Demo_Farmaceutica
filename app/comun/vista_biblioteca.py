"""Vista 7 · Biblioteca normativa: NOM reales por cláusula y buscador semántico (código compartido)."""
import time

import streamlit as st

from ui import encabezado, tabla

EJEMPLOS = ["estabilidad acelerada", "leyendas obligatorias de la etiqueta", "intervalo de confianza de bioequivalencia",
            "plan de manejo de riesgos", "validación de métodos analíticos", "prórroga del registro sanitario"]
TIPO = {"NOM": "Norma vigente", "PROY-NOM": "Proyecto de norma", "MODIFICACION": "Modificación publicada",
        "LEY": "Ley", "REGLAMENTO": "Reglamento", "GUIA": "Guía ICH"}


@st.cache_data(ttl=3600, show_spinner=False)
def _catalogo(_datos, plataforma):
    return tabla(_datos.catalogo_normas())


def _resultado(datos, r, i):
    proyecto = r["estatus"] != "Vigente"
    etiqueta = f"**{r['norma']} · {r['numeral']}** — {r['titulo'] or ''}"
    with st.expander(("🟠 " if proyecto else "") + etiqueta, expanded=i == 0):
        if proyecto:
            st.warning("Esta cláusula es de un **proyecto de norma** (aún no vigente).")
        c = datos.clausula(r["clausula_id"])
        if not c:
            st.write(r["texto_busqueda"]); return
        st.caption(f"{c['titulo_norma']} · {TIPO.get(c['tipo'], c['tipo'])}" + (f" · {c['contexto']}" if c["contexto"] else ""))
        st.write(c["texto"])
        for h in c["hijas"][:12]:
            st.markdown(f"- **{h['numeral']}** {h['texto'][:400]}")
        if c["modificada_por"]:
            st.info(f"✏️ Este numeral fue modificado por **{c['modificada_por']}**.")
        for rel in c["relacionadas"]:
            aviso = "📣 Mismo numeral en el proyecto de norma (la numeración puede cambiar)" if rel["tipo"] == "PROY-NOM" else \
                    "✏️ Versión modificada" if rel["tipo"] == "MODIFICACION" else "📘 Versión vigente de este numeral"
            st.markdown(f"**{aviso}: {rel['norma']} {rel['numeral']}** ({str(rel['fecha_dof'])[:10]})")
            st.markdown(f"> {rel['texto'][:1200]}")


def pagina(datos, plataforma, usuario="demo"):
    encabezado("📚 Biblioteca normativa", plataforma, "NOM reales del DOF, partidas por cláusula")
    cat = _catalogo(datos, plataforma)
    izq, der = st.columns([2.2, 1])
    with der:
        st.markdown("#### Normas cargadas")
        st.caption(f"{len(cat)} documentos · {int(cat['clausulas'].sum()):,} cláusulas")
        st.dataframe(cat[["norma", "tipo", "estatus", "fecha_dof", "clausulas"]], hide_index=True, use_container_width=True,
                     height=420, column_config={"norma": "Norma", "tipo": "Tipo", "estatus": "Estatus",
                                                "fecha_dof": "DOF", "clausulas": "Cláusulas"})
        proy = cat[cat["tipo"] == "PROY-NOM"]
        if len(proy):
            st.markdown("**📣 Proyectos de norma en consulta**")
            for _, p in proy.iterrows():
                st.caption(f"{p['norma']} → actualizaría {p['norma_relacionada']} (DOF {str(p['fecha_dof'])[:10]})")
    with izq:
        st.markdown("#### Buscar en las normas")
        if "consulta_normas" not in st.session_state:
            st.session_state.consulta_normas = EJEMPLOS[0]
        cols = st.columns(3)
        for k, e in enumerate(EJEMPLOS):
            if cols[k % 3].button(e, key=f"ej_{k}", use_container_width=True):
                st.session_state.consulta_normas = e
        texto = st.text_input("Pregunta o tema", key="consulta_normas", placeholder="¿Qué buscas en las normas?")
        a, b = st.columns([1, 1])
        solo = a.toggle("Solo normas vigentes", value=True, help="Apágalo para incluir los proyectos de norma (PROY-NOM)")
        normas = ["Todas"] + sorted(cat["norma"].tolist())
        norma = b.selectbox("Norma", normas, label_visibility="collapsed")
        if texto:
            t = time.time()
            try:
                res = datos.buscar_normas(texto, solo, None if norma == "Todas" else norma)
            except Exception as e:
                st.error(f"El buscador no respondió: {str(e)[:300]}")
                st.caption("En Databricks el buscador (Vector Search) se apaga al cerrar cada sesión para no generar costo.")
                return
            st.caption(f"{len(res)} cláusulas · respuesta del buscador en {round(time.time() - t, 2)} s")
            for i, r in enumerate(res):
                _resultado(datos, r, i)
