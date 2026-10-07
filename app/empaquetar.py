"""Arma la carpeta que se publica en cada plataforma: entrada + código compartido de la app + extracción.

Uso: python app/empaquetar.py   →   app/_paquete/snowflake/  y  app/_paquete/databricks/
"""
import json
import shutil
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent
RAIZ = APP.parent
sys.path.insert(0, str(RAIZ / "compartido"))
import extraccion  # noqa: E402


def empaquetar():
    tipos = extraccion.tipos_documento()
    for plataforma, archivos in {"snowflake": ["streamlit_app.py", "environment.yml"],
                                 "databricks": ["app.py", "app.yaml", "requirements.txt"]}.items():
        destino = APP / "_paquete" / plataforma
        shutil.rmtree(destino, ignore_errors=True)
        destino.mkdir(parents=True)
        for a in archivos:
            if (APP / plataforma / a).exists():
                shutil.copy(APP / plataforma / a, destino / a)
        for a in ["vista_expediente.py", f"datos_{plataforma}.py"]:
            shutil.copy(APP / "comun" / a, destino / a)
        shutil.copy(RAIZ / "compartido" / "extraccion.py", destino / "extraccion.py")
        (destino / "tipos_documento.json").write_text(json.dumps(tipos, ensure_ascii=False), encoding="utf-8")
        print(plataforma, sorted(p.name for p in destino.iterdir()))


if __name__ == "__main__":
    empaquetar()
