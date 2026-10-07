"""Vista 6 · Control de versiones y comparación (código compartido por Snowflake y Databricks)."""
import streamlit as st

from ui import encabezado

VEREDICTO = {"Atiende": ("✅", "#1e6b42"), "Parcial": ("🟡", "#b7791f"), "No atiende": ("❌", "#c0392b")}
ATENDIDA = {"Si": "✅ Sí", "Parcial": "🟡 Parcial", "No": "❌ No"}


def _nombre(archivo):
    return (archivo or "").rsplit("/", 1)[-1]


def _evaluacion(ev, modelo, seg):
    icono, color = VEREDICTO.get(ev["veredicto"], ("•", "#5f6b76"))
    st.markdown(f"""<div style="border-left:8px solid {color};background:#f7f8fa;padding:12px 16px;border-radius:6px">
        <div style="font-size:13px;color:#5f6b76">Veredicto de la IA ({modelo} · {seg} s)</div>
        <div style="font-size:24px;font-weight:700;color:{color}">{icono} {ev['veredicto']}</div>
        <div>{ev['resumen']}</div></div>""", unsafe_allow_html=True)
    for o in ev["observaciones"]:
        st.markdown(f"- **{ATENDIDA.get(o['atendida'], o['atendida'])}** · {o['observacion']}  \n  <span style='color:#5f6b76'>{o['evidencia']}</span>",
                    unsafe_allow_html=True)
    a, b = st.columns(2)
    with a:
        st.markdown("**Cambios detectados**")
        for c in ev["cambios"] or ["—"]:
            st.markdown(f"- {c}")
    with b:
        st.markdown("**Riesgos nuevos**")
        for c in ev["riesgos_nuevos"] or ["Ninguno"]:
            st.markdown(f"- {c}")


def pagina(datos, plataforma, usuario="demo"):
    encabezado("🔀 Control de versiones", plataforma, "qué cambió y si la corrección atiende lo observado")
    pares = datos.pares_versiones()
    if not pares:
        st.info("Aún no hay documentos con más de una versión. Sube una corrección desde la bandeja del Expediente CTD.")
        return
    opciones = {f"{'✅ ' if p['veredicto'] == 'Atiende' else '🟡 ' if p['veredicto'] == 'Parcial' else '❌ ' if p['veredicto'] else '⚪ '}"
                f"{p['tramite_id']} · {p['seccion_ctd']} {p['nombre_requisito']} (v{p['version_anterior']} → v{p['version_nueva']})": p
                for p in pares}
    par = opciones[st.selectbox("Documento corregido", list(opciones))]
    det = datos.detalle_versiones(par)

    izq, der = st.columns(2)
    for col, titulo, archivo, version, cargado, hall in [
            (izq, "Versión anterior", par["archivo_anterior"], par["version_anterior"], par["cargado_anterior"], det["hallazgos_anterior"]),
            (der, "Versión corregida", par["archivo_nuevo"], par["version_nueva"], par["cargado_nuevo"], det["hallazgos_nuevo"])]:
        with col:
            st.markdown(f"#### {titulo} · v{version}")
            st.caption(f"{_nombre(archivo)} · cargada {str(cargado)[:16]}")
            if hall:
                for h in hall:
                    st.error(f"**{h['hallazgo']}** · {h['norma']} {h['clausula']}")
            else:
                st.success("Sin hallazgos de la revisión automática")
    for o in det["observaciones_cofepris"]:
        st.warning(f"📋 Observación de COFEPRIS (oficio {o['numero_oficio']}, punto {o['numero']}): {o['texto']}")

    cambios = datos.campos_cambiados(det["anterior"], det["nuevo"])
    if cambios:
        st.markdown("#### Datos que cambiaron (extraídos por la IA de la bandeja)")
        st.dataframe([{"Dato": k, "Versión anterior": str(a), "Versión corregida": str(n)} for k, a, n in cambios],
                     hide_index=True, use_container_width=True)
    with st.expander("Diferencias de texto (línea por línea)"):
        st.code(datos.diferencias_texto(det["texto_anterior"], det["texto_nuevo"]) or "Sin diferencias de texto", language="diff")

    st.markdown("#### ¿La corrección atiende lo observado?")
    ev = det["evaluacion"]
    if ev:
        _evaluacion(ev["resultado"], ev["modelo"], ev["segundos"])
        st.caption(f"Evaluado el {str(ev['generado_en'])[:16]}")
    if st.button("🤖 Evaluar con IA" if not ev else "🔁 Volver a evaluar", type="primary" if not ev else "secondary"):
        with st.spinner("La IA está comparando ambas versiones contra las observaciones…"):
            r, seg = datos.evaluar_correccion(par, det)
        st.rerun()
