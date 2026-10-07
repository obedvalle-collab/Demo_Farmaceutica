"""Vista 2 · Expediente CTD (código de pantalla compartido por Snowflake y Databricks).

`datos` es un objeto con la misma interfaz en ambas plataformas (ver datos_snowflake.py / datos_databricks.py).
"""
import streamlit as st

MODULOS = {"M1": "Módulo 1 · Administrativo y regional", "M2": "Módulo 2 · Resúmenes", "M3": "Módulo 3 · Calidad",
           "M4": "Módulo 4 · No clínico", "M5": "Módulo 5 · Clínico"}
ICONO = {"Validado": "✅", "Aprobado": "✅", "Enviado": "📤", "Con hallazgos": "⚠️", "Faltante": "❌",
         "En revisión": "🕒", "Borrador": "📝", "Observado": "⚠️"}
PASOS = ["Solicitado", "Preparando paquete", "Esperando confirmación", "Confirmado", "Enviando", "Enviado"]


def _estilo():
    st.markdown("""<style>
      .candado {padding:14px 18px;border-radius:10px;font-size:18px;font-weight:600;text-align:center}
      .bloqueado {background:#fdecea;color:#a12622;border:1px solid #f5c2bd}
      .listo {background:#e8f5ee;color:#1e6b42;border:1px solid #b9dfc9}
      .enviado {background:#eaf1fb;color:#1b4f8c;border:1px solid #bcd3f0}
      .folio {font-size:30px;font-weight:700;color:#1e6b42;letter-spacing:1px}
      .hallazgo {border-left:4px solid #c0392b;background:#fdf3f2;padding:8px 12px;margin:6px 0;border-radius:4px;font-size:14px}
      .paso {display:inline-block;padding:4px 10px;margin:2px;border-radius:12px;font-size:12px;background:#eef1f4;color:#5f6b76}
      .paso.hecho {background:#1e6b42;color:#fff}
      .paso.actual {background:#c99a2e;color:#fff}
    </style>""", unsafe_allow_html=True)


def _candado(c):
    texto = c["candado"]
    clase = {"Listo para envío": "listo", "Bloqueado": "bloqueado"}.get(texto, "enviado")
    icono = {"Listo para envío": "🔓", "Bloqueado": "🔒"}.get(texto, "📤")
    st.markdown(f'<div class="candado {clase}">{icono} {texto}</div>', unsafe_allow_html=True)


def _encabezado(datos, tramite):
    c = datos.candado(tramite)
    st.subheader(f"{c['producto']} · {c['tipo_tramite']}")
    st.caption(f"{tramite} · Homoclave {c['homoclave']}")
    a, b, d, e, f = st.columns([1, 1, 1, 1, 1.6])
    a.metric("Cobertura", f"{float(c['cobertura_pct']):.0f}%")
    b.metric("Validados", f"{int(c['completos'])}/{int(c['requisitos'])}")
    d.metric("Con hallazgos", int(c["con_hallazgos"]))
    e.metric("Faltantes", int(c["faltantes"]))
    with f:
        _candado(c)
    return c


def _arbol(datos, tramite):
    filas = datos.expediente(tramite)
    hallazgos = datos.hallazgos(tramite)
    pestañas = st.tabs([f"{m} ({sum(1 for r in filas if r['modulo'] == m)})" for m in MODULOS])
    for tab, m in zip(pestañas, MODULOS):
        with tab:
            st.caption(MODULOS[m])
            for r in [r for r in filas if r["modulo"] == m]:
                if r["archivo"]:   # hallazgos de la versión vigente del documento
                    h = [x for x in hallazgos if x["archivo"] == r["archivo"]]
                else:              # requisito sin documento: hallazgo de faltante
                    h = [x for x in hallazgos if not x["archivo"] and x["requisito_id"] == r["requisito_id"]]
                etiqueta = (f"{ICONO.get(r['estatus_efectivo'], '•')} **{r['seccion_ctd']}** · {r['nombre_requisito']}"
                            f"{' · v' + str(r['version']) if r['version'] else ''}"
                            f"{' · ' + str(len(h)) + ' hallazgo(s)' if h else ''}")
                with st.expander(etiqueta, expanded=False):
                    st.write(f"Estado: **{r['estatus_efectivo']}** · Área responsable: {r['area_responsable']}")
                    if r["archivo"]:
                        st.caption(f"Archivo: {r['archivo'].split('/')[-1]} · origen: {r['origen']}")
                    for x in h:
                        cita = " · ".join(v for v in [x["norma"], x["clausula"] and f"numeral {x['clausula']}", x["fundamento"]] if v)
                        st.markdown(f'<div class="hallazgo"><b>{x["severidad"]}</b> · {x["hallazgo"]}<br><small>{cita}</small></div>',
                                    unsafe_allow_html=True)
                    if not h and r["estatus_efectivo"] == "Validado":
                        st.success("Revisado por la IA contra la NOM: sin hallazgos.")


def _bandeja(datos, tramite):
    st.markdown("#### 📥 Bandeja de carga inteligente")
    st.caption("Sube un PDF: la IA lo lee, lo ubica en el CTD, extrae sus datos y lo revisa contra la NOM.")
    archivo = st.file_uploader("Documento PDF", type=["pdf"], key=f"subir_{tramite}")
    if archivo and st.button("Procesar documento", type="primary"):
        with st.spinner("Leyendo y revisando el documento (≈ 30–60 s)…"):
            st.session_state[f"ultimo_{tramite}"] = datos.cargar_documento(tramite, archivo.name, archivo.getvalue())
    r = st.session_state.get(f"ultimo_{tramite}")
    if r:
        if r.get("error"):
            st.error(r["error"])
        else:
            st.success(f"Ubicado en **{r['seccion_ctd']} · {r['tipo_documento']}** como versión {r['version']}.")
            if r["hallazgos"]:
                for x in r["hallazgos"]:
                    st.markdown(f'<div class="hallazgo">{x}</div>', unsafe_allow_html=True)
            else:
                st.info("Sin hallazgos: el documento cumple las reglas revisadas.")
            # si la IA lo ubicó mal, la persona lo reubica
            opciones = {f"{x['seccion_ctd']} · {x['nombre_requisito']}": x["requisito_id"] for x in datos.expediente(tramite)}
            actual = next((k for k, v in opciones.items() if v == r["requisito_id"]), list(opciones)[0])
            elegido = st.selectbox("¿Ubicación correcta?", list(opciones), index=list(opciones).index(actual), key=f"reubicar_{tramite}")
            c1, c2 = st.columns(2)
            if opciones[elegido] != r["requisito_id"] and c1.button("Cambiar ubicación"):
                datos.reubicar(tramite, r["archivo"], opciones[elegido])
                st.session_state.pop(f"ultimo_{tramite}", None); st.rerun()
            if c2.button("Listo"):
                st.session_state.pop(f"ultimo_{tramite}", None); st.rerun()


def _envio(datos, tramite, c, usuario):
    st.markdown("#### 📤 Envío a COFEPRIS (portal simulado)")
    env = datos.ultimo_envio(tramite)
    if not env or env["estatus"] == "Cancelado":
        if c["candado"] == "Listo para envío":
            st.write("El expediente está completo y sin hallazgos. Al pulsar **Enviar**, el agente entrará al portal, "
                     "llenará la solicitud y cargará los 5 módulos; **se detendrá antes de firmar** para que confirmes.")
            if st.button("🚀 Enviar a COFEPRIS", type="primary"):
                datos.solicitar_envio(tramite, usuario)
                st.rerun()
        else:
            st.button("🚀 Enviar a COFEPRIS", disabled=True)
            st.caption("El envío se habilita cuando no hay documentos faltantes ni hallazgos abiertos.")
        if env:
            st.caption(f"Último envío cancelado ({env['envio_id'][:8]}).")
        return
    actual = PASOS.index(env["estatus"]) if env["estatus"] in PASOS else -1
    st.markdown("".join(f'<span class="paso {"hecho" if i < actual or env["estatus"] == "Enviado" else "actual" if i == actual else ""}">{p}</span>'
                        for i, p in enumerate(PASOS)), unsafe_allow_html=True)
    if env["estatus"] == "Error":
        st.error(f"El robot reportó un error: {env['error']}")
    if env["estatus"] == "Esperando confirmación":
        st.warning("El agente llenó la solicitud y está detenido antes de **Firmar y enviar**. Revisa lo que ve:")
        img = datos.captura(env["captura"]) if env["captura"] else None
        if img:
            st.image(img, caption="Pantalla del portal vista por el agente", use_container_width=True)
        if env["resumen_agente"]:
            st.info(env["resumen_agente"])
        a, b = st.columns(2)
        if a.button("✅ Confirmar envío", type="primary"):
            datos.confirmar_envio(env["envio_id"], usuario); st.rerun()
        if b.button("✖ Cancelar"):
            datos.cancelar_envio(env["envio_id"], usuario); st.rerun()
    elif env["estatus"] == "Enviado":
        st.success("Solicitud enviada y recibida en el portal.")
        st.markdown(f'<div class="folio">{env["folio"]}</div>', unsafe_allow_html=True)
        st.caption(f"Enviado: {env['enviado_en']} · Cadena de verificación: {env['cadena_acuse']}")
        img = datos.captura(env["captura"]) if env["captura"] else None
        if img:
            with st.expander("Ver acuse en el portal"):
                st.image(img, use_container_width=True)
    else:
        st.info(f"Estado: **{env['estatus']}**. El robot de envío está trabajando…")
    if st.button("🔄 Actualizar estado"):
        st.rerun()


def pagina(datos, plataforma, usuario="demo"):
    _estilo()
    st.title("📁 Expediente CTD")
    st.caption(f"Laboratorios Altamira (ficticio) · Plataforma: **{plataforma}** · Fecha de la demo: 06/10/2026")
    tramites = datos.tramites()
    if not tramites:
        st.warning("No hay expedientes cargados. Ejecuta la preparación de la Fase 5.")
        return
    opciones = {f"{t['producto']} · {t['tramite_id']} · {t['candado']}": t["tramite_id"] for t in tramites}
    tramite = opciones[st.sidebar.selectbox("Trámite", list(opciones))]
    st.sidebar.caption("Datos ficticios. Normas reales (DOF).")
    c = _encabezado(datos, tramite)
    st.divider()
    izq, der = st.columns([1.6, 1])
    with izq:
        _arbol(datos, tramite)
    with der:
        _envio(datos, tramite, c, usuario)
        st.divider()
        _bandeja(datos, tramite)
