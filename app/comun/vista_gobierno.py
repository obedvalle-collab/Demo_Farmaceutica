"""Vista 10 · Gobierno y bitácora (código compartido por Snowflake y Databricks)."""
import time

import pandas as pd
import streamlit as st

from ui import SEMAFORO, encabezado, tabla, tarjeta

# Qué puede hacer cada rol en la app (demo). La plataforma aplica además sus propios permisos (pestaña 4).
PERMISOS = {
    "Cargar documentos": ["Especialista de Asuntos Regulatorios", "Gerente de Asuntos Regulatorios", "Especialista CMC",
                          "Especialista Clínico", "Analista de Calidad", "Responsable de Farmacovigilancia"],
    "Aprobar documentos": ["Gerente de Asuntos Regulatorios", "Gerente de Aseguramiento de Calidad", "Responsable Sanitario",
                           "Gerente Médico"],
    "Enviar a COFEPRIS (confirmar firma)": ["Representante Legal", "Director(a) de Asuntos Regulatorios"],
    "Abrir oficios de prevención": ["Gerente de Asuntos Regulatorios", "Director(a) de Asuntos Regulatorios"],
    "Editar borrador de respuesta": ["Especialista de Asuntos Regulatorios", "Gerente de Asuntos Regulatorios"],
    "Ejecutar pre-auditoría / evaluar versiones": ["Especialista de Asuntos Regulatorios", "Gerente de Asuntos Regulatorios",
                                                   "Gerente de Aseguramiento de Calidad"],
    "Ver tablero y analítica": ["*"],
}


def _alcoa(datos):
    filas = tabla(datos.alcoa())
    st.markdown("Principios **ALCOA+** de integridad de datos revisados automáticamente sobre la bitácora (cada versión de un "
                "documento se identifica por su huella digital SHA-256).")
    for _, r in filas.iterrows():
        ok = r["incidencias"] == 0
        pct = 100 * (1 - r["incidencias"] / r["revisados"]) if r["revisados"] else 100
        a, b, c = st.columns([1.2, 4, 1.6])
        a.markdown(f"{'✅' if ok else '⚠️'} **{r['principio']}**")
        b.write(r["control"])
        c.markdown(f"<span style='color:{SEMAFORO['Verde'] if ok else SEMAFORO['Amarillo']}'>"
                   f"{int(r['incidencias'])} de {int(r['revisados']):,} · {pct:.1f}% ok</span>", unsafe_allow_html=True)
    st.caption("Las incidencias de segregación de funciones (quien aprueba también cargó) son un hallazgo de auditoría típico; "
               "las versiones sin aprobación corresponden a documentos aún en revisión.")


def _permisos(datos):
    usuarios = tabla(datos.usuarios())
    roles = sorted(usuarios["rol"].unique())
    matriz = pd.DataFrame([{"Acción": accion, **{r: ("✅" if "*" in quien or r in quien else "") for r in roles}}
                           for accion, quien in PERMISOS.items()])
    st.markdown("**Permisos por rol en la app**")
    st.dataframe(matriz, hide_index=True, use_container_width=True)
    st.markdown("**Personal (ficticio)**")
    st.dataframe(usuarios, hide_index=True, use_container_width=True,
                 column_config={"usuario_id": "ID", "titulo": "Título", "nombre": "Nombre", "rol": "Rol", "area": "Área",
                                "activo": "Activo"})


def _plataforma(datos, plataforma):
    t = time.time()
    try:
        a = datos.auditoria_plataforma()
    except Exception as e:
        st.warning(f"La identidad de la app no tiene acceso a la auditoría de la plataforma: {str(e)[:250]}")
        return
    st.caption(f"Fuente: {a['fuente']} · {round(time.time() - t, 1)} s · solo objetos de esta demo")
    izq, der = st.columns([1, 1])
    with izq:
        st.markdown("**Permisos sobre los datos (los aplica la plataforma)**")
        st.dataframe(pd.DataFrame(a["permisos"]), hide_index=True, use_container_width=True, height=300)
    with der:
        st.markdown("**Tablas más leídas (últimos 3 días)**")
        st.dataframe(tabla(a["accesos"]), hide_index=True, use_container_width=True, height=300)
    st.markdown("**Consultas recientes sobre la demo (quién, qué y cuánto tardó)**")
    act = tabla(a["actividad"])
    if len(act):
        act["sentencia"] = act["sentencia"].astype(str).str.replace(r"\s+", " ", regex=True).str[:140]
    st.dataframe(act, hide_index=True, use_container_width=True, height=320)
    st.caption("Las vistas de auditoría de la plataforma se actualizan con retraso (minutos a horas).")


def pagina(datos, plataforma, usuario="demo"):
    encabezado("🛡️ Gobierno y bitácora", plataforma, "trazabilidad, integridad de datos y permisos")
    res = tabla(datos.bitacora_resumen())
    c = st.columns(4)
    tarjeta(c[0], "Eventos en bitácora", f"{int(res['eventos'].sum()):,}", "histórico + app")
    tarjeta(c[1], "Eventos de la app", int(res[res["origen"] == "App"]["eventos"].sum()), "cargas, envíos, IA, alertas")
    tarjeta(c[2], "Acciones de IA y agentes",
            int(res[res["accion"].isin(["Oficio analizado", "Evaluación de corrección", "Envío a COFEPRIS",
                                        "Aviso de prevención detectado", "Alerta enviada por correo"]) & (res["origen"] == "App")]["eventos"].sum()),
            "todas quedan registradas")
    tarjeta(c[3], "Usuario actual", usuario, plataforma.split(" · ")[0])

    t1, t2, t3, t4 = st.tabs(["Bitácora", "Integridad (ALCOA+)", "Roles y permisos", f"Auditoría de {plataforma.split(' · ')[0]}"])
    with t1:
        a, b = st.columns(2)
        origen = a.selectbox("Origen", ["Todos", "App", "Histórico"])
        tramite = b.text_input("Trámite", placeholder="TR-2026-032")
        bit = tabla(datos.bitacora(tramite.strip() or None, None if origen == "Todos" else origen))
        st.dataframe(bit, hide_index=True, use_container_width=True, height=460,
                     column_config={"fecha_hora": st.column_config.DatetimeColumn("Fecha y hora", format="YYYY-MM-DD HH:mm"),
                                    "origen": "Origen", "usuario": "Quién", "rol": "Rol", "accion": "Acción",
                                    "tramite_id": "Trámite", "objeto": "Objeto", "detalle": "Detalle", "sha256": "Huella / acuse"})
        st.download_button("⬇️ Exportar bitácora (CSV)", bit.to_csv(index=False).encode("utf-8"), "bitacora.csv", "text/csv")
    with t2:
        _alcoa(datos)
    with t3:
        _permisos(datos)
    with t4:
        _plataforma(datos, plataforma)
