"""Publica la app (Vista 2) en Streamlit in Snowflake.

Uso: python snowflake/desplegar_app.py
"""
import subprocess
import sys
import time
from pathlib import Path

import snowflake.connector

RAIZ = Path(__file__).resolve().parents[1]
BD = "OBED_FARMACEUTICA"
APP = f"{BD}.APP.EXPEDIENTE_CTD"
STAGE = f"{BD}.APP.STREAMLIT_SRC"


def main():
    subprocess.run([sys.executable, str(RAIZ / "app" / "empaquetar.py")], check=True)
    paquete = RAIZ / "app" / "_paquete" / "snowflake"
    con = snowflake.connector.connect(connection_name="obed_farma")
    cur = con.cursor()
    t = time.time()
    try:
        cur.execute(f"CREATE STAGE IF NOT EXISTS {STAGE} DIRECTORY = (ENABLE = TRUE) COMMENT = 'Código de la app Streamlit'")
        for p in paquete.iterdir():
            cur.execute(f"PUT 'file://{p.as_posix()}' @{STAGE}/expediente_ctd/ AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
        # procedimiento que ejecuta en segundo plano los trabajos de IA con el mismo código de la app
        cur.execute(f"""CREATE TABLE IF NOT EXISTS {BD}.APP.TRABAJOS (
            trabajo_id STRING, tipo STRING, tramite_id STRING, parametros STRING, estatus STRING, paso STRING,
            resultado STRING, error STRING, solicitado_por STRING, creado_en TIMESTAMP, actualizado_en TIMESTAMP)""")
        modulos = ["trabajos_sf.py", "datos_snowflake.py", "trabajos.py", "ciclo_prevencion.py", "consultas.py", "memoria.py",
                   "preauditoria.py", "versiones.py", "extraccion.py", "oficio.py", "tipos_documento.json"]
        imports = ", ".join(f"'@{STAGE}/expediente_ctd/{m}'" for m in modulos)
        cur.execute(f"""CREATE OR REPLACE PROCEDURE {BD}.APP.EJECUTAR_TRABAJO(TRABAJO_ID STRING)
                        RETURNS STRING LANGUAGE PYTHON RUNTIME_VERSION = '3.11'
                        PACKAGES = ('snowflake-snowpark-python') IMPORTS = ({imports})
                        HANDLER = 'trabajos_sf.principal'
                        COMMENT = 'Trabajos de IA en segundo plano (bandeja, versiones, pre-auditoría)'
                        EXECUTE AS OWNER""")
        cur.execute(f"""CREATE OR REPLACE PROCEDURE {BD}.APP.PROCESAR_COLA()
                        RETURNS STRING LANGUAGE PYTHON RUNTIME_VERSION = '3.11'
                        PACKAGES = ('snowflake-snowpark-python') IMPORTS = ({imports})
                        HANDLER = 'trabajos_sf.cola'
                        COMMENT = 'Ejecuta los trabajos de IA en cola'
                        EXECUTE AS OWNER""")
        # la tarea corre en el servidor aunque se cierre la app; la app la despierta con EXECUTE TASK
        cur.execute(f"""CREATE OR REPLACE TASK {BD}.APP.TAREA_TRABAJOS WAREHOUSE = FARMA_WH
                        ALLOW_OVERLAPPING_EXECUTION = TRUE
                        COMMENT = 'Trabajos de IA en segundo plano (la despierta la app al subir un documento)'
                        AS CALL {BD}.APP.PROCESAR_COLA()""")
        # runtime de warehouse (el runtime de contenedor necesita un compute pool, que cobra aparte)
        cur.execute(f"""CREATE OR REPLACE STREAMLIT {APP}
                        ROOT_LOCATION = '@{STAGE}/expediente_ctd'
                        MAIN_FILE = 'streamlit_app.py'
                        QUERY_WAREHOUSE = FARMA_WH
                        TITLE = 'Expediente CTD · Laboratorios Altamira'
                        COMMENT = 'Obed Farmacéutica · Vista 2'""")
    finally:
        cuenta = cur.execute("SELECT CURRENT_ORGANIZATION_NAME(), CURRENT_ACCOUNT_NAME()").fetchone()
        try:
            cur.execute("ALTER WAREHOUSE FARMA_WH SUSPEND")
        except Exception:
            pass
        con.close()
    print(f"Publicada en {round(time.time() - t, 1)} s")
    print(f"Abrir: https://app.snowflake.com/{cuenta[0].lower()}/{cuenta[1].lower()}/#/streamlit-apps/{APP.replace('.', '.')}")


if __name__ == "__main__":
    main()
