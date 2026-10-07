"""Fase 2 en Snowflake: carga de normas, lectura con AI_PARSE_DOCUMENT, partición por cláusula,
buscador Cortex Search y examen. Mide el tiempo de cada paso.

Uso:
    python snowflake/fase2_normas.py todo        # todos los pasos
    python snowflake/fase2_normas.py examen      # solo el examen del buscador
    python snowflake/fase2_normas.py apagar      # suspende buscador y warehouse
"""
import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import snowflake.connector

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "compartido"))
from examen_buscador import PREGUNTAS, calificar  # noqa: E402

BD = "OBED_FARMACEUTICA"
BUSCADOR = f"{BD}.IA.BUSCADOR_NORMAS"
TIEMPOS = {}
RESULTADOS = RAIZ / "docs" / "resultados"


def paso(nombre):
    def deco(f):
        def envoltura(cur, *a, **k):
            t = time.time()
            print(f"\n▶ {nombre}")
            r = f(cur, *a, **k)
            TIEMPOS[nombre] = round(time.time() - t, 2)
            print(f"  ✓ {TIEMPOS[nombre]} s")
            return r
        return envoltura
    return deco


@paso("1. Esquemas y stage")
def esquemas(cur):
    for s in ["CRUDO", "LIMPIO", "NEGOCIO", "IA"]:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {BD}.{s}")
    cur.execute(f"""CREATE STAGE IF NOT EXISTS {BD}.CRUDO.NORMAS
                    DIRECTORY = (ENABLE = TRUE) ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE')
                    COMMENT = 'PDF de normas (DOF, leyes, guías ICH)'""")


@paso("2. Subir PDF al stage")
def subir(cur):
    catalogo = list(csv.DictReader(open(RAIZ / "compartido" / "catalogo_normas.csv", encoding="utf-8")))
    for r in catalogo:
        ruta = (RAIZ / "normas" / r["archivo"]).as_posix()
        cur.execute(f"PUT 'file://{ruta}' @{BD}.CRUDO.NORMAS AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
    cur.execute(f"ALTER STAGE {BD}.CRUDO.NORMAS REFRESH")
    cur.execute(f"""CREATE OR REPLACE TABLE {BD}.CRUDO.NORMAS_CATALOGO (
        archivo STRING, clave STRING, titulo STRING, tipo STRING, estatus STRING, fecha_dof DATE,
        norma_relacionada STRING, idioma STRING, fuente STRING)""")
    cur.executemany(f"INSERT INTO {BD}.CRUDO.NORMAS_CATALOGO VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    [(r["archivo"], r["clave"], r["titulo"], r["tipo"], r["estatus"], r["fecha_dof"] or None,
                      r["norma_relacionada"] or None, r["idioma"], r["fuente"]) for r in catalogo])
    print(f"  {len(catalogo)} archivos")


@paso("3. Lectura con IA (AI_PARSE_DOCUMENT, modo LAYOUT)")
def leer(cur):
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {BD}.CRUDO.NORMAS_PARSEADAS (
        archivo STRING, paginas INT, texto STRING, resultado VARIANT, segundos FLOAT, error STRING,
        procesado_en TIMESTAMP_NTZ)""")
    hechos = {r[0] for r in cur.execute(f"SELECT archivo FROM {BD}.CRUDO.NORMAS_PARSEADAS WHERE error IS NULL").fetchall()}
    archivos = [r[0] for r in cur.execute(f"SELECT archivo FROM {BD}.CRUDO.NORMAS_CATALOGO ORDER BY archivo").fetchall()]
    por_doc = {}
    for a in archivos:
        if a in hechos:
            continue
        t = time.time()
        try:
            cur.execute(f"""INSERT INTO {BD}.CRUDO.NORMAS_PARSEADAS
                SELECT %s, r:metadata:pageCount::INT,
                       ARRAY_TO_STRING(TRANSFORM(r:pages, p -> p:content::STRING), '\n\n'),
                       r, NULL, NULL, CURRENT_TIMESTAMP()
                FROM (SELECT AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.NORMAS', %s),
                                               {{'mode': 'LAYOUT', 'page_split': true}}) AS r)""", (a, a))
            seg = round(time.time() - t, 1)
            cur.execute(f"UPDATE {BD}.CRUDO.NORMAS_PARSEADAS SET segundos = %s WHERE archivo = %s", (seg, a))
            por_doc[a] = seg
            print(f"  {a}: {seg} s")
        except Exception as e:
            cur.execute(f"INSERT INTO {BD}.CRUDO.NORMAS_PARSEADAS (archivo, error, procesado_en) VALUES (%s, %s, CURRENT_TIMESTAMP())",
                        (a, str(e)[:2000]))
            print(f"  {a}: ERROR {str(e)[:200]}")
    TIEMPOS["3a. segundos por documento"] = por_doc


@paso("4. Funciones de partición (mismo código que Databricks)")
def funciones(cur):
    codigo = (RAIZ / "compartido" / "partir_clausulas.py").read_text(encoding="utf-8")
    cur.execute(f"""CREATE OR REPLACE FUNCTION {BD}.LIMPIO.PARTIR_CLAUSULAS(texto STRING, norma STRING, tipo STRING)
        RETURNS ARRAY LANGUAGE PYTHON RUNTIME_VERSION = '3.11' HANDLER = 'partir'
        COMMENT = 'compartido/partir_clausulas.py' AS $${codigo}$$""")
    cur.execute(f"""CREATE OR REPLACE FUNCTION {BD}.LIMPIO.FRAGMENTAR(texto STRING, encabezado STRING)
        RETURNS ARRAY LANGUAGE PYTHON RUNTIME_VERSION = '3.11' HANDLER = 'fragmentar_udf'
        COMMENT = 'compartido/partir_clausulas.py' AS $${codigo}$$""")


@paso("5. Capa limpia: cláusulas y fragmentos")
def capa_limpia(cur):
    cur.execute(f"""CREATE OR REPLACE TABLE {BD}.LIMPIO.NORMAS_CLAUSULAS AS
        WITH base AS (
            SELECT c.clave AS norma, c.titulo AS titulo_norma, c.tipo, c.estatus, c.norma_relacionada, c.idioma,
                   f.value AS v
            FROM {BD}.CRUDO.NORMAS_PARSEADAS p
            JOIN {BD}.CRUDO.NORMAS_CATALOGO c ON c.archivo = p.archivo,
            LATERAL FLATTEN(input => {BD}.LIMPIO.PARTIR_CLAUSULAS(p.texto, c.clave, c.tipo)) f
            WHERE p.error IS NULL)
        SELECT norma || ' ' || v:numeral::STRING AS clausula_id, norma, titulo_norma, tipo, estatus, norma_relacionada, idioma,
               v:orden::INT AS orden, v:numeral::STRING AS numeral, v:nivel::INT AS nivel,
               v:numeral_padre::STRING AS numeral_padre, v:titulo::STRING AS titulo, v:contexto::STRING AS contexto,
               v:texto::STRING AS texto, v:caracteres::INT AS caracteres
        FROM base""")
    # numerales de la NOM-059 que tienen modificación publicada (DOF 19/03/2025)
    cur.execute(f"""ALTER TABLE {BD}.LIMPIO.NORMAS_CLAUSULAS ADD COLUMN IF NOT EXISTS modificada_por STRING""")
    cur.execute(f"""UPDATE {BD}.LIMPIO.NORMAS_CLAUSULAS t SET modificada_por = m.norma
        FROM {BD}.LIMPIO.NORMAS_CLAUSULAS m
        WHERE m.tipo = 'MODIFICACION' AND t.norma = m.norma_relacionada AND t.numeral = m.numeral""")
    cur.execute(f"""CREATE OR REPLACE TABLE {BD}.LIMPIO.NORMAS_FRAGMENTOS AS
        SELECT c.clausula_id || ' #' || f.index AS fragmento_id, c.clausula_id, c.norma, c.tipo, c.estatus,
               c.numeral, c.titulo, f.value::STRING AS texto_busqueda
        FROM {BD}.LIMPIO.NORMAS_CLAUSULAS c,
        LATERAL FLATTEN(input => {BD}.LIMPIO.FRAGMENTAR(c.texto,
            c.norma || ' (' || c.estatus || ')' || IFF(c.contexto <> '', ' | ' || c.contexto, '') || ' › ' || c.numeral || ' ' || c.titulo)) f""")
    for t in ["CLAUSULAS", "FRAGMENTOS"]:
        print(f"  {t}: {cur.execute(f'SELECT COUNT(*) FROM {BD}.LIMPIO.NORMAS_{t}').fetchone()[0]:,}")


@paso("6. Buscador (Cortex Search, arctic-embed-l-v2.0 multilingüe)")
def buscador(cur):
    cur.execute(f"""CREATE OR REPLACE CORTEX SEARCH SERVICE {BUSCADOR}
        ON texto_busqueda
        ATTRIBUTES norma, tipo, estatus
        WAREHOUSE = FARMA_WH
        TARGET_LAG = '7 days'
        EMBEDDING_MODEL = 'snowflake-arctic-embed-l-v2.0'
        COMMENT = 'Biblioteca normativa: NOM, leyes y guías por cláusula'
        AS SELECT fragmento_id, clausula_id, norma, tipo, estatus, numeral, titulo, texto_busqueda
           FROM {BD}.LIMPIO.NORMAS_FRAGMENTOS""")


@paso("7. Examen del buscador")
def examen(cur):
    return {"todas_las_normas": _examen(cur, None),
            "solo_vigentes": _examen(cur, {"@eq": {"estatus": "Vigente"}})}


def _examen(cur, filtro):
    print(f"  — modalidad: {'solo vigentes' if filtro else 'todas las normas (incluye proyectos)'}")
    filas, aciertos, aciertos_norma, latencias = [], 0, 0, []
    for pregunta, norma, numeral in PREGUNTAS:
        q = {"query": pregunta, "columns": ["norma", "numeral", "titulo"], "limit": 5}
        if filtro:
            q["filter"] = filtro
        consulta = json.dumps(q, ensure_ascii=False)
        t = time.time()
        r = json.loads(cur.execute("SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s, %s)", (BUSCADOR, consulta)).fetchone()[0])
        lat = round((time.time() - t) * 1000)
        latencias.append(lat)
        res = [(x["norma"], x["numeral"]) for x in r["results"]]
        ok, ok_norma, pos = calificar(res, norma, numeral)
        aciertos += ok; aciertos_norma += ok_norma
        filas.append(dict(pregunta=pregunta, esperada=f"{norma} {numeral}", acierto_top3=ok, norma_top3=ok_norma,
                          posicion=pos, latencia_ms=lat, top3=[f"{n} {c}" for n, c in res[:3]]))
        print(f"  {'✓' if ok else '✗'} [{lat} ms] {pregunta[:60]} → {res[:3]}")
    resumen = dict(plataforma="Snowflake", fecha=datetime.now().isoformat(timespec="seconds"),
                   acierto_clausula_top3=f"{aciertos}/{len(PREGUNTAS)}", acierto_norma_top3=f"{aciertos_norma}/{len(PREGUNTAS)}",
                   latencia_ms_mediana=sorted(latencias)[len(latencias) // 2], preguntas=filas)
    print(f"  Cláusula exacta en top 3: {aciertos}/{len(PREGUNTAS)} · norma correcta en top 3: {aciertos_norma}/{len(PREGUNTAS)}"
          f" · latencia mediana {resumen['latencia_ms_mediana']} ms")
    return resumen


def apagar(cur):
    try:
        cur.execute(f"ALTER CORTEX SEARCH SERVICE {BUSCADOR} SUSPEND SERVING")
        print("Buscador: servicio suspendido")
    except Exception as e:
        print("Buscador:", str(e)[:150])
    cur.execute("ALTER WAREHOUSE FARMA_WH SUSPEND") if cur.execute(
        "SHOW WAREHOUSES LIKE 'FARMA_WH'").fetchone()[1] != "SUSPENDED" else None
    print("Warehouse FARMA_WH suspendido")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    con = snowflake.connector.connect(connection_name="obed_farma")
    cur = con.cursor()
    cur.execute("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase2'")
    try:
        if accion == "apagar":
            apagar(cur); return
        if accion == "reanudar":
            cur.execute(f"ALTER CORTEX SEARCH SERVICE {BUSCADOR} RESUME SERVING"); return
        if accion == "todo":
            esquemas(cur); subir(cur); leer(cur); funciones(cur); capa_limpia(cur); buscador(cur)
        if accion == "limpia":
            funciones(cur); capa_limpia(cur); buscador(cur)
        resumen = examen(cur)
        resumen["tiempos_s"] = TIEMPOS
        RESULTADOS.mkdir(parents=True, exist_ok=True)
        (RESULTADOS / "fase2_snowflake.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        con.close()


if __name__ == "__main__":
    main()
