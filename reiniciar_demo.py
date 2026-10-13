"""Deja toda la demo en cero: Snowflake, Databricks y el portal simulado local.

Uso:
    python reiniciar_demo.py                 # todo
    python reiniciar_demo.py snowflake       # solo una parte (snowflake | databricks | portal)
    python reiniciar_demo.py --listo         # además deja las 9 correcciones cargadas (candado abierto, listo para enviar)

En cero significa: expediente inicial de la sitagliptina (8 documentos con hallazgos y 1 faltante), sin envíos,
prevenciones, alertas, pre-auditorías ni evaluaciones de versiones; el portal sin solicitudes, avisos ni correos.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
for p in ("app/comun", "compartido", "databricks"):
    sys.path.insert(0, str(RAIZ / p))


def snowflake():
    from snowflake.snowpark import Session
    from datos_snowflake import DatosSnowflake
    s = Session.builder.config("connection_name", "obed_farma").create()
    try:
        DatosSnowflake(s).reiniciar_demo()
    finally:
        try:
            s.sql("ALTER WAREHOUSE FARMA_WH SUSPEND").collect()
        except Exception:
            pass
        s.close()
    print("  Snowflake en cero")


def databricks():
    import fase2_normas as F
    from datos_databricks import DatosDatabricks
    try:
        DatosDatabricks(F.w, F.WAREHOUSE).reiniciar_demo()
    finally:
        F.w.warehouses.stop(F.WAREHOUSE)
    print("  Databricks en cero")


def portal():
    db = RAIZ / "portal_simulado" / "datos" / "portal.db"
    if db.exists():
        with sqlite3.connect(db) as c:
            for t in ["archivos", "notificaciones", "correos_salientes", "solicitudes"]:
                c.execute(f"DELETE FROM {t}")
    print("  portal simulado en cero")


def listo():
    """Atajo para demostrar el envío sin pasar por la bandeja: registra las 9 correcciones ya analizadas."""
    for plataforma in ("snowflake", "databricks"):
        if plataforma in PARTES:
            subprocess.run([sys.executable, str(RAIZ / plataforma / "fase5_preparar.py"), "correcciones_cargadas"], check=True)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    PARTES = args or ["snowflake", "databricks", "portal"]
    for parte in PARTES:
        {"snowflake": snowflake, "databricks": databricks, "portal": portal}[parte]()
    if "--listo" in sys.argv:
        listo()
