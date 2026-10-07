"""Publica la app (Vista 2) en Databricks Apps y da permisos mínimos a su identidad de servicio.

Uso:
    python databricks/desplegar_app.py            # crea (si no existe), sube el código y despliega
    python databricks/desplegar_app.py detener    # detiene la app (cobra por hora encendida)
    python databricks/desplegar_app.py iniciar
"""
import io
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase2_normas as F  # noqa: E402
from databricks.sdk.service.apps import App, AppDeployment, AppResource, AppResourceSqlWarehouse, \
    AppResourceSqlWarehouseSqlWarehousePermission  # noqa: E402
from databricks.sdk.service.workspace import ImportFormat  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
NOMBRE = "obed-farma-ctd"
w = F.w


def subir_codigo():
    subprocess.run([sys.executable, str(RAIZ / "app" / "empaquetar.py")], check=True)
    usuario = w.current_user.me().user_name
    destino = f"/Workspace/Users/{usuario}/obed_farma_app"
    w.workspace.mkdirs(destino)
    for p in (RAIZ / "app" / "_paquete" / "databricks").iterdir():
        w.workspace.upload(f"{destino}/{p.name}", io.BytesIO(p.read_bytes()), format=ImportFormat.AUTO, overwrite=True)
    return destino


def permisos(sp):
    q = f"`{sp}`"
    cat = F.CAT
    sentencias = [f"GRANT USE CATALOG ON CATALOG {cat} TO {q}"]
    for esquema in ["crudo", "limpio", "negocio", "app"]:
        sentencias += [f"GRANT USE SCHEMA, SELECT ON SCHEMA {cat}.{esquema} TO {q}"]
    sentencias += [f"GRANT MODIFY ON SCHEMA {cat}.app TO {q}",
                   f"GRANT MODIFY ON TABLE {cat}.crudo.expedientes_parseados TO {q}",
                   f"GRANT MODIFY ON TABLE {cat}.limpio.documentos_extraidos_json TO {q}",
                   f"GRANT MODIFY ON TABLE {cat}.limpio.documentos_extraidos TO {q}",
                   f"GRANT READ VOLUME, WRITE VOLUME ON VOLUME {cat}.crudo.expedientes TO {q}",
                   f"GRANT READ VOLUME, WRITE VOLUME ON VOLUME {cat}.app.capturas TO {q}"]
    for s in sentencias:
        F.sql(s)


def desplegar():
    t = time.time()
    existentes = [a.name for a in w.apps.list()]
    if NOMBRE not in existentes:
        print("Creando la app (la primera vez prepara el entorno de cómputo)…")
        w.apps.create_and_wait(App(name=NOMBRE, description="Obed Farmacéutica · Expediente CTD (Vista 2)",
                                   resources=[AppResource(name="sql-warehouse", sql_warehouse=AppResourceSqlWarehouse(
                                       id=F.WAREHOUSE, permission=AppResourceSqlWarehouseSqlWarehousePermission.CAN_USE))]))
    app = w.apps.get(NOMBRE)
    permisos(app.service_principal_client_id)
    ruta = subir_codigo()
    print("Desplegando…")
    w.apps.deploy_and_wait(NOMBRE, AppDeployment(source_code_path=ruta))
    app = w.apps.get(NOMBRE)
    print(f"Publicada en {round(time.time() - t, 1)} s · {app.url} · estado de cómputo: {app.compute_status.state}")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "desplegar"
    if accion == "detener":
        w.apps.stop_and_wait(NOMBRE); print("App detenida")
    elif accion == "iniciar":
        w.apps.start_and_wait(NOMBRE); print("App iniciada:", w.apps.get(NOMBRE).url)
    else:
        desplegar()
    w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
