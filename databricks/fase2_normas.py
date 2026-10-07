"""Fase 2 en Databricks: carga de normas a un volume, lectura con ai_parse_document, partición por cláusula
(mismo código que Snowflake), buscador Vector Search y examen. Mide el tiempo de cada paso.

Uso:
    python databricks/fase2_normas.py todo      # todos los pasos
    python databricks/fase2_normas.py examen    # solo el examen
    python databricks/fase2_normas.py apagar    # borra el endpoint de Vector Search (cobra mientras exista) y apaga el warehouse
"""
import csv
import glob
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

CLI = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Databricks.DatabricksCLI_*"))
os.environ["PATH"] += os.pathsep + os.pathsep.join(CLI)

from databricks.sdk import WorkspaceClient  # noqa: E402
from databricks.sdk.service.sql import StatementState  # noqa: E402
from databricks.sdk.service.vectorsearch import (DeltaSyncVectorIndexSpecRequest, EmbeddingSourceColumn,  # noqa: E402
                                                 EndpointType, PipelineType, VectorIndexType)

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "compartido"))
from examen_buscador import PREGUNTAS, calificar  # noqa: E402

CAT = "obed_farmaceutica"
WAREHOUSE = "f0765c244dca9b5a"          # farma_wh (serverless 2X-Small, auto-stop 5 min)
VOLUMEN = f"/Volumes/{CAT}/crudo/normas"
ENDPOINT_VS = "farma_vs"
INDICE = f"{CAT}.ia.buscador_normas"
MODELO_EMB = "databricks-qwen3-embedding-0-6b"   # único modelo de embeddings multilingüe disponible
TIEMPOS = {}
RESULTADOS = RAIZ / "docs" / "resultados"
w = WorkspaceClient(profile="obed_farma")


def sql(sentencia, params=None, espera=600):
    r = w.statement_execution.execute_statement(statement=sentencia, warehouse_id=WAREHOUSE, wait_timeout="50s",
                                                parameters=params or [])
    t = time.time()
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        if time.time() - t > espera:
            w.statement_execution.cancel_execution(r.statement_id)
            raise TimeoutError(sentencia[:80])
        time.sleep(2)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.state}: {r.status.error.message if r.status.error else ''}"[:1500])
    return r.result.data_array if r.result and r.result.data_array else []


def paso(nombre):
    def deco(f):
        def envoltura(*a, **k):
            t = time.time()
            print(f"\n▶ {nombre}")
            r = f(*a, **k)
            TIEMPOS[nombre] = round(time.time() - t, 2)
            print(f"  ✓ {TIEMPOS[nombre]} s")
            return r
        return envoltura
    return deco


def iniciar_endpoint():
    """Crea el endpoint de Vector Search sin esperar (tarda varios minutos en estar listo)."""
    existentes = [e.name for e in w.vector_search_endpoints.list_endpoints()]
    if ENDPOINT_VS not in existentes:
        w.vector_search_endpoints.create_endpoint(name=ENDPOINT_VS, endpoint_type=EndpointType.STANDARD)
        print(f"  endpoint {ENDPOINT_VS} en creación")
    TIEMPOS["_inicio_endpoint"] = time.time()


@paso("1. Esquemas y volume")
def esquemas():
    for s in ["crudo", "limpio", "negocio", "ia"]:
        sql(f"CREATE SCHEMA IF NOT EXISTS {CAT}.{s}")
    sql(f"CREATE VOLUME IF NOT EXISTS {CAT}.crudo.normas COMMENT 'PDF de normas (DOF, leyes, guías ICH)'")


@paso("2. Subir PDF al volume")
def subir():
    catalogo = list(csv.DictReader(open(RAIZ / "compartido" / "catalogo_normas.csv", encoding="utf-8")))
    for r in catalogo:
        with open(RAIZ / "normas" / r["archivo"], "rb") as fh:
            w.files.upload(f"{VOLUMEN}/{r['archivo']}", fh, overwrite=True)
    sql(f"""CREATE OR REPLACE TABLE {CAT}.crudo.normas_catalogo (archivo STRING, clave STRING, titulo STRING,
            tipo STRING, estatus STRING, fecha_dof DATE, norma_relacionada STRING, idioma STRING, fuente STRING)""")
    valores = ",".join(
        "(" + ",".join("NULL" if v == "" else "'" + v.replace("'", "''") + "'" for v in
                       [r["archivo"], r["clave"], r["titulo"], r["tipo"], r["estatus"], r["fecha_dof"],
                        r["norma_relacionada"], r["idioma"], r["fuente"]]) + ")" for r in catalogo)
    sql(f"INSERT INTO {CAT}.crudo.normas_catalogo VALUES {valores}")
    print(f"  {len(catalogo)} archivos")


@paso("3. Lectura con IA (ai_parse_document)")
def leer():
    sql(f"""CREATE TABLE IF NOT EXISTS {CAT}.crudo.normas_parseadas (archivo STRING, paginas INT, texto STRING,
            resultado VARIANT, segundos DOUBLE, error STRING, procesado_en TIMESTAMP)""")
    hechos = {r[0] for r in sql(f"SELECT archivo FROM {CAT}.crudo.normas_parseadas WHERE error IS NULL")}
    archivos = [r[0] for r in sql(f"SELECT archivo FROM {CAT}.crudo.normas_catalogo ORDER BY archivo")]
    por_doc = {}
    for a in archivos:
        if a in hechos:
            continue
        t = time.time()
        try:
            sql(f"""INSERT INTO {CAT}.crudo.normas_parseadas
                SELECT '{a}', size(cast(r:document:pages AS ARRAY<VARIANT>)),
                       array_join(transform(
                           filter(cast(r:document:elements AS ARRAY<VARIANT>),
                                  e -> cast(e:type AS STRING) NOT IN ('page_header', 'page_footer', 'page_number')),
                           e -> cast(e:content AS STRING)), '\\n\\n'),
                       r, NULL, NULL, current_timestamp()
                FROM (SELECT ai_parse_document(content, map('version', '2.0')) AS r
                      FROM READ_FILES('{VOLUMEN}/{a}', format => 'binaryFile'))""", espera=1800)
            seg = round(time.time() - t, 1)
            sql(f"UPDATE {CAT}.crudo.normas_parseadas SET segundos = {seg} WHERE archivo = '{a}'")
            por_doc[a] = seg
            print(f"  {a}: {seg} s")
        except Exception as e:
            msg = str(e)[:1500].replace("'", "''")
            sql(f"INSERT INTO {CAT}.crudo.normas_parseadas (archivo, error, procesado_en) VALUES ('{a}', '{msg}', current_timestamp())")
            print(f"  {a}: ERROR {str(e)[:200]}")
    TIEMPOS["3a. segundos por documento"] = por_doc


@paso("4. Funciones de partición (mismo código que Snowflake)")
def funciones():
    codigo = (RAIZ / "compartido" / "partir_clausulas.py").read_text(encoding="utf-8")
    sql(f"""CREATE OR REPLACE FUNCTION {CAT}.limpio.partir_clausulas(texto STRING, norma STRING, tipo STRING)
        RETURNS STRING LANGUAGE PYTHON COMMENT 'compartido/partir_clausulas.py' AS $$
{codigo}
import json
return json.dumps(partir(texto, norma, tipo), ensure_ascii=False)
$$""")
    sql(f"""CREATE OR REPLACE FUNCTION {CAT}.limpio.fragmentar(texto STRING, encabezado STRING)
        RETURNS STRING LANGUAGE PYTHON COMMENT 'compartido/partir_clausulas.py' AS $$
{codigo}
import json
return json.dumps(fragmentar(texto, encabezado), ensure_ascii=False)
$$""")


@paso("5. Capa limpia: cláusulas y fragmentos")
def capa_limpia():
    esquema = ("ARRAY<STRUCT<numeral: STRING, nivel: INT, numeral_padre: STRING, titulo: STRING, texto: STRING, "
               "orden: INT, norma: STRING, contexto: STRING, caracteres: INT>>")
    sql(f"""CREATE OR REPLACE TABLE {CAT}.limpio.normas_clausulas AS
        WITH base AS (
            SELECT c.clave AS norma, c.titulo AS titulo_norma, c.tipo, c.estatus, c.norma_relacionada, c.idioma,
                   explode(from_json({CAT}.limpio.partir_clausulas(p.texto, c.clave, c.tipo), '{esquema}')) AS v
            FROM {CAT}.crudo.normas_parseadas p JOIN {CAT}.crudo.normas_catalogo c ON c.archivo = p.archivo
            WHERE p.error IS NULL)
        SELECT concat(norma, ' ', v.numeral) AS clausula_id, norma, titulo_norma, tipo, estatus, norma_relacionada,
               idioma, v.orden, v.numeral, v.nivel, v.numeral_padre, v.titulo, v.contexto, v.texto, v.caracteres,
               CAST(NULL AS STRING) AS modificada_por
        FROM base""")
    sql(f"""MERGE INTO {CAT}.limpio.normas_clausulas t
        USING (SELECT norma, norma_relacionada, numeral FROM {CAT}.limpio.normas_clausulas WHERE tipo = 'MODIFICACION') m
        ON t.norma = m.norma_relacionada AND t.numeral = m.numeral
        WHEN MATCHED THEN UPDATE SET t.modificada_por = m.norma""")
    sql(f"""CREATE OR REPLACE TABLE {CAT}.limpio.normas_fragmentos
        TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
        SELECT concat(clausula_id, ' #', pos) AS fragmento_id, clausula_id, norma, tipo, estatus, numeral, titulo,
               texto_busqueda
        FROM (SELECT c.*, posexplode(from_json({CAT}.limpio.fragmentar(c.texto,
                  concat(c.norma, ' (', c.estatus, ')', IF(c.contexto <> '', concat(' | ', c.contexto), ''),
                         ' › ', c.numeral, ' ', c.titulo)), 'ARRAY<STRING>')) AS (pos, texto_busqueda)
              FROM {CAT}.limpio.normas_clausulas c)""")
    for t in ["clausulas", "fragmentos"]:
        print(f"  {t}: {int(sql(f'SELECT COUNT(*) FROM {CAT}.limpio.normas_{t}')[0][0]):,}")


@paso("6. Buscador (Vector Search, qwen3-embedding multilingüe)")
def buscador():
    print("  esperando a que el endpoint esté listo…")
    while True:
        e = w.vector_search_endpoints.get_endpoint(ENDPOINT_VS)
        estado = e.endpoint_status.state.value if e.endpoint_status else "?"
        if estado == "ONLINE":
            break
        if estado in ("OFFLINE", "FAILED"):
            raise RuntimeError(f"endpoint {estado}")
        time.sleep(20)
    TIEMPOS["6a. endpoint listo tras (s)"] = round(time.time() - TIEMPOS.pop("_inicio_endpoint", time.time()), 1)
    try:
        w.vector_search_indexes.delete_index(INDICE)
        time.sleep(10)
    except Exception:
        pass
    w.vector_search_indexes.create_index(
        name=INDICE, endpoint_name=ENDPOINT_VS, primary_key="fragmento_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=f"{CAT}.limpio.normas_fragmentos", pipeline_type=PipelineType.TRIGGERED,
            embedding_source_columns=[EmbeddingSourceColumn(name="texto_busqueda", embedding_model_endpoint_name=MODELO_EMB)],
            columns_to_sync=["fragmento_id", "clausula_id", "norma", "tipo", "estatus", "numeral", "titulo", "texto_busqueda"]))
    print("  índice creado; sincronizando embeddings…")
    t = time.time()
    while True:
        i = w.vector_search_indexes.get_index(INDICE)
        st = i.status
        if st and st.ready:
            break
        if st and st.message and "FAILED" in st.message.upper():
            raise RuntimeError(st.message)
        time.sleep(20)
    TIEMPOS["6b. sincronización del índice (s)"] = round(time.time() - t, 1)
    print(f"  filas indexadas: {i.status.indexed_row_count}")


@paso("7. Examen del buscador")
def examen():
    return {"todas_las_normas": _examen(None), "solo_vigentes": _examen('{"estatus": "Vigente"}')}


def _examen(filtro):
    print(f"  — modalidad: {'solo vigentes' if filtro else 'todas las normas (incluye proyectos)'}")
    filas, aciertos, aciertos_norma, latencias = [], 0, 0, []
    for pregunta, norma, numeral in PREGUNTAS:
        t = time.time()
        r = w.vector_search_indexes.query_index(index_name=INDICE, columns=["norma", "numeral", "titulo"],
                                                query_text=pregunta, num_results=5, query_type="HYBRID",
                                                filters_json=filtro)
        lat = round((time.time() - t) * 1000)
        latencias.append(lat)
        res = [(x[0], x[1]) for x in (r.result.data_array or [])]
        ok, ok_norma, pos = calificar(res, norma, numeral)
        aciertos += ok; aciertos_norma += ok_norma
        filas.append(dict(pregunta=pregunta, esperada=f"{norma} {numeral}", acierto_top3=ok, norma_top3=ok_norma,
                          posicion=pos, latencia_ms=lat, top3=[f"{n} {c}" for n, c in res[:3]]))
        print(f"  {'✓' if ok else '✗'} [{lat} ms] {pregunta[:60]} → {res[:3]}")
    resumen = dict(plataforma="Databricks", fecha=datetime.now().isoformat(timespec="seconds"),
                   acierto_clausula_top3=f"{aciertos}/{len(PREGUNTAS)}", acierto_norma_top3=f"{aciertos_norma}/{len(PREGUNTAS)}",
                   latencia_ms_mediana=sorted(latencias)[len(latencias) // 2], preguntas=filas)
    print(f"  Cláusula exacta en top 3: {aciertos}/{len(PREGUNTAS)} · norma correcta en top 3: {aciertos_norma}/{len(PREGUNTAS)}"
          f" · latencia mediana {resumen['latencia_ms_mediana']} ms")
    return resumen


def apagar():
    try:
        w.vector_search_indexes.delete_index(INDICE); print("Índice borrado")
    except Exception as e:
        print("Índice:", str(e)[:120])
    try:
        w.vector_search_endpoints.delete_endpoint(ENDPOINT_VS); print("Endpoint de Vector Search borrado")
    except Exception as e:
        print("Endpoint:", str(e)[:120])
    w.warehouses.stop(WAREHOUSE); print("Warehouse farma_wh detenido")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if accion == "apagar":
        return apagar()
    if accion == "todo":
        iniciar_endpoint(); esquemas(); subir(); leer(); funciones(); capa_limpia(); buscador()
    if accion == "limpia":
        iniciar_endpoint(); funciones(); capa_limpia(); buscador()
    if accion == "indice":
        iniciar_endpoint(); buscador()
    resumen = examen()
    resumen["tiempos_s"] = TIEMPOS
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "fase2_databricks.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
