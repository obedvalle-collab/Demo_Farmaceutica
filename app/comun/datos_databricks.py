"""Acceso a datos de la app en Databricks (Databricks Apps o local con el perfil de la CLI)."""
import io
import json
import os
import time
import uuid

from extraccion import INSTRUCCION, MAX_CARACTERES, esquema

CAT = "obed_farmaceutica"
VOL = f"/Volumes/{CAT}/crudo/expedientes"
MODELO = "databricks-gpt-oss-120b"
DDL = ("STRUCT<tipo_documento: STRING, producto: STRING, emisor: STRING, fabricante_farmaco: STRING, fecha_emision: STRING, "
       "numero_lotes_estudio: INT, firmas_vacias: ARRAY<STRING>, leyenda_receta_medica: BOOLEAN, "
       "leyenda_no_alcance_ninos: BOOLEAN, leyenda_farmacovigilancia: BOOLEAN, leyenda_venta_fraccionada: BOOLEAN, "
       "siglas_mbb: BOOLEAN, codigo_postal_fabricante: STRING, ic90_cmax_inferior: DOUBLE, ic90_cmax_superior: DOUBLE, "
       "f2_valores: ARRAY<DOUBLE>, pruebas_fuera_especificacion: ARRAY<STRING>, conclusion_favorable: BOOLEAN, "
       "meses_largo_plazo: INT, evalua_excursiones_temperatura: BOOLEAN, secciones: ARRAY<STRING>, es_legible: BOOLEAN, "
       "resumen: STRING>")


class DatosDatabricks:
    def __init__(self, w, warehouse_id):
        self.w, self.wh = w, warehouse_id

    def _q(self, sql, params=None):
        from databricks.sdk.service.sql import StatementParameterListItem as P, StatementState
        ps = [P(name=k, value=None if v is None else str(v)) for k, v in (params or {}).items()]
        r = self.w.statement_execution.execute_statement(statement=sql, warehouse_id=self.wh, wait_timeout="50s", parameters=ps)
        while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(1); r = self.w.statement_execution.get_statement(r.statement_id)
        if r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(r.status.error.message if r.status.error else str(r.status.state))
        if not r.manifest or not r.manifest.schema or not r.manifest.schema.columns:
            return []
        cols = [c.name for c in r.manifest.schema.columns]
        return [dict(zip(cols, f)) for f in (r.result.data_array or [])]

    # --------------------------------------------------------------------------------- lectura
    def tramites(self):
        return self._q(f"""SELECT c.tramite_id, c.producto, c.candado FROM {CAT}.negocio.candado_envio c
            WHERE c.tramite_id IN (SELECT DISTINCT tramite_id FROM {CAT}.app.cargas) ORDER BY c.tramite_id DESC""")

    def candado(self, tramite):
        return self._q(f"SELECT * FROM {CAT}.negocio.candado_envio WHERE tramite_id = :t", {"t": tramite})[0]

    def expediente(self, tramite):
        return self._q(f"""SELECT * FROM {CAT}.negocio.expediente_estado WHERE tramite_id = :t
                           ORDER BY modulo, seccion_ctd, requisito_id""", {"t": tramite})

    def hallazgos(self, tramite):
        return self._q(f"SELECT * FROM {CAT}.negocio.hallazgos_ia WHERE tramite_id = :t", {"t": tramite})

    def ultimo_envio(self, tramite):
        r = self._q(f"SELECT * FROM {CAT}.app.envios WHERE tramite_id = :t ORDER BY solicitado_en DESC LIMIT 1", {"t": tramite})
        return r[0] if r else None

    def captura(self, ruta):
        try:
            return self.w.files.download(f"/Volumes/{CAT}/app/capturas/{ruta}").contents.read()
        except Exception:
            return None

    # --------------------------------------------------------------------------------- envío
    def solicitar_envio(self, tramite, usuario):
        self._q(f"""INSERT INTO {CAT}.app.envios (envio_id, tramite_id, estatus, solicitado_por, solicitado_en, actualizado_en)
                    VALUES (:e, :t, 'Solicitado', :u, current_timestamp(), current_timestamp())""",
                {"e": str(uuid.uuid4()), "t": tramite, "u": usuario})

    def confirmar_envio(self, envio_id, usuario):
        self._q(f"""UPDATE {CAT}.app.envios SET estatus = 'Confirmado', confirmado_por = :u, confirmado_en = current_timestamp(),
                    actualizado_en = current_timestamp() WHERE envio_id = :e AND estatus = 'Esperando confirmación'""",
                {"u": usuario, "e": envio_id})

    def cancelar_envio(self, envio_id, usuario):
        self._q(f"""UPDATE {CAT}.app.envios SET estatus = 'Cancelado', confirmado_por = :u, actualizado_en = current_timestamp()
                    WHERE envio_id = :e""", {"u": usuario, "e": envio_id})

    # --------------------------------------------------------------------------------- bandeja
    def cargar_documento(self, tramite, nombre, contenido):
        carpeta = self._q(f"SELECT split(MIN(archivo), '/')[0] AS c FROM {CAT}.app.cargas WHERE tramite_id = :t", {"t": tramite})[0]["c"]
        archivo = f"{carpeta}/cargas/{nombre}"
        self.w.files.upload(f"{VOL}/{archivo}", io.BytesIO(contenido), overwrite=True)
        a = {"a": archivo}
        self._q(f"DELETE FROM {CAT}.crudo.expedientes_parseados WHERE archivo = :a", a)
        self._q(f"""INSERT INTO {CAT}.crudo.expedientes_parseados
            SELECT :a, :t, size(cast(r:document:pages AS ARRAY<VARIANT>)),
                   array_join(transform(filter(cast(r:document:elements AS ARRAY<VARIANT>), e -> cast(e:type AS STRING) <> 'page_number'),
                       e -> CASE cast(e:type AS STRING) WHEN 'signature' THEN '[Firma manuscrita detectada]'
                                 WHEN 'figure' THEN concat('[Figura] ', coalesce(cast(e:content AS STRING), ''))
                                 ELSE cast(e:content AS STRING) END), '\\n\\n'), NULL, current_timestamp()
            FROM (SELECT ai_parse_document(content, map('version', '2.0')) AS r FROM READ_FILES('{VOL}/{archivo}', format => 'binaryFile'))""",
                {**a, "t": tramite})
        formato = json.dumps({"type": "json_schema", "json_schema": {"name": "extraccion", "schema": esquema(), "strict": True}},
                             ensure_ascii=False)
        self._q(f"DELETE FROM {CAT}.limpio.documentos_extraidos_json WHERE archivo = :a", a)
        self._q(f"""INSERT INTO {CAT}.limpio.documentos_extraidos_json
            SELECT archivo, tramite_id, :m, ai_query(:m, concat(:i, left(texto, {MAX_CARACTERES})), responseFormat => :f),
                   NULL, current_timestamp() FROM {CAT}.crudo.expedientes_parseados WHERE archivo = :a""",
                {**a, "m": MODELO, "i": INSTRUCCION, "f": formato})
        self._q(f"DELETE FROM {CAT}.limpio.documentos_extraidos WHERE archivo = :a", a)
        self._q(self._sql_aplanar(), a)
        r = self._q(f"""SELECT MIN(q.requisito_id) AS req, MIN(q.seccion_ctd) AS sec, MIN(x.tipo_documento) AS tipo
                        FROM {CAT}.limpio.documentos_extraidos x LEFT JOIN {CAT}.limpio.requisitos_ctd q ON q.nombre = x.tipo_documento
                        WHERE x.archivo = :a""", a)[0]
        if not r["req"]:
            return {"error": f"La IA no pudo ubicar el documento en el CTD (tipo detectado: {r['tipo'] or 'ninguno'})."}
        version = int(self._q(f"SELECT COALESCE(MAX(version), 0) + 1 AS v FROM {CAT}.app.cargas WHERE tramite_id = :t AND requisito_id = :q",
                              {"t": tramite, "q": r["req"]})[0]["v"])
        self._q(f"INSERT INTO {CAT}.app.cargas VALUES (:t, :q, :a, {version}, current_timestamp(), 'app', 'Bandeja de carga')",
                {**a, "t": tramite, "q": r["req"]})
        hall = [h["hallazgo"] + (f" ({h['norma']} {h['clausula']})" if h["norma"] else "") for h in
                self._q(f"SELECT hallazgo, norma, clausula FROM {CAT}.negocio.hallazgos_ia WHERE archivo = :a", a)]
        return {"seccion_ctd": r["sec"], "tipo_documento": r["tipo"], "version": version, "hallazgos": hall}

    @staticmethod
    def _sql_aplanar():
        return f"""INSERT INTO {CAT}.limpio.documentos_extraidos
        SELECT j.archivo, j.tramite_id, j.modelo,
               r.tipo_documento, r.producto, r.emisor, r.fabricante_farmaco, try_cast(r.fecha_emision AS DATE) AS fecha_emision,
               r.numero_lotes_estudio, array_join(r.firmas_vacias, '; ') AS firmas_vacias,
               CASE WHEN r.firmas_vacias IS NULL THEN 0 ELSE size(r.firmas_vacias) END AS n_firmas_vacias,
               r.leyenda_receta_medica, r.leyenda_no_alcance_ninos, r.leyenda_farmacovigilancia, r.leyenda_venta_fraccionada,
               r.siglas_mbb, r.codigo_postal_fabricante, r.ic90_cmax_inferior, r.ic90_cmax_superior,
               array_min(r.f2_valores) AS f2_minimo, array_join(r.pruebas_fuera_especificacion, '; ') AS pruebas_fuera_especificacion,
               CASE WHEN r.pruebas_fuera_especificacion IS NULL THEN 0 ELSE size(r.pruebas_fuera_especificacion) END AS n_fuera_especificacion,
               r.conclusion_favorable, r.meses_largo_plazo, r.evalua_excursiones_temperatura,
               array_join(r.secciones, ' | ') AS secciones, r.es_legible, length(p.texto) AS caracteres_texto, r.resumen
        FROM (SELECT *, from_json(respuesta, '{DDL}') AS r FROM {CAT}.limpio.documentos_extraidos_json) j
        JOIN {CAT}.crudo.expedientes_parseados p ON p.archivo = j.archivo
        WHERE j.archivo = :a"""
