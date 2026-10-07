"""Vista 5 · Ciclo de prevenciones (código compartido por Snowflake y Databricks)."""
import streamlit as st

COLOR = {"Verde": "#1e6b42", "Amarillo": "#b7791f", "Rojo": "#c0392b", "Vencido": "#6b0f1a"}


def _f(v):
    return str(v)[:10] if v else "—"


def _semaforo(p):
    color = COLOR.get(p["semaforo"], "#5f6b76")
    dias = p["dias_habiles_restantes"]
    st.markdown(f"""<div style="border-left:8px solid {color};background:#f7f8fa;padding:12px 16px;border-radius:6px">
        <div style="font-size:13px;color:#5f6b76">{p['accion_pendiente']} · fecha límite {_f(p['fecha_limite_accion'])}</div>
        <div style="font-size:28px;font-weight:700;color:{color}">{dias} días hábiles · {p['semaforo']}</div></div>""",
                unsafe_allow_html=True)


def _linea_tiempo(p):
    hitos = [("Aviso de COFEPRIS", p["fecha_aviso"]), ("Límite para abrir", p["fecha_limite_apertura"]),
             ("Oficio abierto", p["fecha_apertura"]), ("Surte efectos", p["fecha_surte_efectos"]),
             ("Límite para responder", p["fecha_limite"])]
    cols = st.columns(len(hitos))
    for c, (t, f) in zip(cols, hitos):
        c.markdown(f"<div style='text-align:center;font-size:12px;color:#5f6b76'>{t}</div>"
                   f"<div style='text-align:center;font-weight:600'>{'●' if f else '○'} {_f(f)}</div>", unsafe_allow_html=True)


def _detalle(datos, p, usuario):
    if p["accion_pendiente"] == "Abrir oficio":
        if p["estatus_aviso"] == "Nuevo":
            st.warning("COFEPRIS dejó un acto en el portal. **Al abrirlo empieza a correr el plazo** (surte efectos el día hábil "
                       "siguiente). Ábrelo cuando el equipo esté listo para atenderlo.")
            if st.button("📂 Abrir oficio en el portal", type="primary", key=f"abrir_{p['aviso_id']}"):
                datos.solicitar_apertura(p["tramite_id"], p["aviso_id"], usuario); st.rerun()
        else:
            st.info("El robot está abriendo y descargando el oficio; la IA lo analizará en cuanto llegue (≈ 1–2 min).")
        return
    d = datos.detalle_oficio(p["oficio_id"])
    st.markdown(f"#### Oficio {p['numero_oficio']} · {len(d['observaciones'])} observaciones · plazo {p['plazo_dias_habiles']} días hábiles")
    t1, t2, t3 = st.tabs(["Observaciones", f"Tareas ({p['tareas_cerradas']}/{p['tareas']})", "Borrador de respuesta"])
    with t1:
        for o in d["observaciones"]:
            cita = " · ".join(x for x in [o["norma"], o["clausula"] and f"numeral {o['clausula']}"] if x)
            with st.expander(f"**{o['numero']}.** {o['texto'][:110]}…", expanded=False):
                st.write(o["texto"])
                st.caption(f"Fundamento: {cita or '—'} · Sección CTD {o['seccion_ctd'] or '—'} · Área: {o['area_responsable']}")
                if o["texto_clausula"]:
                    st.markdown(f"> **Texto de la norma ({cita})**: {o['texto_clausula']}")
    with t2:
        for t in d["tareas"]:
            a, b, c, e = st.columns([3, 1.4, 1, 0.8])
            a.write(f"**{t['numero']}.** {t['descripcion']}")
            b.caption(f"{t['responsable']} · {t['area']}")
            c.caption(f"Compromiso {_f(t['fecha_compromiso'])}")
            if t["estatus"] == "Cerrada":
                e.success("Cerrada")
            elif e.button("Cerrar", key=f"cerrar_{t['tarea_id']}"):
                datos.cerrar_tarea(t["tarea_id"]); st.rerun()
    with t3:
        st.caption("Redactado por la IA con las observaciones y el texto de las cláusulas. Revísalo y edítalo antes de firmar.")
        texto = st.text_area("Borrador", d["borrador"], height=420, key=f"borrador_{p['oficio_id']}", label_visibility="collapsed")
        a, b = st.columns(2)
        if a.button("💾 Guardar cambios", key=f"guardar_{p['oficio_id']}"):
            datos.guardar_borrador(p["oficio_id"], texto); st.success("Borrador guardado")
        b.download_button("⬇️ Descargar (.md)", texto, file_name=f"respuesta_{p['numero_oficio'] or 'oficio'}.md".replace("/", "-"))


def pagina(datos, plataforma, usuario="demo"):
    st.title("⏱️ Ciclo de prevenciones")
    st.caption(f"Laboratorios Altamira (ficticio) · Plataforma: **{plataforma}** · Fecha de la demo: 06/10/2026")
    vivas = datos.prevenciones()
    if not vivas:
        st.info("No hay avisos de COFEPRIS en curso. Cuando el portal emita una prevención, el vigía la detectará, "
                "llegará una alerta a tu correo y aparecerá aquí.")
    else:
        opciones = {f"{p['producto']} · folio {p['folio']} · {p['accion_pendiente']}": p for p in vivas}
        p = opciones[st.selectbox("Prevención", list(opciones))]
        st.subheader(f"{p['producto']} · {p['tipo_tramite']}")
        st.caption(f"{p['tramite_id']} · folio {p['folio']}")
        izq, der = st.columns([1, 2])
        with izq:
            _semaforo(p)
        with der:
            _linea_tiempo(p)
        st.divider()
        _detalle(datos, p, usuario)
        with st.expander("📧 Alertas enviadas por correo"):
            for a in datos.alertas_enviadas(p["tramite_id"]):
                st.write(f"{'✅' if a['enviada_en'] else '🕒'} {a['asunto']} · {_f(a['creada_en'])} · {a['canal'] or 'pendiente'}")
            if st.button("Revisar plazos y enviar recordatorios"):
                n = datos.generar_recordatorios()
                st.success(f"{n} recordatorio(s) nuevos · {datos.enviar_correos()} correo(s) enviados")
    if st.button("🔄 Actualizar"):
        st.rerun()
