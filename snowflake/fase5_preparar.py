"""Fase 5 en Snowflake: estado operativo de la app (esquema APP), versiones corregidas y reinicio de la demo.

Uso:
    python snowflake/fase5_preparar.py preparar        # esquema APP, tablas, vistas y subir correcciones al stage
    python snowflake/fase5_preparar.py reiniciar       # deja la demo en cero (expediente v1 bloqueado, sin envíos)
    python snowflake/fase5_preparar.py correcciones    # procesa las 9 correcciones con la bandeja (prueba del candado)
    python snowflake/fase5_preparar.py estado          # muestra el candado
"""
import csv
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "snowflake"))
import fase4_bandeja as B  # noqa: E402

BD = B.BD
PDF = RAIZ / "datos" / "salida" / "pdf"
TRAMITE_DEMO = "TR-2026-032"


def sql_app():
    texto = (RAIZ / "compartido" / "sql" / "app.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{BD}.LIMPIO").replace("{N}", f"{BD}.NEGOCIO").replace("{A}", f"{BD}.APP")
    return [s.strip() for s in texto.split(";") if s.strip()]


def preparar(cur):
    cur.execute(f"CREATE SCHEMA IF NOT EXISTS {BD}.APP COMMENT = 'Estado operativo de la app (cargas, envíos)'")
    cur.execute(f"""CREATE STAGE IF NOT EXISTS {BD}.APP.CAPTURAS DIRECTORY = (ENABLE = TRUE)
                    ENCRYPTION = (TYPE = 'SNOWFLAKE_SSE') COMMENT = 'Capturas de pantalla del agente de envío'""")
    for s in sql_app():
        cur.execute(s)
    for p in sorted((PDF / "TR-2026-032_sitagliptina" / "correcciones").glob("*.pdf")):
        cur.execute(f"PUT 'file://{p.as_posix()}' @{BD}.CRUDO.EXPEDIENTES/TR-2026-032_sitagliptina/correcciones/ "
                    "AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
    cur.execute(f"ALTER STAGE {BD}.CRUDO.EXPEDIENTES REFRESH")
    print("  esquema APP, vistas y correcciones listas")


def reiniciar(cur):
    cur.execute(f"DELETE FROM {BD}.APP.CARGAS")
    cur.execute(f"DELETE FROM {BD}.APP.ENVIOS")
    filas = []
    for r in csv.DictReader(open(PDF / "INDICE.csv", encoding="utf-8")):
        if r["requisito_id"] and r["origen"] == "Expediente de la empresa":
            filas.append((r["tramite_id"], r["requisito_id"], r["archivo"].removeprefix("pdf/"), 1, "Expediente inicial"))
    cur.executemany(f"""INSERT INTO {BD}.APP.CARGAS (tramite_id, requisito_id, archivo, version, cargado_en, cargado_por, origen)
                        VALUES (%s, %s, %s, %s, '2026-09-30 10:00:00', 'demo', %s)""", filas)
    print(f"  demo reiniciada: {len(filas)} documentos v1, sin envíos")


def cargar_documento(cur, archivo, cargado_por="demo"):
    """Lo que hace la bandeja al subir un documento: leer, extraer, ubicar en el CTD según la IA y registrar la carga."""
    B.procesar_documento(archivo)
    B.aplanar(cur)
    r = cur.execute(f"""SELECT x.tramite_id, MIN(q.requisito_id), x.tipo_documento
        FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS x
        LEFT JOIN {BD}.LIMPIO.REQUISITOS_CTD q ON q.nombre = x.tipo_documento
        WHERE x.archivo = %s GROUP BY x.tramite_id, x.tipo_documento""", (archivo,)).fetchone()
    if not r or not r[1]:
        print(f"  {archivo}: la IA no pudo ubicarlo en el CTD ({r[2] if r else 'sin respuesta'})")
        return None
    version = cur.execute(f"SELECT COALESCE(MAX(version), 0) + 1 FROM {BD}.APP.CARGAS WHERE tramite_id = %s AND requisito_id = %s",
                          (r[0], r[1])).fetchone()[0]
    cur.execute(f"""INSERT INTO {BD}.APP.CARGAS SELECT %s, %s, %s, %s, CURRENT_TIMESTAMP(), %s, 'Bandeja de carga'""",
                (r[0], r[1], archivo, version, cargado_por))
    return r[1], r[2], version


def correcciones(cur):
    t = time.time()
    for p in sorted((PDF / "TR-2026-032_sitagliptina" / "correcciones").glob("*.pdf")):
        print("  ", cargar_documento(cur, f"TR-2026-032_sitagliptina/correcciones/{p.name}"))
    print(f"  {round(time.time() - t, 1)} s")


def estado(cur):
    for r in cur.execute(f"""SELECT tramite_id, producto, requisitos, completos, con_hallazgos, faltantes, cobertura_pct, candado
                             FROM {BD}.NEGOCIO.CANDADO_ENVIO WHERE tramite_id = '{TRAMITE_DEMO}'""").fetchall():
        print("  candado:", r)
    for r in cur.execute(f"""SELECT seccion_ctd, nombre_requisito, version, hallazgos_abiertos, estatus_efectivo
                             FROM {BD}.NEGOCIO.EXPEDIENTE_ESTADO WHERE tramite_id = '{TRAMITE_DEMO}'
                             AND estatus_efectivo <> 'Validado' ORDER BY seccion_ctd""").fetchall():
        print("   ", r)


def correcciones_cargadas(cur):
    """Atajo de demo: registra las 9 correcciones (ya analizadas por la IA) como versión 2, sin reprocesarlas."""
    filas = [(r["tramite_id"], r["requisito_id"], r["archivo"].removeprefix("pdf/"))
             for r in csv.DictReader(open(PDF / "INDICE.csv", encoding="utf-8")) if r["origen"] == "Corrección (v2)"]
    cur.executemany(f"""INSERT INTO {BD}.APP.CARGAS (tramite_id, requisito_id, archivo, version, cargado_en, cargado_por, origen)
                        VALUES (%s, %s, %s, 2, CURRENT_TIMESTAMP(), 'demo', 'Bandeja de carga')""", filas)
    print(f"  {len(filas)} correcciones registradas")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "estado"
    con = B.conectar(); cur = con.cursor()
    try:
        {"preparar": lambda: (preparar(cur), reiniciar(cur), estado(cur)),
         "reiniciar": lambda: (reiniciar(cur), estado(cur)),
         "correcciones": lambda: (correcciones(cur), estado(cur)),
         "estado": lambda: estado(cur),
         "correcciones_cargadas": lambda: (correcciones_cargadas(cur), estado(cur))}[accion]()
    finally:
        try:
            cur.execute("ALTER WAREHOUSE FARMA_WH SUSPEND")
        except Exception:
            pass
        con.close()


if __name__ == "__main__":
    main()
