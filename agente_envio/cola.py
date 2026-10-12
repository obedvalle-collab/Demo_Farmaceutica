"""Acceso a la cola de envíos (APP.ENVIOS) y a los documentos del expediente en cada plataforma."""
import glob
import os
import tempfile
from pathlib import Path


class ColaSnowflake:
    nombre = "Snowflake"
    BD = "OBED_FARMACEUTICA"

    def __init__(self):
        import snowflake.connector
        self.con = snowflake.connector.connect(connection_name="obed_farma")
        self.con.cursor().execute("ALTER SESSION SET QUERY_TAG = 'obed_farma_robot_envio'")

    def _q(self, sql, params=None):
        cur = self.con.cursor()
        cur.execute(sql, params or ())
        cols = [c[0].lower() for c in cur.description] if cur.description else []
        return [dict(zip(cols, r)) for r in cur.fetchall()] if cols else []

    def pendientes(self):
        return self._q(f"SELECT envio_id, tramite_id FROM {self.BD}.APP.ENVIOS WHERE estatus = 'Solicitado' ORDER BY solicitado_en")

    def tomar(self, envio_id):
        cur = self.con.cursor()
        cur.execute(f"""UPDATE {self.BD}.APP.ENVIOS SET estatus = 'Preparando paquete', actualizado_en = CURRENT_TIMESTAMP()
                        WHERE envio_id = %s AND estatus = 'Solicitado'""", (envio_id,))
        return cur.rowcount == 1

    def actualizar(self, envio_id, **campos):
        sets = ", ".join(f"{k} = %s" for k in campos) + ", actualizado_en = CURRENT_TIMESTAMP()"
        self.con.cursor().execute(f"UPDATE {self.BD}.APP.ENVIOS SET {sets} WHERE envio_id = %s", (*campos.values(), envio_id))

    def estatus(self, envio_id):
        return self._q(f"SELECT estatus FROM {self.BD}.APP.ENVIOS WHERE envio_id = %s", (envio_id,))[0]["estatus"]

    def datos_tramite(self, tramite_id):
        return self._q(f"""SELECT t.tramite_id, t.homoclave, p.denominacion_generica || ' ' || p.concentracion || ', ' ||
                                  LOWER(p.forma_farmaceutica) AS denominacion, p.tipo_producto
                           FROM {self.BD}.LIMPIO.TRAMITES t JOIN {self.BD}.LIMPIO.PRODUCTOS p ON p.producto_id = t.producto_id
                           WHERE t.tramite_id = %s""", (tramite_id,))[0]

    def documentos(self, tramite_id):
        return self._q(f"""SELECT archivo, seccion_ctd, modulo, version FROM {self.BD}.NEGOCIO.EXPEDIENTE_ESTADO
                           WHERE tramite_id = %s AND archivo IS NOT NULL ORDER BY seccion_ctd""", (tramite_id,))

    def descargar(self, archivo, destino):
        destino.mkdir(parents=True, exist_ok=True)
        self.con.cursor().execute(f"GET '@{self.BD}.CRUDO.EXPEDIENTES/{archivo}' 'file://{destino.as_posix()}/'")
        return destino / Path(archivo).name

    def subir_captura(self, png, nombre):
        tmp = Path(tempfile.gettempdir()) / "claude" / nombre
        tmp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_bytes(png)
        self.con.cursor().execute(f"PUT 'file://{tmp.as_posix()}' @{self.BD}.APP.CAPTURAS AUTO_COMPRESS = FALSE OVERWRITE = TRUE")
        return nombre

    def vivo(self, envio_id, paso, accion, imagen):
        """Último cuadro de la transmisión en vivo (JPEG en base64): una fila por envío que se va reemplazando."""
        self.con.cursor().execute(f"""MERGE INTO {self.BD}.APP.ENVIO_VIVO t
            USING (SELECT %s AS envio_id, %s::INT AS paso, %s AS accion, %s AS imagen) s ON t.envio_id = s.envio_id
            WHEN MATCHED THEN UPDATE SET paso = s.paso, accion = s.accion, imagen = s.imagen, actualizado_en = CURRENT_TIMESTAMP()
            WHEN NOT MATCHED THEN INSERT (envio_id, paso, accion, imagen, actualizado_en)
                 VALUES (s.envio_id, s.paso, s.accion, s.imagen, CURRENT_TIMESTAMP())""", (envio_id, paso, accion, imagen))

    def cerrar_conexion(self):
        self.con.close()

    def cerrar(self):
        try:
            self.con.cursor().execute("ALTER WAREHOUSE FARMA_WH SUSPEND")
        except Exception:
            pass
        self.con.close()


class ColaDatabricks:
    nombre = "Databricks"
    CAT = "obed_farmaceutica"
    WAREHOUSE = "f0765c244dca9b5a"

    def __init__(self):
        cli = glob.glob(os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Databricks.DatabricksCLI_*"))
        os.environ["PATH"] += os.pathsep + os.pathsep.join(cli)
        from databricks.sdk import WorkspaceClient
        self.w = WorkspaceClient(profile="obed_farma")

    def _q(self, sql, params=None):
        import time
        from databricks.sdk.service.sql import StatementParameterListItem as P, StatementState
        ps = [P(name=k, value=None if v is None else str(v)) for k, v in (params or {}).items()]
        r = self.w.statement_execution.execute_statement(statement=sql, warehouse_id=self.WAREHOUSE, wait_timeout="50s", parameters=ps)
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(1); r = self.w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(r.status.error.message if r.status.error else str(r.status.state))
        if not r.manifest or not r.manifest.schema or not r.manifest.schema.columns:
            return []
        cols = [c.name for c in r.manifest.schema.columns]
        return [dict(zip(cols, f)) for f in (r.result.data_array or [])]

    def pendientes(self):
        return self._q(f"SELECT envio_id, tramite_id FROM {self.CAT}.app.envios WHERE estatus = 'Solicitado' ORDER BY solicitado_en")

    def tomar(self, envio_id):
        self._q(f"""UPDATE {self.CAT}.app.envios SET estatus = 'Preparando paquete', actualizado_en = current_timestamp()
                    WHERE envio_id = :e AND estatus = 'Solicitado'""", {"e": envio_id})
        return self.estatus(envio_id) == "Preparando paquete"

    def actualizar(self, envio_id, **campos):
        tipos = {"pasos": "INT", "segundos": "DOUBLE", "costo_usd": "DOUBLE", "enviado_en": "TIMESTAMP",
                 "confirmado_en": "TIMESTAMP"}
        sets = ", ".join(f"{k} = CAST(:{k} AS {tipos.get(k, 'STRING')})" for k in campos) + ", actualizado_en = current_timestamp()"
        self._q(f"UPDATE {self.CAT}.app.envios SET {sets} WHERE envio_id = :envio_id", {**campos, "envio_id": envio_id})

    def estatus(self, envio_id):
        return self._q(f"SELECT estatus FROM {self.CAT}.app.envios WHERE envio_id = :e", {"e": envio_id})[0]["estatus"]

    def datos_tramite(self, tramite_id):
        return self._q(f"""SELECT t.tramite_id, t.homoclave, concat(p.denominacion_generica, ' ', p.concentracion, ', ',
                                  lower(p.forma_farmaceutica)) AS denominacion, p.tipo_producto
                           FROM {self.CAT}.limpio.tramites t JOIN {self.CAT}.limpio.productos p ON p.producto_id = t.producto_id
                           WHERE t.tramite_id = :t""", {"t": tramite_id})[0]

    def documentos(self, tramite_id):
        return self._q(f"""SELECT archivo, seccion_ctd, modulo, version FROM {self.CAT}.negocio.expediente_estado
                           WHERE tramite_id = :t AND archivo IS NOT NULL ORDER BY seccion_ctd""", {"t": tramite_id})

    def descargar(self, archivo, destino):
        destino.mkdir(parents=True, exist_ok=True)
        r = self.w.files.download(f"/Volumes/{self.CAT}/crudo/expedientes/{archivo}")
        ruta = destino / Path(archivo).name
        ruta.write_bytes(r.contents.read())
        return ruta

    def subir_captura(self, png, nombre):
        import io
        self.w.files.upload(f"/Volumes/{self.CAT}/app/capturas/{nombre}", io.BytesIO(png), overwrite=True)
        return nombre

    def cerrar(self):
        try:
            self.w.warehouses.stop(self.WAREHOUSE)
        except Exception:
            pass

    def vivo(self, envio_id, paso, accion, imagen):
        self._q(f"""MERGE INTO {self.CAT}.app.envio_vivo t
            USING (SELECT :e AS envio_id, CAST(:p AS INT) AS paso, :a AS accion, :i AS imagen) s ON t.envio_id = s.envio_id
            WHEN MATCHED THEN UPDATE SET paso = s.paso, accion = s.accion, imagen = s.imagen, actualizado_en = current_timestamp()
            WHEN NOT MATCHED THEN INSERT (envio_id, paso, accion, imagen, actualizado_en)
                 VALUES (s.envio_id, s.paso, s.accion, s.imagen, current_timestamp())""",
                {"e": envio_id, "p": paso, "a": accion, "i": imagen})

    def cerrar_conexion(self):
        pass
