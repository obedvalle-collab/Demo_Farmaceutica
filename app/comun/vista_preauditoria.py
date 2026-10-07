"""Vista 4 · Pre-auditoría ("simulador COFEPRIS") (código compartido por Snowflake y Databricks)."""
import streamlit as st

from ui import SEMAFORO, encabezado

RIESGO = {"Alto": SEMAFORO["Rojo"], "Medio": SEMAFORO["Amarillo"], "Bajo": SEMAFORO["Verde"]}
PROB = {"Alta": "🔴 Alta", "Media": "🟡 Media", "Baja": "🟢 Baja"}


def _resultado(p):
    r = p["resultado"]
    color = RIESGO.get(r["riesgo"], "#5f6b76")
    st.markdown(f"""<div style="border-left:8px solid {color};background:#f7f8fa;padding:12px 16px;border-radius:6px">
        <div style="font-size:13px;color:#5f6b76">Riesgo de prevención · {p['modelo']} · {p['segundos']} s · {str(p['generado_en'])[:16]}</div>
        <div style="font-size:28px;font-weight:700;color:{color}">{r['riesgo']}</div>
        <div>{r['resumen']}</div></div>""", unsafe_allow_html=True)
    st.markdown(f"#### {len(r['prevenciones'])} prevenciones probables")
    for i, x in enumerate(r["prevenciones"], 1):
        with st.expander(f"{PROB.get(x['probabilidad'], x['probabilidad'])} · **{x['seccion_ctd']}** {x['observacion'][:120]}",
                         expanded=i <= 2):
            st.write(x["observacion"])
            st.caption(f"Fundamento: {x['norma']} numeral {x['clausula']} · Requisito: {x['requisito']}")
            st.markdown(f"**Por qué:** {x['motivo']}")
            st.markdown(f"**Qué hacer antes de enviar:** {x['recomendacion']}")


def pagina(datos, plataforma, usuario="demo"):
    encabezado("🕵️ Pre-auditoría", plataforma, "la IA actúa como dictaminador antes del envío")
    st.caption("Combina el expediente (documentos y datos extraídos), los hallazgos de la revisión automática y el historial "
               "de observaciones de trámites parecidos. Cita la norma y el numeral de cada posible prevención.")
    tramites = datos.tramites_preauditables()
    opciones = {f"{t['tramite_id']} · {t['producto']} · {t['candado']}"
                + (f" · riesgo {t['riesgo']}" if t["riesgo"] else ""): t for t in tramites}
    t = opciones[st.selectbox("Trámite", list(opciones))]
    c = st.columns(3)
    c[0].metric("Requisitos", t["requisitos"])
    c[1].metric("Con hallazgos", t["con_hallazgos"])
    c[2].metric("Faltantes", t["faltantes"])
    previa = datos.ultima_preauditoria(t["tramite_id"])
    if st.button("🕵️ Ejecutar pre-auditoría" if not previa else "🔁 Ejecutar de nuevo", type="primary" if not previa else "secondary"):
        with st.spinner("El dictaminador virtual está revisando el expediente (≈ 20–60 s)…"):
            datos.preauditar(t["tramite_id"], usuario)
        st.rerun()
    if previa:
        _resultado(previa)
    else:
        st.info("Aún no hay pre-auditoría para este trámite.")
