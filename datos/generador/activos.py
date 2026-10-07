"""Trámites activos de la demo, sus documentos PDF y los defectos sembrados a propósito.

Este archivo es la "hoja de respuestas": lo usan gen_tablas.py (para que las tablas cuadren con los
PDF) y gen_pdfs.py (para dibujar cada documento con o sin defecto).
"""
from datetime import date

# Cada documento: requisito, plantilla de PDF, si va escaneado, y la lista de defectos que lleva.
# Un defecto con plantilla None significa "documento faltante".


def doc(req, plantilla, escaneado=False, defectos=(), estatus=None, **extra):
    return dict(requisito_id=req, plantilla=plantilla, escaneado=escaneado,
                defectos=list(defectos), estatus=estatus, extra=extra)


def defecto(tipo, descripcion, norma, clausula, fundamento=None, como_detectar=""):
    return dict(tipo=tipo, descripcion=descripcion, norma=norma, clausula=clausula,
                fundamento=fundamento, como_detectar=como_detectar)


ACTIVOS = [
    # ------------------------------------------------------------------------------------
    # A1 · Sitagliptina: expediente en integración (protagonista de la carga inteligente y
    # de la pre-auditoría). Todos los requisitos tienen PDF, salvo el documento IMPI.
    # ------------------------------------------------------------------------------------
    dict(clave="A1", producto_id="P09", tipo="REG_GEN", etapa="Integración del expediente",
         estatus="Borrador", fecha_inicio=date(2026, 7, 15), fecha_ingreso=None,
         fecha_objetivo_envio=date(2026, 10, 30),
         documentos=[
             doc("R001", "solicitud"),
             doc("R002", "pago_derechos", escaneado=True),
             doc("R003", "licencia_sanitaria", escaneado=True),
             doc("R004", "carta_poder", escaneado=True, firma_otorgante=False, defectos=[
                 defecto("Firma faltante", "El instrumento de representación legal no está firmado por el otorgante.",
                         None, None, "LFPA art. 19", "Revisar el bloque de firmas: el espacio del otorgante está vacío.")]),
             doc("R005", "etiqueta_primaria"),
             doc("R006", "etiqueta_secundaria", omitir=["receta", "venta_fraccionada"], defectos=[
                 defecto("Leyenda faltante", "Falta la leyenda \"Su venta requiere receta médica\".",
                         "NOM-072-SSA1-2012", "6.1.4", None, "Buscar la leyenda en todas las caras de la etiqueta."),
                 defecto("Leyenda faltante", "Falta la leyenda \"prohibida la venta fraccionada del producto\" (tratamiento crónico).",
                         "NOM-072-SSA1-2012", "5.19", None, "Producto para diabetes tipo 2 (crónico-degenerativa): la leyenda es obligatoria.")]),
             doc("R007", "ipp_amplia"),
             doc("R008", "ipp_reducida"),
             doc("R009", None, estatus="Faltante", defectos=[
                 defecto("Documento faltante", "No existe el documento IMPI de titularidad de patentes o licencia de explotación.",
                         None, None, "RIS art. 167 fr. I Bis (reforma DOF 24/04/2026)",
                         "El espacio CTD 1.5.1 está vacío; requisito nuevo desde abril de 2026.")]),
             doc("R010", "pmr", omitir_minimizacion=True, defectos=[
                 defecto("Sección faltante", "El plan de manejo de riesgos no incluye el plan de minimización de riesgos.",
                         "NOM-220-SSA1-2016", "8.4.3.1.4", None, "El índice salta de 'Plan de farmacovigilancia' a 'Anexos'.")]),
             doc("R011", "certificado_bpf_medicamento"),
             doc("R012", "certificado_bpf_farmaco", fecha_emision=date(2023, 11, 15), defectos=[
                 defecto("Vigencia vencida", "El certificado de BPF del fármaco se emitió el 15/11/2023; con vigencia de 30 meses venció el 15/05/2026.",
                         "NOM-164-SSA1-2015", None, "RIS art. 167 fr. VI (vigencia de 30 meses)",
                         "Calcular fecha de emisión + 30 meses y comparar con la fecha de envío.")]),
             doc("R020", "resumen_calidad"),
             doc("R030", "info_general_farmaco"),
             doc("R031", "fabricacion_farmaco"),
             doc("R032", "coa_farmaco", fabricante_distinto=True, defectos=[
                 defecto("Inconsistencia entre documentos", "El certificado de análisis del fármaco lo emite un fabricante distinto al declarado en 3.2.S.2 y en el certificado de BPF.",
                         "NOM-164-SSA1-2015", "11", None, "Cruzar el nombre del fabricante con 3.2.S.2 y con el certificado de BPF del fármaco.")]),
             doc("R033", "estabilidad_farmaco"),
             doc("R034", "composicion"),
             doc("R035", "validacion_proceso"),
             doc("R036", "validacion_limpieza"),
             doc("R037", "coa_lote", disolucion_fuera=True, defectos=[
                 defecto("Resultado fuera de especificación", "La disolución reporta 76% (especificación Q = 80% a 30 min) y el dictamen dice \"Cumple\".",
                         "NOM-059-SSA1-2015", "5.5.1", None, "Comparar resultado contra especificación en la tabla de pruebas.")]),
             doc("R038", "validacion_metodos"),
             doc("R039", "contenedor_cierre"),
             doc("R040", "estabilidad", lotes=2, firma_rs=False, defectos=[
                 defecto("Requisito técnico incumplido", "El estudio de estabilidad se realizó con 2 lotes; se requieren al menos 3.",
                         "NOM-073-SSA1-2015", "8.1", None, "Contar los lotes en la tabla de lotes del estudio."),
                 defecto("Firma faltante", "El informe de estabilidad no está avalado (firmado) por el responsable sanitario.",
                         "NOM-073-SSA1-2015", "10.19", None, "Revisar la sección de aprobaciones al final del informe.")]),
             doc("R060", "bioequivalencia", ic_cmax=(91.24, 127.63), defectos=[
                 defecto("Conclusión no sustentada", "El IC 90% de Cmáx (91.24–127.63%) excede el límite de 125% y aun así se concluye bioequivalencia.",
                         "NOM-177-SSA1-2013", "9.6.4", None, "Comparar los límites del IC 90% con el rango 80–125%.")]),
             doc("R061", "perfiles_disolucion", f2=(63.4, 58.9, 61.2)),
             doc("R062", "autorizacion_tercero", escaneado=True),
         ]),
    # ------------------------------------------------------------------------------------
    # A2 · Adalimumab biocomparable: sometido, prevención abierta y en atención.
    # ------------------------------------------------------------------------------------
    dict(clave="A2", producto_id="P10", tipo="REG_BIO", etapa="Prevención – respuesta en preparación",
         estatus="Prevenido", fecha_ingreso=date(2026, 6, 17),
         prevencion=dict(fecha_emision=date(2026, 9, 28), fecha_apertura=date(2026, 9, 29),
                         plazo_dias_habiles=15, tipo="Técnica",
                         observaciones=["R006:5.31.7", "R040:7.5.6", "R041:6.1.3", "R002:", "R007:"]),
         documentos=[
             doc("R002", "pago_derechos", escaneado=True, ilegible=True, defectos=[
                 defecto("Documento ilegible", "El comprobante de pago de derechos escaneado es ilegible.",
                         None, None, "Ley Federal de Derechos art. 195-A", "Calidad de imagen insuficiente para leer importe y referencia.")]),
             doc("R005", "etiqueta_primaria"),
             doc("R006", "etiqueta_secundaria", omitir=["mbb"], defectos=[
                 defecto("Leyenda faltante", "No aparecen las siglas M.B.B. en la superficie principal del envase secundario.",
                         "NOM-072-SSA1-2012", "5.31.7", None, "Medicamento biotecnológico biocomparable: buscar 'M.B.B.' en la cara principal.")]),
             doc("R010", "pmr"),
             doc("R011", "certificado_bpf_medicamento"),
             doc("R040", "estabilidad", refrigeracion=True, sin_excursiones=True, defectos=[
                 defecto("Estudio incompleto", "No se evalúa el impacto de excursiones de temperatura fuera de 2–8 °C.",
                         "NOM-073-SSA1-2015", "7.5.6", None, "Buscar un apartado de excursiones de temperatura en el informe.")]),
             doc("R041", "programa_aseguramiento", sin_auditorias=True, defectos=[
                 defecto("Sección faltante", "El programa de aseguramiento de calidad no incluye el programa de auditorías internas.",
                         "NOM-257-SSA1-2014", "6.1.3", None, "Comparar el índice contra los incisos 6.1.1 a 6.1.6 de la NOM-257.")]),
             doc("R042", "caracterizacion"),
             doc("R063", "estudio_biocomparabilidad"),
             doc("R065", "dictamen_etica", escaneado=True),
         ]),
    # ------------------------------------------------------------------------------------
    # A3 · Rosuvastatina: sometido, prevención abierta con plazo corto (urgente).
    # ------------------------------------------------------------------------------------
    dict(clave="A3", producto_id="P08", tipo="REG_GEN", etapa="Prevención – respuesta en preparación",
         estatus="Prevenido", fecha_ingreso=date(2026, 5, 20),
         prevencion=dict(fecha_emision=date(2026, 9, 30), fecha_apertura=date(2026, 10, 1),
                         plazo_dias_habiles=10, tipo="Técnica",
                         observaciones=["R006:6.1.6.2", "R040:8.4", "R061:7.5.5"]),
         documentos=[
             doc("R001", "solicitud"),
             doc("R006", "etiqueta_secundaria", omitir=["farmacovigilancia"], defectos=[
                 defecto("Leyenda faltante", "Falta la leyenda para reportar sospechas de reacción adversa.",
                         "NOM-072-SSA1-2012", "6.1.6.2", None, "Buscar la leyenda de farmacovigilancia en la etiqueta.")]),
             doc("R012", "certificado_bpf_farmaco", fecha_emision=date(2025, 2, 10)),
             doc("R037", "coa_lote"),
             doc("R040", "estabilidad", meses_largo_plazo=1, defectos=[
                 defecto("Datos insuficientes", "La estabilidad a largo plazo solo tiene datos a 1 mes; se requieren mínimo 3 meses al solicitar.",
                         "NOM-073-SSA1-2015", "8.4", None, "Revisar el último punto de muestreo de la tabla de largo plazo.")]),
             doc("R060", "bioequivalencia", ic_cmax=(92.10, 109.84)),
             doc("R061", "perfiles_disolucion", f2=(57.2, 46.8, 54.1), defectos=[
                 defecto("Conclusión no sustentada", "En el medio pH 4.5 el f2 es 46.8 (< 50) y el informe concluye que los perfiles son similares.",
                         "NOM-177-SSA1-2013", "7.5.5", None, "Revisar el f2 de cada medio contra el mínimo de 50.")]),
         ]),
    # ------------------------------------------------------------------------------------
    # A4 · Losartán: prórroga; COFEPRIS ya mandó el aviso pero nadie ha abierto el oficio.
    # ------------------------------------------------------------------------------------
    dict(clave="A4", producto_id="P03", tipo="PRORROGA", etapa="Aviso de prevención sin abrir",
         estatus="Aviso recibido", fecha_ingreso=date(2026, 6, 8),
         prevencion=dict(fecha_emision=date(2026, 10, 5), fecha_apertura=None,
                         plazo_dias_habiles=10, tipo="Técnica",
                         observaciones=["R006:5.17.2.5", "R010:8.4.1.2"]),
         documentos=[
             doc("R001", "solicitud", prorroga=True),
             doc("R013", "registro_sanitario", escaneado=True),
             doc("R006", "etiqueta_secundaria", domicilio_anterior=True, defectos=[
                 defecto("Dato inconsistente", "El domicilio del fabricante en la etiqueta es el anterior (Azcapotzalco); el registro autoriza el de Toluca.",
                         "NOM-072-SSA1-2012", "5.17.2.5", None, "Cruzar el domicilio de la etiqueta con el del registro sanitario.")]),
             doc("R010", None, estatus="Faltante", defectos=[
                 defecto("Documento faltante", "No se presentó plan de manejo de riesgos con la solicitud de prórroga.",
                         "NOM-220-SSA1-2016", "8.4.1.2", None, "El espacio CTD 1.6 está vacío.")]),
             doc("R011", "certificado_bpf_medicamento"),
             doc("R012", "certificado_bpf_farmaco", fecha_emision=date(2025, 6, 2)),
             doc("R014", "informe_seguridad"),
         ]),
    # ------------------------------------------------------------------------------------
    # Trámites activos sin PDF (solo datos en tablas)
    # ------------------------------------------------------------------------------------
    dict(clave="A5", producto_id="P01", tipo="MOD_SIN", descripcion="Cambio de proveedor del fármaco",
         etapa="En evaluación COFEPRIS", estatus="En evaluación", fecha_ingreso=date(2026, 8, 20), documentos=[]),
    dict(clave="A6", producto_id="P02", tipo="MOD_SIN", descripcion="Actualización de textos de etiqueta",
         etapa="Integración del expediente", estatus="Borrador", fecha_inicio=date(2026, 9, 14),
         fecha_ingreso=None, fecha_objetivo_envio=date(2026, 11, 6), documentos=[]),
    dict(clave="A7", producto_id="P07", tipo="MOD_SIN", descripcion="Inclusión de presentación comercial",
         etapa="En evaluación COFEPRIS", estatus="En evaluación", fecha_ingreso=date(2026, 9, 10), documentos=[]),
    dict(clave="A8", producto_id="P11", tipo="MOD_SITIO", descripcion="Cambio de sitio de acondicionamiento secundario",
         etapa="En evaluación COFEPRIS", estatus="En evaluación", fecha_ingreso=date(2026, 7, 28), documentos=[]),
    dict(clave="A9", producto_id="P12", tipo="REG_NUEVA", etapa="Reunión técnica con el CMN programada (12/11/2026)",
         estatus="Borrador", fecha_inicio=date(2026, 3, 2), fecha_ingreso=None,
         fecha_objetivo_envio=date(2027, 1, 29), documentos=[]),
    # A10 · Clopidogrel: ya respondió una prevención; queda el oficio y el escrito de respuesta.
    dict(clave="A10", producto_id="P06", tipo="MOD_CON", descripcion="Cambio en el proceso de granulación",
         etapa="Respuesta a prevención enviada – en evaluación", estatus="En evaluación",
         fecha_ingreso=date(2026, 6, 30),
         prevencion=dict(fecha_emision=date(2026, 8, 24), fecha_apertura=date(2026, 8, 25),
                         plazo_dias_habiles=20, tipo="Técnica", fecha_respuesta=date(2026, 9, 18),
                         observaciones=["R061:7.5.5", "R035:9.9.2.2.3"]),
         documentos=[]),
]
