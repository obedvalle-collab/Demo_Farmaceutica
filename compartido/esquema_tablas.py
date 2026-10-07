"""Tipos de dato de la capa limpia y SQL de conversión para cada plataforma.

La capa cruda guarda todo como texto (tal cual viene del CSV); la capa limpia convierte con funciones
"try" (si un valor no se puede convertir queda NULL y lo detecta el control de calidad).
"""
import csv
from pathlib import Path

TABLAS_DIR = Path(__file__).resolve().parents[1] / "datos" / "salida" / "tablas"

# llaves primarias (para los controles de calidad)
LLAVES = {
    "empresa": "rfc", "productos": "producto_id", "tipos_tramite": "clave", "requisitos_ctd": "plantilla_id",
    "tramites": "tramite_id", "documentos": "documento_id", "versiones": "version_id",
    "prevenciones": "prevencion_id", "observaciones": "observacion_id", "tareas": "tarea_id",
    "respuestas": "respuesta_id", "usuarios": "usuario_id", "calendario_habil": "fecha", "bitacora": "evento_id",
}

# llaves foráneas: (tabla, columna) -> (tabla referida, columna referida)
FORANEAS = [
    ("tramites", "producto_id", "productos", "producto_id"),
    ("tramites", "responsable_id", "usuarios", "usuario_id"),
    ("documentos", "tramite_id", "tramites", "tramite_id"),
    ("versiones", "documento_id", "documentos", "documento_id"),
    ("prevenciones", "tramite_id", "tramites", "tramite_id"),
    ("observaciones", "prevencion_id", "prevenciones", "prevencion_id"),
    ("observaciones", "documento_id", "documentos", "documento_id"),
    ("tareas", "observacion_id", "observaciones", "observacion_id"),
    ("tareas", "responsable_id", "usuarios", "usuario_id"),
    ("respuestas", "prevencion_id", "prevenciones", "prevencion_id"),
]

_BOOL = {"es_habil", "tiene_pdf_demo", "escaneado", "activo", "cronico", "notificada_por_estrados", "tuvo_prevencion",
         "es_activo", "obligatorio"}
_INT = {"anio", "mes", "dia_semana", "version_actual", "paginas", "tamano_kb", "numero", "plazo_dias_habiles",
        "num_observaciones", "num_documentos_adjuntos", "dias_habiles_usados", "plazo_resolucion_dias",
        "dias_en_cofepris", "dias_para_vencimiento", "version"}


def tipo(columna):
    if columna == "fecha_hora":
        return "timestamp"
    if columna == "fecha" or columna.startswith("fecha_"):
        return "date"
    if columna in _BOOL:
        return "bool"
    if columna in _INT:
        return "int"
    return "string"


def columnas(tabla):
    with open(TABLAS_DIR / f"{tabla}.csv", encoding="utf-8") as fh:
        return next(csv.reader(fh))


def tablas():
    return sorted(p.stem for p in TABLAS_DIR.glob("*.csv"))


def _conv(col, t, plataforma):
    c = f"NULLIF(TRIM({col}), '')"
    if plataforma == "snowflake":
        return {"date": f"TRY_TO_DATE({c})", "timestamp": f"TRY_TO_TIMESTAMP_NTZ({c})",
                "bool": f"TRY_TO_BOOLEAN({c})", "int": f"TRY_TO_NUMBER({c})", "string": c}[t]
    return {"date": f"try_cast({c} AS DATE)", "timestamp": f"try_cast({c} AS TIMESTAMP)",
            "bool": f"try_cast({c} AS BOOLEAN)", "int": f"try_cast({c} AS INT)", "string": c}[t]


def sql_limpia(tabla, origen, destino, plataforma):
    """CREATE TABLE de la capa limpia con conversión de tipos."""
    sel = ",\n       ".join(f"{_conv(c, tipo(c), plataforma)} AS {c}" for c in columnas(tabla))
    return f"CREATE OR REPLACE TABLE {destino} AS\nSELECT {sel}\nFROM {origen}"
