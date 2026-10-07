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
