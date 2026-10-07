"""Fase 4 en Databricks: bandeja de carga inteligente sobre los 54 PDF de expedientes.

Por documento: ai_parse_document (lectura; reconoce firmas y figuras) → ai_query con gpt-oss-120b y salida
estructurada (clasificación + extracción). Después: aplanado, reglas compartidas (sql/hallazgos.sql) y evaluación.

Uso: python databricks/fase4_bandeja.py [todo|reglas]
"""
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase2_normas as F  # noqa: E402
from databricks.sdk.service.sql import StatementParameterListItem as Param  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
import capas  # noqa: E402
import evaluar_bandeja  # noqa: E402
import extraccion as X  # noqa: E402

CAT = F.CAT
VOL = f"/Volumes/{CAT}/crudo/expedientes"
MODELO = "databricks-gpt-oss-120b"
HILOS = 4
SALIDA = RAIZ / "docs" / "resultados" / "fase4" / "databricks"
FORMATO = json.dumps({"type": "json_schema", "json_schema": {"name": "extraccion", "schema": X.esquema(), "strict": True}},
                     ensure_ascii=False)
DDL = ("STRUCT<tipo_documento: STRING, producto: STRING, emisor: STRING, fabricante_farmaco: STRING, fecha_emision: STRING, "
       "numero_lotes_estudio: INT, firmas_vacias: ARRAY<STRING>, leyenda_receta_medica: BOOLEAN, "
       "leyenda_no_alcance_ninos: BOOLEAN, leyenda_farmacovigilancia: BOOLEAN, leyenda_venta_fraccionada: BOOLEAN, "
       "siglas_mbb: BOOLEAN, codigo_postal_fabricante: STRING, ic90_cmax_inferior: DOUBLE, ic90_cmax_superior: DOUBLE, "
       "f2_valores: ARRAY<DOUBLE>, pruebas_fuera_especificacion: ARRAY<STRING>, conclusion_favorable: BOOLEAN, "
       "meses_largo_plazo: INT, evalua_excursiones_temperatura: BOOLEAN, secciones: ARRAY<STRING>, es_legible: BOOLEAN, "
       "resumen: STRING>")


def listar(ruta):
    for e in F.w.files.list_directory_contents(ruta):
        if e.is_directory:
            yield from listar(e.path)
        elif e.path.endswith(".pdf"):
            yield e.path.removeprefix(VOL + "/")


def preparar():
    F.sql(f"""CREATE TABLE IF NOT EXISTS {CAT}.crudo.expedientes_parseados (archivo STRING, tramite_id STRING,
              paginas INT, texto STRING, segundos DOUBLE, procesado_en TIMESTAMP)""")
    F.sql(f"""CREATE TABLE IF NOT EXISTS {CAT}.limpio.documentos_extraidos_json (archivo STRING, tramite_id STRING,
              modelo STRING, respuesta STRING, segundos DOUBLE, procesado_en TIMESTAMP)""")


def procesar_documento(archivo):
    """Lo que hará la bandeja con cada PDF que se suba: leerlo y extraer sus datos."""
    a = [Param(name="a", value=archivo)]
    try:
        t = time.time()
        F.sql(f"DELETE FROM {CAT}.crudo.expedientes_parseados WHERE archivo = :a", a)
        F.sql(f"""INSERT INTO {CAT}.crudo.expedientes_parseados
            SELECT :a, substr(:a, 1, 11), size(cast(r:document:pages AS ARRAY<VARIANT>)),
                   array_join(transform(
                       filter(cast(r:document:elements AS ARRAY<VARIANT>),
                              e -> cast(e:type AS STRING) <> 'page_number'),   -- los encabezados traen títulos clave (p. ej. "ENVASE SECUNDARIO")
                       e -> CASE cast(e:type AS STRING)
                                WHEN 'signature' THEN '[Firma manuscrita detectada]'
                                WHEN 'figure' THEN concat('[Figura] ', coalesce(cast(e:content AS STRING), ''))
                                ELSE cast(e:content AS STRING) END), '\\n\\n'),
                   NULL, current_timestamp()
            FROM (SELECT ai_parse_document(content, map('version', '2.0')) AS r
                  FROM READ_FILES('{VOL}/{archivo}', format => 'binaryFile'))""", a, espera=1800)
        t_lectura = round(time.time() - t, 1)
        F.sql(f"UPDATE {CAT}.crudo.expedientes_parseados SET segundos = {t_lectura} WHERE archivo = :a", a)
        t = time.time()
        F.sql(f"DELETE FROM {CAT}.limpio.documentos_extraidos_json WHERE archivo = :a", a)
        F.sql(f"""INSERT INTO {CAT}.limpio.documentos_extraidos_json
            SELECT archivo, tramite_id, :m,
                   ai_query(:m, concat(:i, left(texto, {X.MAX_CARACTERES})), responseFormat => :f), NULL, current_timestamp()
            FROM {CAT}.crudo.expedientes_parseados WHERE archivo = :a""",
              a + [Param(name="m", value=MODELO), Param(name="i", value=X.INSTRUCCION), Param(name="f", value=FORMATO)],
              espera=1800)
        t_ext = round(time.time() - t, 1)
        F.sql(f"UPDATE {CAT}.limpio.documentos_extraidos_json SET segundos = {t_ext} WHERE archivo = :a", a)
        print(f"  {archivo[:70]:70s} lectura {t_lectura:5.1f} s · extracción {t_ext:5.1f} s", flush=True)
        return archivo, t_lectura, t_ext, None
    except Exception as e:
        print(f"  {archivo}: ERROR {str(e)[:200]}", flush=True)
        return archivo, None, None, str(e)[:500]


def aplanar():
    F.sql(f"""CREATE OR REPLACE TABLE {CAT}.limpio.documentos_extraidos AS
        SELECT j.archivo, j.tramite_id, j.modelo,
               r.tipo_documento, r.producto, r.emisor, r.fabricante_farmaco, try_cast(r.fecha_emision AS DATE) AS fecha_emision,
               r.numero_lotes_estudio,
               array_join(r.firmas_vacias, '; ') AS firmas_vacias,
               CASE WHEN r.firmas_vacias IS NULL THEN 0 ELSE size(r.firmas_vacias) END AS n_firmas_vacias,
               r.leyenda_receta_medica, r.leyenda_no_alcance_ninos, r.leyenda_farmacovigilancia, r.leyenda_venta_fraccionada,
               r.siglas_mbb, r.codigo_postal_fabricante, r.ic90_cmax_inferior, r.ic90_cmax_superior,
               array_min(r.f2_valores) AS f2_minimo,
               array_join(r.pruebas_fuera_especificacion, '; ') AS pruebas_fuera_especificacion,
               CASE WHEN r.pruebas_fuera_especificacion IS NULL THEN 0 ELSE size(r.pruebas_fuera_especificacion) END AS n_fuera_especificacion,
               r.conclusion_favorable, r.meses_largo_plazo, r.evalua_excursiones_temperatura,
               array_join(r.secciones, ' | ') AS secciones, r.es_legible,
               length(p.texto) AS caracteres_texto, r.resumen
        FROM (SELECT *, from_json(respuesta, '{DDL}') AS r FROM {CAT}.limpio.documentos_extraidos_json) j
        JOIN {CAT}.crudo.expedientes_parseados p ON p.archivo = j.archivo""")


def exportar(consulta, nombre):
    r = F.w.statement_execution.execute_statement(statement=consulta, warehouse_id=F.WAREHOUSE, wait_timeout="50s")
    while r.status.state.value in ("PENDING", "RUNNING"):
        time.sleep(2); r = F.w.statement_execution.get_statement(r.statement_id)
    cols = [c.name for c in r.manifest.schema.columns]
    filas = r.result.data_array or []
    capas.guardar(SALIDA / f"{nombre}.csv", cols, filas)
    return [dict(zip(cols, ['' if v is None else str(v) for v in f])) for f in filas]


def reglas_y_evaluacion():
    texto = (RAIZ / "compartido" / "sql" / "hallazgos.sql").read_text(encoding="utf-8")
    F.sql(re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{CAT}.limpio").replace("{N}", f"{CAT}.negocio"))
    SALIDA.mkdir(parents=True, exist_ok=True)
    hallazgos = exportar(f"SELECT * FROM {CAT}.negocio.hallazgos_ia", "hallazgos_ia")
    extraidos = exportar(f"SELECT * FROM {CAT}.limpio.documentos_extraidos", "documentos_extraidos")
    return evaluar_bandeja.evaluar(extraidos, hallazgos)


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    try:
        tiempos = {}
        if accion == "todo":
            preparar()
            archivos = sorted(listar(VOL))
            print(f"▶ Procesando {len(archivos)} PDF con {HILOS} hilos (lectura + extracción con {MODELO})")
            t = time.time()
            with ThreadPoolExecutor(HILOS) as ex:
                res = list(ex.map(procesar_documento, archivos))
            tiempos["total_54_documentos_s"] = round(time.time() - t, 1)
            ok = [r for r in res if not r[3]]
            tiempos["lectura_mediana_s"] = sorted(r[1] for r in ok)[len(ok) // 2]
            tiempos["extraccion_mediana_s"] = sorted(r[2] for r in ok)[len(ok) // 2]
            tiempos["errores"] = [r for r in res if r[3]]
        print("▶ Aplanado, reglas y evaluación")
        aplanar()
        ev = reglas_y_evaluacion()
        ev["tiempos"] = tiempos
        ev["modelo"] = MODELO
        (SALIDA / "evaluacion.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Clasificación: {ev['clasificacion_correcta']} · Defectos detectados: {ev['defectos_detectados']} · "
              f"Falsas alarmas: {ev['falsas_alarmas']} · Tiempos: {tiempos}")
    finally:
        F.w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
