"""Vista 1 · Portafolio: tablero ejecutivo (código compartido por Snowflake y Databricks)."""
import time

import altair as alt
import streamlit as st

from ui import ICONO, SEMAFORO, encabezado, tabla, tarjeta


@st.cache_data(ttl=300, show_spinner="Consultando el portafolio…")
def _cargar(_datos, plataforma):
    t = time.time()
    p, r = tabla(_datos.portafolio()), tabla(_datos.registros_vigencia())
    return p, r, round(time.time() - t, 1)


def pagina(datos, plataforma, usuario="demo"):
    p, r, seg = _cargar(datos, plataforma)
    encabezado("📊 Portafolio", plataforma, f"consultas en {seg} s")

    en_cofepris = p[p["fecha_ingreso"].notna()]
    prev = p[p["semaforo_prevencion"].isin(["Verde", "Amarillo", "Rojo", "Vencido"])]
    urgentes = prev[prev["semaforo_prevencion"].isin(["Rojo", "Vencido"])]
    renovar = r[r["semaforo"].isin(["Rojo", "Amarillo"])]
    c = st.columns(4)
    tarjeta(c[0], "Trámites activos", len(p), f"{len(p) - len(en_cofepris)} en integración")
    tarjeta(c[1], "En COFEPRIS", len(en_cofepris),
            f"{int(en_cofepris['dias_en_cofepris'].mean()) if len(en_cofepris) else 0} días en promedio")
    tarjeta(c[2], "Prevenciones abiertas", len(prev), f"{len(urgentes)} en rojo o vencidas",
            SEMAFORO["Rojo"] if len(urgentes) else SEMAFORO["Amarillo"] if len(prev) else "#12355B")
    tarjeta(c[3], "Registros por renovar", len(renovar), "prórroga en ≤ 90 días",
            SEMAFORO["Rojo"] if (renovar["semaforo"] == "Rojo").any() else "#12355B")

    st.markdown("#### Trámites activos")
    vista = p.assign(semaforo=p["semaforo_prevencion"].map(lambda s: f"{ICONO.get(s, '')} {s}"))
    st.dataframe(
        vista[["semaforo", "tramite_id", "producto", "familia", "etapa", "estatus", "dias_en_cofepris",
               "cobertura_pct", "accion_pendiente", "fecha_limite_accion", "dias_habiles_restantes"]],
        hide_index=True, use_container_width=True,
        column_config={
            "semaforo": "Prevención", "tramite_id": "Trámite", "producto": "Producto", "familia": "Tipo",
            "etapa": "Etapa", "estatus": "Estatus", "dias_en_cofepris": st.column_config.NumberColumn("Días en COFEPRIS"),
            "cobertura_pct": st.column_config.ProgressColumn("Cobertura CTD", format="%.0f%%", min_value=0, max_value=100),
            "accion_pendiente": "Acción pendiente", "fecha_limite_accion": "Fecha límite",
            "dias_habiles_restantes": st.column_config.NumberColumn("Días hábiles"),
        })

    izq, der = st.columns(2)
    with izq:
        st.markdown("#### Trámites por etapa")
        g = p.groupby(["etapa", "familia"]).size().reset_index(name="tramites")
        st.altair_chart(alt.Chart(g).mark_bar().encode(
            y=alt.Y("etapa:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)), x=alt.X("tramites:Q", title="Trámites"),
            color=alt.Color("familia:N", title="Tipo", scale=alt.Scale(scheme="tableau10")),
            tooltip=["etapa", "familia", "tramites"]).properties(height=260), use_container_width=True)
    with der:
        st.markdown("#### Días en COFEPRIS contra el plazo legal")
        if len(en_cofepris):
            e = en_cofepris.assign(etiqueta=en_cofepris["producto"] + " · " + en_cofepris["tramite_id"])
            st.altair_chart(alt.Chart(e).mark_bar(color="#2f6690").encode(
                y=alt.Y("etiqueta:N", title=None, sort="-x", axis=alt.Axis(labelLimit=260)), x=alt.X("dias_en_cofepris:Q", title="Días naturales"),
                tooltip=["tramite_id", "producto", "dias_en_cofepris", "plazo_resolucion_dias", "tipo_plazo"],
            ).properties(height=260), use_container_width=True)
            st.caption("Plazo de resolución por tipo de trámite en la columna emergente (pase el cursor).")

    st.markdown("#### Vigencia de registros sanitarios (5 años; prórroga 150 días antes)")
    rv = r.assign(semaforo=r["semaforo"].map(lambda s: f"{ICONO.get(s, '')} {s}"))
    st.dataframe(rv[["semaforo", "producto", "registro_sanitario", "fecha_vencimiento_registro",
                     "fecha_limite_solicitar_prorroga", "dias_para_limite_prorroga", "estatus_vigencia", "prorroga_en_tramite"]],
                 hide_index=True, use_container_width=True,
                 column_config={"semaforo": "Semáforo", "producto": "Producto", "registro_sanitario": "Registro",
                                "fecha_vencimiento_registro": "Vence", "fecha_limite_solicitar_prorroga": "Pedir prórroga antes de",
                                "dias_para_limite_prorroga": st.column_config.NumberColumn("Días restantes"),
                                "estatus_vigencia": "Estatus", "prorroga_en_tramite": "Trámite de prórroga"})
    if st.button("🔄 Actualizar", key="act_portafolio"):
        _cargar.clear(); st.rerun()
