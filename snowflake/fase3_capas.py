"""Fase 3 en Snowflake: carga de las tablas ficticias (crudo), capa limpia con tipos y controles de calidad,
y vistas de negocio (SQL compartido con Databricks). También sube los PDF de los expedientes para la Fase 4.

Uso: python snowflake/fase3_capas.py
"""
import csv
import json
import sys
import time
from pathlib import Path

import snowflake.connector

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "compartido"))
import capas  # noqa: E402
import esquema_tablas as E  # noqa: E402

BD = "OBED_FARMACEUTICA"
T = {}
SALIDA = RAIZ / "docs" / "resultados" / "fase3" / "snowflake"


def medir(nombre, f, *a):
    t = time.time(); print(f"\n▶ {nombre}")
    r = f(*a)
    T[nombre] = round(time.time() - t, 2); print(f"  ✓ {T[nombre]} s")
    return r


def cargar_crudo(cur):
    cur.execute(f"CREATE STAGE IF NOT EXISTS {BD}.CRUDO.DATOS COMMENT = 'CSV de Laboratorios Altamira (ficticio)'")
    cur.execute(f"""CREATE FILE FORMAT IF NOT EXISTS {BD}.CRUDO.CSV_ALTAMIRA TYPE = CSV SKIP_HEADER = 1
                    FIELD_OPTIONALLY_ENCLOSED_BY = '"' ENCODING = 'UTF8' EMPTY_FIELD_AS_NULL = FALSE""")
    for t in E.tablas():
        ruta = (E.TABLAS_DIR / f"{t}.csv").as_posix()
        cur.execute(f"PUT 'file://{ruta}' @{BD}.CRUDO.DATOS AUTO_COMPRESS = TRUE OVERWRITE = TRUE")
        cols = ", ".join(f"{c} STRING" for c in E.columnas(t))
        cur.execute(f"CREATE OR REPLACE TABLE {BD}.CRUDO.{t} ({cols})")
        cur.execute(f"COPY INTO {BD}.CRUDO.{t} FROM @{BD}.CRUDO.DATOS/{t}.csv.gz "
                    f"FILE_FORMAT = (FORMAT_NAME = '{BD}.CRUDO.CSV_ALTAMIRA') ON_ERROR = 'ABORT_STATEMENT'")
        n_db = cur.execute(f"SELECT COUNT(*) FROM {BD}.CRUDO.{t}").fetchone()[0]
        n_csv = sum(1 for _ in csv.reader(open(E.TABLAS_DIR / f"{t}.csv", encoding="utf-8"))) - 1
        print(f"  {t:18s} {n_db:6,} filas {'✓' if n_db == n_csv else f'✗ (CSV: {n_csv})'}")


def subir_expedientes(cur):
    cur.execute(f"""CREATE STAGE IF NOT EXISTS {BD}.CRUDO.EXPEDIENTES DIRECTORY = (ENABLE = TRUE)
                    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE') COMMENT = 'PDF de los expedientes y oficios (ficticios)'""")
    pdfs = sorted((RAIZ / "datos" / "salida" / "pdf").rglob("*.pdf"))
    for p in pdfs:
        rel = p.relative_to(RAIZ / "datos" / "salida" / "pdf").parent.as_posix()
        cur.execute(f"PUT 'file://{p.as_posix()}' @{BD}.CRUDO.EXPEDIENTES/{rel}/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
    cur.execute(f"ALTER STAGE {BD}.CRUDO.EXPEDIENTES REFRESH")
    print(f"  {cur.execute(f'SELECT COUNT(*) FROM DIRECTORY(@{BD}.CRUDO.EXPEDIENTES)').fetchone()[0]} PDF en el stage")


def capa_limpia(cur):
    for t in E.tablas():
        cur.execute(E.sql_limpia(t, f"{BD}.CRUDO.{t}", f"{BD}.LIMPIO.{t}", "snowflake"))
    cur.execute(f"CREATE OR REPLACE TABLE {BD}.LIMPIO.CALIDAD_DATOS AS {capas.sql_calidad(f'{BD}.CRUDO', f'{BD}.LIMPIO')}")
    r = cur.execute(f"SELECT resultado, COUNT(*) FROM {BD}.LIMPIO.CALIDAD_DATOS GROUP BY 1").fetchall()
    print("  controles de calidad:", dict(r))
    for f in cur.execute(f"SELECT * FROM {BD}.LIMPIO.CALIDAD_DATOS WHERE resultado <> 'OK'").fetchall():
        print("   FALLA:", f)


def negocio(cur):
    for s in capas.sentencias_negocio(f"{BD}.LIMPIO", f"{BD}.NEGOCIO"):
        cur.execute(s)


def exportar(cur):
    for v in capas.VISTAS_NEGOCIO:
        t = time.time()
        filas = cur.execute(f"SELECT * FROM {BD}.NEGOCIO.{v}").fetchall()
        T[f"consulta {v} (ms)"] = round((time.time() - t) * 1000)
        capas.guardar(SALIDA / f"{v}.csv", [d[0] for d in cur.description], filas)
        print(f"  {v:24s} {len(filas):5} filas · {T[f'consulta {v} (ms)']} ms")


def main():
    con = snowflake.connector.connect(connection_name="obed_farma")
    cur = con.cursor()
    cur.execute("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase3'")
    try:
        medir("1. Capa cruda (14 tablas)", cargar_crudo, cur)
        medir("2. PDF de expedientes al stage", subir_expedientes, cur)
        medir("3. Capa limpia + controles de calidad", capa_limpia, cur)
        medir("4. Capa de negocio (SQL compartido)", negocio, cur)
        medir("5. Consultar y exportar vistas", exportar, cur)
        (SALIDA / "tiempos.json").write_text(json.dumps(T, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        try:
            cur.execute("ALTER WAREHOUSE FARMA_WH SUSPEND")
        except snowflake.connector.errors.ProgrammingError:
            pass   # ya estaba suspendido (p. ej., consultas resueltas desde el caché de resultados)
        con.close()


if __name__ == "__main__":
    main()
