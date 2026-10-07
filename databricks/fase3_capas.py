"""Fase 3 en Databricks: carga de las tablas ficticias (crudo), capa limpia con tipos y controles de calidad,
y vistas de negocio (SQL compartido con Snowflake). También sube los PDF de los expedientes para la Fase 4.

Uso: python databricks/fase3_capas.py
"""
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase2_normas as F  # noqa: E402  (reutiliza conexión y sql())

RAIZ = Path(__file__).resolve().parents[1]
import capas  # noqa: E402
import esquema_tablas as E  # noqa: E402

CAT = F.CAT
T = {}
SALIDA = RAIZ / "docs" / "resultados" / "fase3" / "databricks"


def medir(nombre, f):
    t = time.time(); print(f"\n▶ {nombre}")
    r = f()
    T[nombre] = round(time.time() - t, 2); print(f"  ✓ {T[nombre]} s")
    return r


def cargar_crudo():
    F.sql(f"CREATE VOLUME IF NOT EXISTS {CAT}.crudo.datos COMMENT 'CSV de Laboratorios Altamira (ficticio)'")
    for t in E.tablas():
        with open(E.TABLAS_DIR / f"{t}.csv", "rb") as fh:
            F.w.files.upload(f"/Volumes/{CAT}/crudo/datos/{t}.csv", fh, overwrite=True)
        cols = ", ".join(f"{c} STRING" for c in E.columnas(t))
        F.sql(f"""CREATE OR REPLACE TABLE {CAT}.crudo.{t} AS
                  SELECT * FROM read_files('/Volumes/{CAT}/crudo/datos/{t}.csv', format => 'csv', header => true,
                                           schema => '{cols}', encoding => 'UTF-8', quote => '"', escape => '"')""")
        n_db = int(F.sql(f"SELECT COUNT(*) FROM {CAT}.crudo.{t}")[0][0])
        n_csv = sum(1 for _ in csv.reader(open(E.TABLAS_DIR / f"{t}.csv", encoding="utf-8"))) - 1
        print(f"  {t:18s} {n_db:6,} filas {'✓' if n_db == n_csv else f'✗ (CSV: {n_csv})'}")


def subir_expedientes():
    F.sql(f"CREATE VOLUME IF NOT EXISTS {CAT}.crudo.expedientes COMMENT 'PDF de los expedientes y oficios (ficticios)'")
    base = RAIZ / "datos" / "salida" / "pdf"
    pdfs = sorted(base.rglob("*.pdf"))
    for p in pdfs:
        with open(p, "rb") as fh:
            F.w.files.upload(f"/Volumes/{CAT}/crudo/expedientes/{p.relative_to(base).as_posix()}", fh, overwrite=True)
    print(f"  {len(pdfs)} PDF en el volume")


def capa_limpia():
    for t in E.tablas():
        F.sql(E.sql_limpia(t, f"{CAT}.crudo.{t}", f"{CAT}.limpio.{t}", "databricks"))
    F.sql(f"CREATE OR REPLACE TABLE {CAT}.limpio.calidad_datos AS {capas.sql_calidad(f'{CAT}.crudo', f'{CAT}.limpio')}")
    r = F.sql(f"SELECT resultado, COUNT(*) FROM {CAT}.limpio.calidad_datos GROUP BY 1")
    print("  controles de calidad:", {a: b for a, b in r})
    for f in F.sql(f"SELECT * FROM {CAT}.limpio.calidad_datos WHERE resultado <> 'OK'"):
        print("   FALLA:", f)


def negocio():
    for s in capas.sentencias_negocio(f"{CAT}.limpio", f"{CAT}.negocio"):
        F.sql(s)


def exportar():
    for v in capas.VISTAS_NEGOCIO:
        t = time.time()
        r = F.w.statement_execution.execute_statement(statement=f"SELECT * FROM {CAT}.negocio.{v}",
                                                      warehouse_id=F.WAREHOUSE, wait_timeout="50s")
        T[f"consulta {v} (ms)"] = round((time.time() - t) * 1000)
        columnas = [c.name for c in r.manifest.schema.columns]
        filas = r.result.data_array or []
        capas.guardar(SALIDA / f"{v}.csv", columnas, filas)
        print(f"  {v:24s} {len(filas):5} filas · {T[f'consulta {v} (ms)']} ms")


def main():
    try:
        medir("1. Capa cruda (14 tablas)", cargar_crudo)
        medir("2. PDF de expedientes al volume", subir_expedientes)
        medir("3. Capa limpia + controles de calidad", capa_limpia)
        medir("4. Capa de negocio (SQL compartido)", negocio)
        medir("5. Consultar y exportar vistas", exportar)
        (SALIDA / "tiempos.json").write_text(json.dumps(T, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        F.w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
