"""Entrada de la app en Databricks Apps (también corre local: streamlit run app/databricks/app.py)."""
import glob
import os
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
for p in (AQUI, AQUI.parent / "comun", AQUI.parents[1] / "compartido"):
    if p.exists():
        sys.path.insert(0, str(p))

import streamlit as st  # noqa: E402
from databricks.sdk import WorkspaceClient  # noqa: E402

from datos_databricks import DatosDatabricks  # noqa: E402
from vista_expediente import pagina  # noqa: E402

WAREHOUSE_LOCAL = "f0765c244dca9b5a"


@st.cache_resource
def cliente():
    if os.environ.get("DATABRICKS_APP_NAME"):          # dentro de Databricks Apps: credenciales de la app
        return WorkspaceClient()
    cli = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Databricks.DatabricksCLI_*"))
    os.environ["PATH"] += os.pathsep + os.pathsep.join(cli)
    return WorkspaceClient(profile="obed_farma")


usuario = st.context.headers.get("X-Forwarded-Email", "demo") if hasattr(st, "context") else "demo"
datos = DatosDatabricks(cliente(), os.environ.get("DATABRICKS_WAREHOUSE_ID", WAREHOUSE_LOCAL))
pagina(datos, "Databricks · Databricks Apps", usuario or "demo")
