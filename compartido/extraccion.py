"""Instrucción y esquema de extracción para la bandeja de carga inteligente (Fase 4).

La IA SOLO clasifica y extrae datos; las reglas de revisión contra la NOM viven en sql/hallazgos.sql.
El mismo texto de instrucción y el mismo esquema se usan en Snowflake y en Databricks.
"""
import csv
import json
from pathlib import Path

AQUI = Path(__file__).resolve().parent
MAX_CARACTERES = 24000     # los documentos de la demo caben completos; se recorta por seguridad


def tipos_documento():
    empaquetado = AQUI / "tipos_documento.json"   # dentro de las apps publicadas no está el CSV del generador
    if empaquetado.exists():
        return json.loads(empaquetado.read_text(encoding="utf-8"))
    nombres = []
    with open(AQUI.parent / "datos" / "salida" / "tablas" / "requisitos_ctd.csv", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["nombre"] not in nombres:
                nombres.append(r["nombre"])
    return nombres + ["Oficio de prevención", "Escrito de respuesta a prevención", "Otro"]


def _nul(t):
    return {"type": [t, "null"]}


def esquema():
    return {
        "type": "object",
        "properties": {
            "tipo_documento": {"type": "string", "enum": tipos_documento()},
            "producto": _nul("string"),
            "emisor": _nul("string"),
            "fabricante_farmaco": _nul("string"),
            "fecha_emision": _nul("string"),
            "numero_lotes_estudio": _nul("integer"),
            "firmas_vacias": {"type": "array", "items": {"type": "string"}},
            "leyenda_receta_medica": _nul("boolean"),
            "leyenda_no_alcance_ninos": _nul("boolean"),
            "leyenda_farmacovigilancia": _nul("boolean"),
            "leyenda_venta_fraccionada": _nul("boolean"),
            "siglas_mbb": _nul("boolean"),
            "codigo_postal_fabricante": _nul("string"),
            "ic90_cmax_inferior": _nul("number"),
            "ic90_cmax_superior": _nul("number"),
            "f2_valores": {"type": "array", "items": {"type": "number"}},
            "pruebas_fuera_especificacion": {"type": "array", "items": {"type": "string"}},
            "conclusion_favorable": _nul("boolean"),
            "meses_largo_plazo": _nul("integer"),
            "evalua_excursiones_temperatura": _nul("boolean"),
            "secciones": {"type": "array", "items": {"type": "string"}},
            "es_legible": {"type": "boolean"},
            "resumen": {"type": "string"},
        },
        "required": ["tipo_documento", "producto", "emisor", "fabricante_farmaco", "fecha_emision",
                     "numero_lotes_estudio", "firmas_vacias", "leyenda_receta_medica", "leyenda_no_alcance_ninos",
                     "leyenda_farmacovigilancia", "leyenda_venta_fraccionada", "siglas_mbb",
                     "codigo_postal_fabricante", "ic90_cmax_inferior", "ic90_cmax_superior", "f2_valores",
                     "pruebas_fuera_especificacion", "conclusion_favorable", "meses_largo_plazo",
                     "evalua_excursiones_temperatura", "secciones", "es_legible", "resumen"],
        "additionalProperties": False,
    }


INSTRUCCION = """Eres analista de asuntos regulatorios de una farmacéutica mexicana. Recibes el texto de UN documento de un expediente de registro sanitario (formato CTD) leído de un PDF. Clasifícalo y extrae sus datos. No evalúes si cumple la norma: solo reporta lo que dice el documento. Si un dato no aplica o no aparece, usa null (o lista vacía).

Reglas de extracción:
- tipo_documento: elige el valor de la lista que mejor describa el documento.
- emisor: organización que emite o firma el documento (laboratorio, autoridad, tercero, proveedor).
- fabricante_farmaco: fabricante del principio activo (fármaco) que aparece en el documento, si aparece.
- fecha_emision: fecha de emisión o expedición del documento, formato AAAA-MM-DD.
- numero_lotes_estudio: cuántos lotes distintos se incluyen en el estudio (estabilidad, validación); cuéntalos en las tablas.
- firmas_vacias: roles cuyo espacio de firma está vacío o sin fecha (por ejemplo, la fecha aparece como "____").
- leyenda_*: solo para etiquetas. true si la leyenda aparece en el texto, false si no aparece. receta_medica = "Su venta requiere receta médica"; no_alcance_ninos = "No se deje al alcance de los niños"; farmacovigilancia = reporte de sospechas de reacción adversa; venta_fraccionada = "prohibida la venta fraccionada"; siglas_mbb = siglas "M.B.B.".
- codigo_postal_fabricante: código postal del domicilio del fabricante que declara el documento (etiquetas y registros).
- ic90_cmax_inferior / ic90_cmax_superior: límites del intervalo de confianza al 90% de Cmáx en estudios de bioequivalencia, en porcentaje.
- f2_valores: todos los valores del factor de similitud f2 reportados.
- pruebas_fuera_especificacion: pruebas cuyo resultado NO cumple la especificación numérica indicada, aunque el documento diga "Cumple".
- conclusion_favorable: true si el documento concluye favorablemente (bioequivalente, perfiles similares, lote aprobado, cumple).
- meses_largo_plazo: último mes con datos en la estabilidad a largo plazo.
- evalua_excursiones_temperatura: si el estudio de estabilidad evalúa excursiones de temperatura.
- secciones: títulos de las secciones o apartados del documento, en orden.
- es_legible: false si el texto es ilegible, vacío o casi no tiene contenido útil.
- resumen: una frase en español con lo esencial del documento.

Texto del documento:
"""


def prompt(texto):
    return INSTRUCCION + (texto or "")[:MAX_CARACTERES]


def esquema_json():
    return json.dumps(esquema(), ensure_ascii=False)
