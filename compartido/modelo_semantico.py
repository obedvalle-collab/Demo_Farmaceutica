"""Diccionario de datos del asistente (Vista 8), el mismo para ambas plataformas.

De aquí salen la vista semántica de Snowflake (Cortex Analyst) y el espacio Genie de Databricks: mismas tablas,
descripciones, sinónimos, relaciones, instrucciones y preguntas de ejemplo.
Columnas: (nombre, "dim" | "hecho" | "fecha", descripción, sinónimos).
"""

FECHA_DEMO = "2026-10-06"

INSTRUCCIONES_DATOS = (
    f"Datos de Laboratorios Altamira (empresa ficticia) y sus trámites ante COFEPRIS. La fecha de hoy en la demo es {FECHA_DEMO}: "
    "úsala en lugar de CURRENT_DATE. Los plazos de prevención se cuentan en días hábiles (columna dias_habiles_restantes). "
    "Para trámites en curso usa portafolio; para prevenciones vivas detectadas por la app usa prevenciones_en_curso; "
    "para el historial usa prevenciones y observaciones. Responde en español."
)

TABLAS = [
    {"nombre": "portafolio", "esquema": "negocio", "pk": ["tramite_id"],
     "descripcion": "Trámites activos (tablero ejecutivo): etapa, días en COFEPRIS, cobertura del expediente y prevención pendiente.",
     "columnas": [
         ("tramite_id", "dim", "Identificador del trámite (TR-AAAA-NNN)", ["trámite", "expediente"]),
         ("producto", "dim", "Medicamento con su concentración", ["medicamento", "producto"]),
         ("familia", "dim", "Tipo de trámite: Registro nuevo, Modificación o Prórroga", ["tipo de trámite"]),
         ("tipo_tramite", "dim", "Nombre oficial del trámite COFEPRIS", []),
         ("etapa", "dim", "Etapa actual del trámite", ["fase", "situación"]),
         ("estatus", "dim", "Estatus del trámite", []),
         ("fecha_ingreso", "fecha", "Fecha en que se ingresó a COFEPRIS", ["fecha de envío"]),
         ("dias_en_cofepris", "hecho", "Días naturales desde el ingreso a COFEPRIS", ["días en evaluación"]),
         ("cobertura_pct", "hecho", "Porcentaje del expediente CTD completo", ["avance del expediente"]),
         ("candado_envio", "dim", "Listo para envío, Bloqueado o Ya enviado", []),
         ("accion_pendiente", "dim", "Acción pendiente por prevención: Abrir oficio o Responder prevención", []),
         ("fecha_limite_accion", "fecha", "Fecha límite de la acción pendiente", ["vencimiento"]),
         ("dias_habiles_restantes", "hecho", "Días hábiles que quedan para la acción pendiente", ["plazo restante"]),
         ("semaforo_prevencion", "dim", "Verde, Amarillo, Rojo, Vencido o Sin prevención", ["semáforo"])]},
    {"nombre": "prevenciones_en_curso", "esquema": "negocio", "pk": ["aviso_id"],
     "descripcion": "Prevenciones vivas detectadas por la app (aviso del portal, oficio abierto y analizado, tareas).",
     "columnas": [
         ("aviso_id", "dim", "Identificador del aviso", []),
         ("tramite_id", "dim", "Trámite", []), ("producto", "dim", "Medicamento", ["medicamento"]),
         ("folio", "dim", "Folio DIGIPRiS", []), ("numero_oficio", "dim", "Número del oficio de prevención", ["oficio"]),
         ("accion_pendiente", "dim", "Abrir oficio o Responder prevención", []),
         ("fecha_limite_accion", "fecha", "Fecha límite", ["vencimiento"]),
         ("dias_habiles_restantes", "hecho", "Días hábiles restantes", ["plazo restante"]),
         ("tareas", "hecho", "Tareas creadas", []), ("tareas_cerradas", "hecho", "Tareas cerradas", []),
         ("semaforo", "dim", "Verde, Amarillo, Rojo o Vencido", [])]},
    {"nombre": "registros_vigencia", "esquema": "negocio", "pk": ["producto_id"],
     "descripcion": "Registros sanitarios: vencimiento (5 años) y fecha límite para pedir prórroga (150 días antes).",
     "columnas": [
         ("producto_id", "dim", "Identificador del producto", []), ("producto", "dim", "Medicamento", ["medicamento"]),
         ("registro_sanitario", "dim", "Número de registro sanitario", ["registro"]),
         ("fecha_vencimiento_registro", "fecha", "Fecha en que vence el registro", ["vencimiento del registro"]),
         ("fecha_limite_solicitar_prorroga", "fecha", "Último día para solicitar la prórroga", []),
         ("dias_para_limite_prorroga", "hecho", "Días naturales para el límite de prórroga", []),
         ("estatus_vigencia", "dim", "Vigente, Preparar prórroga, Solicitar prórroga urgente, Prórroga en trámite", []),
         ("semaforo", "dim", "Verde, Amarillo, Rojo o En trámite", [])]},
    {"nombre": "expediente_estado", "esquema": "negocio", "pk": ["tramite_id", "requisito_id"],
     "descripcion": "Estado de cada requisito del expediente CTD de los trámites cargados en la app.",
     "columnas": [
         ("tramite_id", "dim", "Trámite", []), ("requisito_id", "dim", "Requisito", []),
         ("seccion_ctd", "dim", "Sección CTD (ej. 3.2.P.8)", ["sección"]),
         ("nombre_requisito", "dim", "Nombre del requisito o documento", ["documento"]),
         ("area_responsable", "dim", "Área responsable", ["área"]),
         ("version", "hecho", "Versión vigente del documento", []),
         ("hallazgos_abiertos", "hecho", "Hallazgos de la revisión automática sin resolver", ["defectos"]),
         ("estatus_efectivo", "dim", "Validado, Con hallazgos, Faltante, etc.", ["estatus del documento"])]},
    {"nombre": "tramites", "esquema": "limpio", "pk": ["tramite_id"],
     "descripcion": "Todos los trámites 2023–2026 (históricos y activos) con su resultado.",
     "columnas": [
         ("tramite_id", "dim", "Trámite", []), ("producto_id", "dim", "Producto", []),
         ("producto", "dim", "Medicamento", ["medicamento"]),
         ("familia", "dim", "Registro nuevo, Modificación o Prórroga", ["tipo de trámite"]),
         ("descripcion", "dim", "Descripción del trámite", []),
         ("fecha_ingreso", "fecha", "Fecha de ingreso a COFEPRIS", []),
         ("fecha_resolucion", "fecha", "Fecha de resolución", []),
         ("resultado", "dim", "Aprobado, Negado, Desechado, Desistido", []),
         ("tuvo_prevencion", "dim", "Si el trámite tuvo al menos una prevención", []),
         ("dias_en_cofepris", "hecho", "Días naturales en COFEPRIS", []),
         ("es_activo", "dim", "Si el trámite sigue en curso", []),
         ("responsable_id", "dim", "Usuario responsable", [])]},
    {"nombre": "productos", "esquema": "limpio", "pk": ["producto_id"],
     "descripcion": "Portafolio de productos (genéricos y biocomparables).",
     "columnas": [
         ("producto_id", "dim", "Producto", []), ("denominacion_generica", "dim", "Principio activo", ["fármaco"]),
         ("concentracion", "dim", "Concentración", []), ("tipo_producto", "dim", "Genérico o Biocomparable", []),
         ("area_terapeutica", "dim", "Área terapéutica", []), ("fabricante_farmaco", "dim", "Fabricante del fármaco", ["proveedor"])]},
    {"nombre": "prevenciones", "esquema": "limpio", "pk": ["prevencion_id"],
     "descripcion": "Oficios de prevención históricos y activos emitidos por COFEPRIS.",
     "columnas": [
         ("prevencion_id", "dim", "Prevención", []), ("tramite_id", "dim", "Trámite", []),
         ("numero_oficio", "dim", "Número de oficio", ["oficio"]), ("fecha_emision", "fecha", "Fecha de emisión", []),
         ("plazo_dias_habiles", "hecho", "Plazo en días hábiles", []), ("num_observaciones", "hecho", "Número de observaciones", []),
         ("estatus", "dim", "Sin abrir, Abierta, Respondida, etc.", [])]},
    {"nombre": "observaciones", "esquema": "limpio", "pk": ["observacion_id"],
     "descripcion": "Observaciones de los oficios de prevención, con la norma y el numeral citados.",
     "columnas": [
         ("observacion_id", "dim", "Observación", []), ("prevencion_id", "dim", "Prevención", []),
         ("tramite_id", "dim", "Trámite", []), ("seccion_ctd", "dim", "Sección CTD observada", ["sección"]),
         ("norma", "dim", "Norma citada (ej. NOM-072-SSA1-2012)", ["NOM"]), ("clausula", "dim", "Numeral citado", ["numeral"]),
         ("texto", "dim", "Texto de la observación", []), ("severidad", "dim", "Mayor o Menor", []),
         ("area_responsable", "dim", "Área que la atiende", ["área"]), ("estatus", "dim", "Estatus de la observación", [])]},
    {"nombre": "tareas", "esquema": "limpio", "pk": ["tarea_id"],
     "descripcion": "Tareas para atender observaciones, con área, responsable y fechas.",
     "columnas": [
         ("tarea_id", "dim", "Tarea", []), ("observacion_id", "dim", "Observación", []), ("area", "dim", "Área", ["área"]),
         ("fecha_compromiso", "fecha", "Fecha compromiso", []), ("fecha_cierre", "fecha", "Fecha de cierre", []),
         ("estatus", "dim", "Pendiente, En curso, Cerrada o Vencida", [])]},
    {"nombre": "usuarios", "esquema": "limpio", "pk": ["usuario_id"],
     "descripcion": "Personal (ficticio) con rol y área.",
     "columnas": [("usuario_id", "dim", "Usuario", []), ("nombre", "dim", "Nombre", ["persona"]),
                  ("rol", "dim", "Puesto", ["puesto"]), ("area", "dim", "Área", ["área"])]},
]

RELACIONES = [  # (tabla, columna, tabla referida)
    ("tramites", "producto_id", "productos"),
    ("tramites", "responsable_id", "usuarios"),
    ("prevenciones", "tramite_id", "tramites"),
    ("observaciones", "prevencion_id", "prevenciones"),
    ("tareas", "observacion_id", "observaciones"),
]

METRICAS = [  # (tabla, nombre, expresión, descripción)
    ("tramites", "total_tramites", "COUNT(tramites.tramite_id)", "Número de trámites"),
    ("tramites", "ciclo_promedio_dias", "AVG(tramites.dias_en_cofepris)", "Días promedio en COFEPRIS"),
    ("prevenciones", "total_prevenciones", "COUNT(prevenciones.prevencion_id)", "Número de prevenciones"),
    ("observaciones", "total_observaciones", "COUNT(observaciones.observacion_id)", "Número de observaciones"),
    ("tareas", "total_tareas", "COUNT(tareas.tarea_id)", "Número de tareas"),
]

PREGUNTAS_EJEMPLO = [
    "¿Qué prevenciones vencen en los próximos 5 días hábiles?",
    "¿Qué normas generan más observaciones?",
    "¿Qué registros sanitarios hay que renovar?",
    "¿Qué le falta al expediente de la sitagliptina?",
    "¿Cuántos trámites se aprobaron al primer intento en 2025?",
]

INSTRUCCIONES_AGENTE = (
    "Eres el asistente regulatorio de Laboratorios Altamira (empresa ficticia de una demostración). "
    f"Hoy es {FECHA_DEMO}. Usa la herramienta de datos para preguntas sobre trámites, plazos, prevenciones, registros, "
    "expedientes e indicadores; usa el buscador de normas para preguntas sobre lo que dicen las NOM, leyes y guías. "
    "Reglas: responde en español y de forma breve; cita siempre la fuente (tabla consultada, o norma y numeral); "
    "si la información no está en las herramientas, dilo y no inventes."
)
