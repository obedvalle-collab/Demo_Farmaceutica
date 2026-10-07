"""Instrucciones de IA para el ciclo de prevenciones (mismas en ambas plataformas):
1) separar las observaciones de un oficio de prevención y leer su plazo;
2) redactar el borrador del escrito de respuesta.
También arma el texto de las alertas por correo.
"""
import json

ESQUEMA_OFICIO = {
    "type": "object",
    "properties": {
        "numero_oficio": {"type": "string"},
        "plazo_dias_habiles": {"type": "integer"},
        "observaciones": {"type": "array", "items": {
            "type": "object",
            "properties": {"numero": {"type": "integer"}, "texto": {"type": "string"}, "norma": {"type": "string"},
                           "clausula": {"type": "string"}, "seccion_ctd": {"type": "string"}},
            "required": ["numero", "texto", "norma", "clausula", "seccion_ctd"], "additionalProperties": False}},
    },
    "required": ["numero_oficio", "plazo_dias_habiles", "observaciones"],
    "additionalProperties": False,
}

INSTRUCCION_OFICIO = """Eres analista de asuntos regulatorios. Recibes el texto de un oficio de prevención de la autoridad sanitaria mexicana. Extrae:
- numero_oficio: el número de oficio tal como aparece.
- plazo_dias_habiles: el plazo en días hábiles para desahogar la prevención (número).
- observaciones: cada punto numerado, con:
  - numero: el número del punto;
  - texto: el texto de la observación (sin el fundamento);
  - norma: la norma citada en el fundamento (por ejemplo "NOM-072-SSA1-2012"); si el fundamento es una ley o reglamento, escríbelo (por ejemplo "Ley Federal de Derechos art. 195-A");
  - clausula: el numeral citado (por ejemplo "6.1.4"), o cadena vacía si no hay;
  - seccion_ctd: la sección CTD indicada entre paréntesis (por ejemplo "1.4.1"), o cadena vacía.
No inventes datos: usa solo lo que dice el oficio.

Texto del oficio:
"""

INSTRUCCION_BORRADOR = """Eres el área de asuntos regulatorios de Laboratorios Altamira, S.A. de C.V. (empresa ficticia de una demostración). Redacta en español el BORRADOR del escrito libre de respuesta a la prevención, para revisión humana antes de firmarse.

Estructura (en Markdown):
1. Encabezado: lugar y fecha ("Toluca, Estado de México, a ____"), destinatario (Comisión Federal para la Protección contra Riesgos Sanitarios, Comisión de Autorización Sanitaria) y asunto (desahogo de la prevención del oficio y folio indicados).
2. Párrafo de comparecencia del representante legal, dentro del plazo concedido.
3. Una sección por observación: "Observación N", el texto observado en cursiva, y "Respuesta": qué se corrigió o se aclara, citando la cláusula de la norma y el anexo que se adjunta ("Anexo N: <documento corregido>"). Usa el texto de la cláusula que se te da para fundamentar. NO afirmes que algo ya se corrigió ni describas cambios concretos: redacta la respuesta en términos de lo que se presenta y deja marcadores [PENDIENTE: …] donde el equipo debe describir la corrección realizada y el anexo correspondiente.
4. Petitorio: tener por desahogada la prevención en tiempo y forma.
5. Bloque de firmas: representante legal y responsable sanitario (sin nombres; "________").

No inventes resultados de laboratorio ni datos que no estén en la información proporcionada; usa marcadores [PENDIENTE].

Información:
"""


def contexto_borrador(oficio, tramite, observaciones):
    datos = {"oficio": oficio, "tramite": tramite, "observaciones": observaciones}
    return INSTRUCCION_BORRADOR + json.dumps(datos, ensure_ascii=False, default=str, indent=1)


def esquema_oficio_json():
    return json.dumps(ESQUEMA_OFICIO, ensure_ascii=False)


# ------------------------------------------------------------------------------------------------ alertas
def _html(titulo, filas, pie):
    celdas = "".join(f"<tr><td style='padding:4px 10px;color:#5f6b76'>{k}</td><td style='padding:4px 10px'><b>{v}</b></td></tr>"
                     for k, v in filas)
    return (f"<div style='font-family:Segoe UI,Arial,sans-serif;max-width:620px'>"
            f"<div style='background:#12355B;color:#fff;padding:12px 16px;font-size:16px'>{titulo}</div>"
            f"<table style='border-collapse:collapse;margin:10px 0'>{celdas}</table>"
            f"<p style='font-size:13px;color:#333'>{pie}</p>"
            f"<p style='font-size:11px;color:#888'>Demo Obed Farmacéutica · Laboratorios Altamira es ficticio · Aviso generado automáticamente.</p></div>")


def alerta_aviso(aviso, tramite, responsable):
    asunto = f"[COFEPRIS] Prevención disponible – {tramite['producto']} (folio {aviso['folio']})"
    cuerpo = _html("⚠️ COFEPRIS emitió un acto sobre su trámite",
                   [("Trámite", f"{tramite['tramite_id']} · {tramite['producto']}"), ("Folio", aviso["folio"]),
                    ("Aviso recibido", str(aviso["fecha_aviso"])),
                    ("Abrir a más tardar", f"{aviso['fecha_limite_apertura']} (5 días hábiles)"),
                    ("Responsable", responsable)],
                   "Al abrir el oficio en el portal empieza a correr el plazo para responder (surte efectos el día hábil "
                   "siguiente). Ábralo desde la app cuando el equipo esté listo.")
    return asunto, cuerpo


def alerta_oficio(oficio, tramite, n_obs, responsables):
    asunto = f"[COFEPRIS] {n_obs} observaciones – {tramite['producto']} · vence {oficio['fecha_limite']}"
    cuerpo = _html("📋 Oficio de prevención abierto y analizado",
                   [("Trámite", f"{tramite['tramite_id']} · {tramite['producto']}"), ("Oficio", oficio["numero_oficio"]),
                    ("Observaciones", n_obs), ("Plazo", f"{oficio['plazo_dias_habiles']} días hábiles"),
                    ("Fecha límite", oficio["fecha_limite"]), ("Áreas con tareas", responsables)],
                   "La IA separó las observaciones, creó las tareas por área y redactó el borrador de respuesta. "
                   "Revíselo en la vista de prevenciones de la app.")
    return asunto, cuerpo


def alerta_recordatorio(prev):
    asunto = f"[Recordatorio] {prev['producto']}: quedan {prev['dias_habiles_restantes']} días hábiles – {prev['accion_pendiente']}"
    cuerpo = _html("⏰ Recordatorio de plazo",
                   [("Trámite", f"{prev['tramite_id']} · {prev['producto']}"), ("Acción pendiente", prev["accion_pendiente"]),
                    ("Fecha límite", prev["fecha_limite_accion"]), ("Días hábiles restantes", prev["dias_habiles_restantes"]),
                    ("Tareas cerradas", f"{prev['tareas_cerradas']}/{prev['tareas']}")],
                   "Si la prevención no se desahoga en el plazo, la solicitud se tiene por no presentada (RIS art. 155).")
    return asunto, cuerpo
