"""Vista 9 · Analítica de desempeño (código compartido por Snowflake y Databricks)."""
import time

import altair as alt
import streamlit as st

from ui import encabezado, tabla, tarjeta


@st.cache_data(ttl=300, show_spinner="Calculando indicadores…")
def _cargar(_datos, plataforma):
    t = time.time()
    r = {"norma": tabla(_datos.obs_por_norma()), "clausulas": tabla(_datos.obs_top_clausulas()),
         "seccion": tabla(_datos.obs_por_seccion()), "desempeno": tabla(_datos.desempeno()), "areas": tabla(_datos.areas())}
    return r, round(time.time() - t, 1)


def pagina(datos, plataforma, usuario="demo"):
    d, seg = _cargar(datos, plataforma)
    encabezado("📈 Analítica de desempeño", plataforma, f"consultas en {seg} s · trámites 2023–2026")

    de, ar, no = d["desempeno"], d["areas"], d["norma"]
    concl = de["concluidos"].sum()
    primer = de["aprobados_primer_intento"].sum()
    ciclo = (de["ciclo_promedio_dias"] * de["concluidos"]).sum() / concl if concl else 0
    c = st.columns(4)
    tarjeta(c[0], "Trámites concluidos", int(concl), f"{int(de['aprobados'].sum())} aprobados")
    tarjeta(c[1], "Aprobados al primer intento", f"{100 * primer / concl:.0f}%" if concl else "—", "sin prevención")
    tarjeta(c[2], "Ciclo promedio", f"{ciclo:.0f} días", "del ingreso a la resolución")
    tarjeta(c[3], "Observaciones históricas", int(no["observaciones"].sum()), f"{len(no)} fundamentos distintos")

    t1, t2, t3 = st.tabs(["Prevenciones por norma", "Desempeño por año", "Cuellos de botella por área"])
    with t1:
        izq, der = st.columns([1, 1])
        with izq:
            st.markdown("**Observaciones por norma o fundamento**")
            st.altair_chart(alt.Chart(no).mark_bar(color="#12355B").encode(
                y=alt.Y("norma:N", sort="-x", title=None, axis=alt.Axis(labelLimit=220)), x=alt.X("observaciones:Q", title="Observaciones"),
                tooltip=["norma", "observaciones", "tramites"]).properties(height=320), use_container_width=True)
        with der:
            st.markdown("**Observaciones por sección CTD**")
            se = d["seccion"].head(15)
            st.altair_chart(alt.Chart(se).mark_bar().encode(
                y=alt.Y("seccion_ctd:N", sort="-x", title=None), x=alt.X("observaciones:Q", title="Observaciones"),
                color=alt.Color("modulo:N", title="Módulo", scale=alt.Scale(scheme="tableau10")),
                tooltip=["seccion_ctd", "observaciones"]).properties(height=320), use_container_width=True)
        st.markdown("**Cláusulas más observadas** — dónde conviene reforzar la revisión antes de enviar")
        st.dataframe(d["clausulas"], hide_index=True, use_container_width=True,
                     column_config={"norma": "Norma", "clausula": "Numeral", "seccion_ctd": "Sección CTD",
                                    "area_responsable": "Área", "observaciones": "Observaciones",
                                    "tramites_afectados": "Trámites", "pct_del_total": st.column_config.NumberColumn("% del total", format="%.1f%%")})
    with t2:
        izq, der = st.columns(2)
        with izq:
            st.markdown("**Aprobación al primer intento (%)**")
            st.altair_chart(alt.Chart(de).mark_line(point=True).encode(
                x=alt.X("anio:O", title="Año de ingreso", axis=alt.Axis(labelAngle=0)), y=alt.Y("pct_primer_intento:Q", title="%"),
                color=alt.Color("familia:N", title="Tipo"), tooltip=["anio", "familia", "concluidos", "pct_primer_intento"],
            ).properties(height=280), use_container_width=True)
        with der:
            st.markdown("**Tiempo de ciclo promedio (días)**")
            st.altair_chart(alt.Chart(de).mark_line(point=True).encode(
                x=alt.X("anio:O", title="Año de ingreso", axis=alt.Axis(labelAngle=0)), y=alt.Y("ciclo_promedio_dias:Q", title="Días"),
                color=alt.Color("familia:N", title="Tipo"), tooltip=["anio", "familia", "ciclo_promedio_dias"],
            ).properties(height=280), use_container_width=True)
        st.dataframe(de, hide_index=True, use_container_width=True,
                     column_config={"anio": st.column_config.NumberColumn("Año", format="%d"), "familia": "Tipo",
                                    "concluidos": "Concluidos", "aprobados": "Aprobados",
                                    "aprobados_primer_intento": "1.er intento", "pct_primer_intento": "% 1.er intento",
                                    "con_prevencion": "Con prevención", "negados_o_desechados": "Negados/desechados",
                                    "ciclo_promedio_dias": "Ciclo (días)"})
    with t3:
        st.markdown("**Tareas de respuesta a prevenciones por área**")
        largo = ar.melt(id_vars="area", value_vars=["cerradas", "abiertas", "vencidas"], var_name="estatus", value_name="cantidad")
        st.altair_chart(alt.Chart(largo).mark_bar().encode(
            y=alt.Y("area:N", title=None, axis=alt.Axis(labelLimit=220)), x=alt.X("cantidad:Q", title="Tareas"),
            color=alt.Color("estatus:N", title="Estatus", scale=alt.Scale(domain=["cerradas", "abiertas", "vencidas"],
                                                                          range=["#1e6b42", "#b7791f", "#c0392b"])),
            tooltip=["area", "estatus", "cantidad"]).properties(height=260), use_container_width=True)
        st.dataframe(ar, hide_index=True, use_container_width=True,
                     column_config={"area": "Área", "tareas": "Tareas", "cerradas": "Cerradas", "vencidas": "Vencidas",
                                    "abiertas": "Abiertas", "dias_habiles_promedio_atencion": "Días hábiles promedio",
                                    "pct_cerradas_a_tiempo": st.column_config.NumberColumn("% a tiempo", format="%.1f%%")})
    if st.button("🔄 Actualizar", key="act_analitica"):
        _cargar.clear(); st.rerun()
