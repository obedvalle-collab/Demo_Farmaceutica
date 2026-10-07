"""Fase 4 en Snowflake: bandeja de carga inteligente sobre los 54 PDF de expedientes.

Por documento: AI_PARSE_DOCUMENT (lectura) → AI_COMPLETE con Claude y salida estructurada (clasificación +
extracción). Después: aplanado de los datos, reglas de revisión compartidas (sql/hallazgos.sql) y evaluación
contra la hoja de respuestas.

Uso: python snowflake/fase4_bandeja.py [todo|reglas]
"""
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import snowflake.connector

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "compartido"))
import capas  # noqa: E402
import evaluar_bandeja  # noqa: E402
import extraccion as X  # noqa: E402

BD = "OBED_FARMACEUTICA"
MODELO = "claude-sonnet-4-5"
HILOS = 4
SALIDA = RAIZ / "docs" / "resultados" / "fase4" / "snowflake"


def conectar():
    con = snowflake.connector.connect(connection_name="obed_farma")
    con.cursor().execute("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase4'")
    return con


def preparar(cur):
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {BD}.CRUDO.EXPEDIENTES_PARSEADOS (archivo STRING, tramite_id STRING,
                    paginas INT, texto STRING, segundos FLOAT, procesado_en TIMESTAMP_NTZ)""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON (archivo STRING, tramite_id STRING,
                    modelo STRING, respuesta VARIANT, segundos FLOAT, procesado_en TIMESTAMP_NTZ)""")


def procesar_documento(archivo):
    """Lo que hará la bandeja con cada PDF que se suba: leerlo y extraer sus datos."""
    con = conectar(); cur = con.cursor()
    try:
        t = time.time()
        cur.execute(f"DELETE FROM {BD}.CRUDO.EXPEDIENTES_PARSEADOS WHERE archivo = %s", (archivo,))
        cur.execute(f"""INSERT INTO {BD}.CRUDO.EXPEDIENTES_PARSEADOS
            SELECT %s, SUBSTR(%s, 1, 11), r:metadata:pageCount::INT,
                   ARRAY_TO_STRING(TRANSFORM(r:pages, p -> p:content::STRING), '\n\n'), NULL, CURRENT_TIMESTAMP()
            FROM (SELECT AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.EXPEDIENTES', %s), {{'mode': 'LAYOUT', 'page_split': true}}) AS r)""",
                    (archivo, archivo, archivo))
        # si la lectura estructurada convirtió zonas en imágenes (escaneados, bloques de firmas),
        # se complementa con OCR, que lee todo el texto visible de la página
        cur.execute(f"""UPDATE {BD}.CRUDO.EXPEDIENTES_PARSEADOS
            SET texto = texto || '

[Texto OCR complementario]
' ||
                AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.EXPEDIENTES', %s), {{'mode': 'OCR'}}):content::STRING
            WHERE archivo = %s AND texto LIKE '%%![img-%%'""", (archivo, archivo))
        t_lectura = round(time.time() - t, 1)
        cur.execute(f"UPDATE {BD}.CRUDO.EXPEDIENTES_PARSEADOS SET segundos = %s WHERE archivo = %s", (t_lectura, archivo))
        t = time.time()
        cur.execute(f"DELETE FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON WHERE archivo = %s", (archivo,))
        cur.execute(f"""INSERT INTO {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON
            SELECT archivo, tramite_id, %s,
                   TRY_PARSE_JSON(AI_COMPLETE(model => %s, prompt => %s || LEFT(texto, {X.MAX_CARACTERES}),
                                              response_format => {{'type': 'json', 'schema': PARSE_JSON(%s)}})::STRING),
                   NULL, CURRENT_TIMESTAMP()
            FROM {BD}.CRUDO.EXPEDIENTES_PARSEADOS WHERE archivo = %s""",
                    (MODELO, MODELO, X.INSTRUCCION, X.esquema_json(), archivo))
        t_ext = round(time.time() - t, 1)
        cur.execute(f"UPDATE {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON SET segundos = %s WHERE archivo = %s", (t_ext, archivo))
        print(f"  {archivo[:70]:70s} lectura {t_lectura:5.1f} s · extracción {t_ext:5.1f} s", flush=True)
        return archivo, t_lectura, t_ext, None
    except Exception as e:
        print(f"  {archivo}: ERROR {str(e)[:200]}", flush=True)
        return archivo, None, None, str(e)[:500]
    finally:
        con.close()


def aplanar(cur):
    cur.execute(f"""CREATE OR REPLACE TABLE {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS AS
        SELECT j.archivo, j.tramite_id, j.modelo,
               r:tipo_documento::STRING AS tipo_documento, r:producto::STRING AS producto, r:emisor::STRING AS emisor,
               r:fabricante_farmaco::STRING AS fabricante_farmaco, TRY_TO_DATE(r:fecha_emision::STRING) AS fecha_emision,
               r:numero_lotes_estudio::INT AS numero_lotes_estudio,
               ARRAY_TO_STRING(r:firmas_vacias, '; ') AS firmas_vacias, ARRAY_SIZE(r:firmas_vacias) AS n_firmas_vacias,
               r:leyenda_receta_medica::BOOLEAN AS leyenda_receta_medica,
               r:leyenda_no_alcance_ninos::BOOLEAN AS leyenda_no_alcance_ninos,
               r:leyenda_farmacovigilancia::BOOLEAN AS leyenda_farmacovigilancia,
               r:leyenda_venta_fraccionada::BOOLEAN AS leyenda_venta_fraccionada,
               r:siglas_mbb::BOOLEAN AS siglas_mbb, r:codigo_postal_fabricante::STRING AS codigo_postal_fabricante,
               r:ic90_cmax_inferior::FLOAT AS ic90_cmax_inferior, r:ic90_cmax_superior::FLOAT AS ic90_cmax_superior,
               ARRAY_MIN(r:f2_valores)::FLOAT AS f2_minimo,
               ARRAY_TO_STRING(r:pruebas_fuera_especificacion, '; ') AS pruebas_fuera_especificacion,
               ARRAY_SIZE(r:pruebas_fuera_especificacion) AS n_fuera_especificacion,
               r:conclusion_favorable::BOOLEAN AS conclusion_favorable, r:meses_largo_plazo::INT AS meses_largo_plazo,
               r:evalua_excursiones_temperatura::BOOLEAN AS evalua_excursiones_temperatura,
               ARRAY_TO_STRING(r:secciones, ' | ') AS secciones, r:es_legible::BOOLEAN AS es_legible,
               LENGTH(p.texto) AS caracteres_texto, r:resumen::STRING AS resumen
        FROM (SELECT *, respuesta AS r FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON) j
        JOIN {BD}.CRUDO.EXPEDIENTES_PARSEADOS p ON p.archivo = j.archivo""")


def reglas_y_evaluacion(cur):
    texto = (RAIZ / "compartido" / "sql" / "hallazgos.sql").read_text(encoding="utf-8")
    import re
    sql = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{BD}.LIMPIO").replace("{N}", f"{BD}.NEGOCIO")
    cur.execute(sql)
    SALIDA.mkdir(parents=True, exist_ok=True)
    resultados = {}
    for nombre, consulta in [("hallazgos_ia", f"SELECT * FROM {BD}.NEGOCIO.HALLAZGOS_IA"),
                             ("documentos_extraidos", f"SELECT * FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS")]:
        filas = cur.execute(consulta).fetchall()
        cols = [c[0].lower() for c in cur.description]
        resultados[nombre] = [dict(zip(cols, ['' if v is None else str(v) for v in f])) for f in filas]
        capas.guardar(SALIDA / f"{nombre}.csv", cols, filas)
    ev = evaluar_bandeja.evaluar(resultados["documentos_extraidos"], resultados["hallazgos_ia"])
    return ev


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    con = conectar(); cur = con.cursor()
    try:
        tiempos = {}
        if accion == "todo":
            preparar(cur)
            archivos = [r[0] for r in cur.execute(
                f"SELECT relative_path FROM DIRECTORY(@{BD}.CRUDO.EXPEDIENTES) ORDER BY 1").fetchall()]
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
        aplanar(cur)
        ev = reglas_y_evaluacion(cur)
        ev["tiempos"] = tiempos
        ev["modelo"] = MODELO
        (SALIDA / "evaluacion.json").write_text(json.dumps(ev, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  Clasificación: {ev['clasificacion_correcta']} · Defectos detectados: {ev['defectos_detectados']} · "
              f"Falsas alarmas: {ev['falsas_alarmas']} · Tiempos: {tiempos}")
    finally:
        try:
            cur.execute("ALTER WAREHOUSE FARMA_WH SUSPEND")
        except snowflake.connector.errors.ProgrammingError:
            pass
        con.close()


if __name__ == "__main__":
    main()
