"""Fase 5 en Databricks: estado operativo de la app (esquema app), versiones corregidas y reinicio de la demo.

Uso:
    python databricks/fase5_preparar.py preparar        # esquema app, tablas, vistas, volume de capturas y correcciones
    python databricks/fase5_preparar.py reiniciar       # deja la demo en cero (expediente v1 bloqueado, sin envíos)
    python databricks/fase5_preparar.py correcciones    # procesa las 9 correcciones con la bandeja (prueba del candado)
    python databricks/fase5_preparar.py estado
"""
import csv
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "databricks"))
import fase4_bandeja as B  # noqa: E402
from databricks.sdk.service.sql import StatementParameterListItem as Param  # noqa: E402

F = B.F
CAT = B.CAT
PDF = RAIZ / "datos" / "salida" / "pdf"
TRAMITE_DEMO = "TR-2026-032"


def sql_app():
    texto = (RAIZ / "compartido" / "sql" / "app.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{CAT}.limpio").replace("{N}", f"{CAT}.negocio").replace("{A}", f"{CAT}.app")
    return [s.strip() for s in texto.split(";") if s.strip()]


def preparar():
    F.sql(f"CREATE SCHEMA IF NOT EXISTS {CAT}.app COMMENT 'Estado operativo de la app (cargas, envíos)'")
    F.sql(f"CREATE VOLUME IF NOT EXISTS {CAT}.app.capturas COMMENT 'Capturas de pantalla del agente de envío'")
    for s in sql_app():
        F.sql(s)
    for p in sorted((PDF / "TR-2026-032_sitagliptina" / "correcciones").glob("*.pdf")):
        with open(p, "rb") as fh:
            F.w.files.upload(f"{B.VOL}/TR-2026-032_sitagliptina/correcciones/{p.name}", fh, overwrite=True)
    print("  esquema app, vistas, volume de capturas y correcciones listas")


def reiniciar():
    F.sql(f"DELETE FROM {CAT}.app.cargas")
    F.sql(f"DELETE FROM {CAT}.app.envios")
    filas = [(r["tramite_id"], r["requisito_id"], r["archivo"].removeprefix("pdf/"))
             for r in csv.DictReader(open(PDF / "INDICE.csv", encoding="utf-8"))
             if r["requisito_id"] and r["origen"] == "Expediente de la empresa"]
    valores = ",".join(f"('{t}', '{q}', '{a}', 1, TIMESTAMP'2026-09-30 10:00:00', 'demo', 'Expediente inicial')" for t, q, a in filas)
    F.sql(f"INSERT INTO {CAT}.app.cargas VALUES {valores}")
    print(f"  demo reiniciada: {len(filas)} documentos v1, sin envíos")


def cargar_documento(archivo, cargado_por="demo"):
    B.procesar_documento(archivo)
    B.aplanar()
    a = [Param(name="a", value=archivo)]
    r = F.sql(f"""SELECT x.tramite_id, MIN(q.requisito_id), x.tipo_documento FROM {CAT}.limpio.documentos_extraidos x
                  LEFT JOIN {CAT}.limpio.requisitos_ctd q ON q.nombre = x.tipo_documento
                  WHERE x.archivo = :a GROUP BY x.tramite_id, x.tipo_documento""", a)
    if not r or not r[0][1]:
        print(f"  {archivo}: la IA no pudo ubicarlo en el CTD ({r[0][2] if r else 'sin respuesta'})")
        return None
    tramite, req, tipo = r[0]
    F.sql(f"""INSERT INTO {CAT}.app.cargas
              SELECT :t, :q, :a, COALESCE((SELECT MAX(version) FROM {CAT}.app.cargas WHERE tramite_id = :t AND requisito_id = :q), 0) + 1,
                     current_timestamp(), :u, 'Bandeja de carga'""",
          a + [Param(name="t", value=tramite), Param(name="q", value=req), Param(name="u", value=cargado_por)])
    return req, tipo


def correcciones():
    t = time.time()
    for p in sorted((PDF / "TR-2026-032_sitagliptina" / "correcciones").glob("*.pdf")):
        print("  ", cargar_documento(f"TR-2026-032_sitagliptina/correcciones/{p.name}"))
    print(f"  {round(time.time() - t, 1)} s")


def estado():
    for r in F.sql(f"""SELECT tramite_id, producto, requisitos, completos, con_hallazgos, faltantes, cobertura_pct, candado
                       FROM {CAT}.negocio.candado_envio WHERE tramite_id = '{TRAMITE_DEMO}'"""):
        print("  candado:", r)
    for r in F.sql(f"""SELECT seccion_ctd, nombre_requisito, version, hallazgos_abiertos, estatus_efectivo
                       FROM {CAT}.negocio.expediente_estado WHERE tramite_id = '{TRAMITE_DEMO}'
                       AND estatus_efectivo <> 'Validado' ORDER BY seccion_ctd"""):
        print("   ", r)


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    try:
        {"preparar": lambda: (preparar(), reiniciar(), estado()),
         "reiniciar": lambda: (reiniciar(), estado()),
         "correcciones": lambda: (correcciones(), estado()),
         "estado": estado}[accion]()
    finally:
        F.w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
