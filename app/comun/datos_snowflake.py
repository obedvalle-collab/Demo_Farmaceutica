"""Acceso a datos de la app en Snowflake (Streamlit in Snowflake o local con Snowpark)."""
import io
import json
import uuid

from extraccion import INSTRUCCION, MAX_CARACTERES, esquema_json

BD = "OBED_FARMACEUTICA"
MODELO = "claude-sonnet-4-5"


class DatosSnowflake:
    def __init__(self, session):
        self.s = session

    def _q(self, sql, params=None):
        return [r.as_dict() for r in self.s.sql(sql, params=params or []).collect()]

    @staticmethod
    def _min(filas):
        return [{k.lower(): v for k, v in f.items()} for f in filas]

    # --------------------------------------------------------------------------------- lectura
    def tramites(self):
        return self._min(self._q(f"""SELECT c.tramite_id, c.producto, c.candado FROM {BD}.NEGOCIO.CANDADO_ENVIO c
            WHERE c.tramite_id IN (SELECT DISTINCT tramite_id FROM {BD}.APP.CARGAS) ORDER BY c.tramite_id DESC"""))

    def candado(self, tramite):
        return self._min(self._q(f"SELECT * FROM {BD}.NEGOCIO.CANDADO_ENVIO WHERE tramite_id = ?", [tramite]))[0]

    def expediente(self, tramite):
        return self._min(self._q(f"""SELECT * FROM {BD}.NEGOCIO.EXPEDIENTE_ESTADO WHERE tramite_id = ?
                                     ORDER BY modulo, seccion_ctd, requisito_id""", [tramite]))

    def hallazgos(self, tramite):
        return self._min(self._q(f"SELECT * FROM {BD}.NEGOCIO.HALLAZGOS_IA WHERE tramite_id = ?", [tramite]))

    def ultimo_envio(self, tramite):
        r = self._min(self._q(f"""SELECT * FROM {BD}.APP.ENVIOS WHERE tramite_id = ?
                                  ORDER BY solicitado_en DESC LIMIT 1""", [tramite]))
        return r[0] if r else None

    def captura(self, ruta):
        try:
            return self.s.file.get_stream(f"@{BD}.APP.CAPTURAS/{ruta}").read()
        except Exception:
            return None

    # --------------------------------------------------------------------------------- envío
    def solicitar_envio(self, tramite, usuario):
        self.s.sql(f"""INSERT INTO {BD}.APP.ENVIOS (envio_id, tramite_id, estatus, solicitado_por, solicitado_en, actualizado_en)
                       SELECT ?, ?, 'Solicitado', ?, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()""",
                   params=[str(uuid.uuid4()), tramite, usuario]).collect()

    def confirmar_envio(self, envio_id, usuario):
        self.s.sql(f"""UPDATE {BD}.APP.ENVIOS SET estatus = 'Confirmado', confirmado_por = ?, confirmado_en = CURRENT_TIMESTAMP(),
                       actualizado_en = CURRENT_TIMESTAMP() WHERE envio_id = ? AND estatus = 'Esperando confirmación'""",
                   params=[usuario, envio_id]).collect()

    def cancelar_envio(self, envio_id, usuario):
        self.s.sql(f"""UPDATE {BD}.APP.ENVIOS SET estatus = 'Cancelado', confirmado_por = ?, actualizado_en = CURRENT_TIMESTAMP()
                       WHERE envio_id = ?""", params=[usuario, envio_id]).collect()

    # --------------------------------------------------------------------------------- bandeja
    def cargar_documento(self, tramite, nombre, contenido):
        carpeta = self._q(f"SELECT SPLIT_PART(MIN(archivo), '/', 1) AS c FROM {BD}.APP.CARGAS WHERE tramite_id = ?", [tramite])[0]["C"]
        archivo = f"{carpeta}/cargas/{nombre}"
        self.s.file.put_stream(io.BytesIO(contenido), f"@{BD}.CRUDO.EXPEDIENTES/{archivo}", auto_compress=False, overwrite=True)
        self.s.sql(f"ALTER STAGE {BD}.CRUDO.EXPEDIENTES REFRESH").collect()
        self.s.sql(f"DELETE FROM {BD}.CRUDO.EXPEDIENTES_PARSEADOS WHERE archivo = ?", params=[archivo]).collect()
        self.s.sql(f"""INSERT INTO {BD}.CRUDO.EXPEDIENTES_PARSEADOS
            SELECT ?, ?, r:metadata:pageCount::INT, ARRAY_TO_STRING(TRANSFORM(r:pages, p -> p:content::STRING), '\\n\\n'),
                   NULL, CURRENT_TIMESTAMP()
            FROM (SELECT AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.EXPEDIENTES', ?), {{'mode': 'LAYOUT', 'page_split': true}}) AS r)""",
                   params=[archivo, tramite, archivo]).collect()
        self.s.sql(f"""UPDATE {BD}.CRUDO.EXPEDIENTES_PARSEADOS
            SET texto = texto || '\\n\\n[Texto OCR complementario]\\n' ||
                AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.EXPEDIENTES', ?), {{'mode': 'OCR'}}):content::STRING
            WHERE archivo = ? AND texto LIKE '%![img-%'""", params=[archivo, archivo]).collect()
        self.s.sql(f"DELETE FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON WHERE archivo = ?", params=[archivo]).collect()
        self.s.sql(f"""INSERT INTO {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON
            SELECT archivo, tramite_id, ?, TRY_PARSE_JSON(AI_COMPLETE(model => ?, prompt => ? || LEFT(texto, {MAX_CARACTERES}),
                   response_format => {{'type': 'json', 'schema': PARSE_JSON(?)}})::STRING), NULL, CURRENT_TIMESTAMP()
            FROM {BD}.CRUDO.EXPEDIENTES_PARSEADOS WHERE archivo = ?""",
                   params=[MODELO, MODELO, INSTRUCCION, esquema_json(), archivo]).collect()
        self.s.sql(f"DELETE FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS WHERE archivo = ?", params=[archivo]).collect()
        self.s.sql(self._sql_aplanar(), params=[archivo]).collect()
        r = self._q(f"""SELECT MIN(q.requisito_id) AS req, MIN(q.seccion_ctd) AS sec, MIN(x.tipo_documento) AS tipo
                        FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS x LEFT JOIN {BD}.LIMPIO.REQUISITOS_CTD q ON q.nombre = x.tipo_documento
                        WHERE x.archivo = ?""", [archivo])[0]
        if not r["REQ"]:
            return {"error": f"La IA no pudo ubicar el documento en el CTD (tipo detectado: {r['TIPO'] or 'ninguno'})."}
        version = self._q(f"SELECT COALESCE(MAX(version), 0) + 1 AS v FROM {BD}.APP.CARGAS WHERE tramite_id = ? AND requisito_id = ?",
                          [tramite, r["REQ"]])[0]["V"]
        self.s.sql(f"INSERT INTO {BD}.APP.CARGAS SELECT ?, ?, ?, ?, CURRENT_TIMESTAMP(), 'app', 'Bandeja de carga'",
                   params=[tramite, r["REQ"], archivo, version]).collect()
        hall = [h["HALLAZGO"] + (f" ({h['NORMA']} {h['CLAUSULA']})" if h["NORMA"] else "") for h in
                self._q(f"SELECT hallazgo, norma, clausula FROM {BD}.NEGOCIO.HALLAZGOS_IA WHERE archivo = ?", [archivo])]
        return {"archivo": archivo, "requisito_id": r["REQ"], "seccion_ctd": r["SEC"], "tipo_documento": r["TIPO"], "version": version, "hallazgos": hall}

    def reubicar(self, tramite, archivo, requisito_id):
        self.s.sql(f"""UPDATE {BD}.APP.CARGAS SET requisito_id = ?, origen = 'Bandeja (reubicado por usuario)'
                       WHERE tramite_id = ? AND archivo = ?""", params=[requisito_id, tramite, archivo]).collect()

    @staticmethod
    def _sql_aplanar():
        return f"""INSERT INTO {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS
        SELECT j.archivo, j.tramite_id, j.modelo,
               r:tipo_documento::STRING AS tipo_documento, r:producto::STRING AS producto, r:emisor::STRING AS emisor,
               r:fabricante_farmaco::STRING AS fabricante_farmaco, TRY_TO_DATE(r:fecha_emision::STRING) AS fecha_emision,
               r:numero_lotes_estudio::INT AS numero_lotes_estudio,
               ARRAY_TO_STRING(r:firmas_vacias, '; ') AS firmas_vacias, ARRAY_SIZE(r:firmas_vacias) AS n_firmas_vacias,
               r:leyenda_receta_medica::BOOLEAN AS leyenda_receta_medica, r:leyenda_no_alcance_ninos::BOOLEAN AS leyenda_no_alcance_ninos,
               r:leyenda_farmacovigilancia::BOOLEAN AS leyenda_farmacovigilancia, r:leyenda_venta_fraccionada::BOOLEAN AS leyenda_venta_fraccionada,
               r:siglas_mbb::BOOLEAN AS siglas_mbb, r:codigo_postal_fabricante::STRING AS codigo_postal_fabricante,
               r:ic90_cmax_inferior::FLOAT AS ic90_cmax_inferior, r:ic90_cmax_superior::FLOAT AS ic90_cmax_superior,
               ARRAY_MIN(r:f2_valores)::FLOAT AS f2_minimo,
               ARRAY_TO_STRING(r:pruebas_fuera_especificacion, '; ') AS pruebas_fuera_especificacion,
               ARRAY_SIZE(r:pruebas_fuera_especificacion) AS n_fuera_especificacion,
               r:conclusion_favorable::BOOLEAN AS conclusion_favorable, r:meses_largo_plazo::INT AS meses_largo_plazo,
               r:evalua_excursiones_temperatura::BOOLEAN AS evalua_excursiones_temperatura,
               ARRAY_TO_STRING(r:secciones, ' | ') AS secciones, r:es_legible::BOOLEAN AS es_legible,
               LENGTH(p.texto) AS caracteres_texto, r:resumen::STRING AS resumen
        FROM (SELECT *, respuesta AS r FROM {BD}.LIMPIO.DOCUMENTOS_EXTRAIDOS_JSON) j
        JOIN {BD}.CRUDO.EXPEDIENTES_PARSEADOS p ON p.archivo = j.archivo
        WHERE j.archivo = ?"""
