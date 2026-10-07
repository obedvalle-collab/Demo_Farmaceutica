"""Acceso a datos de la app en Snowflake (Streamlit in Snowflake o local con Snowpark)."""
import io
import json
import time
import uuid

import re

from ciclo_prevencion import CicloPrevencion
from consultas import Consultas
from preauditoria import PreAuditoria
from versiones import Versiones
from extraccion import INSTRUCCION, MAX_CARACTERES, esquema_json

BD = "OBED_FARMACEUTICA"
MODELO = "claude-sonnet-4-5"


class DatosSnowflake(CicloPrevencion, Consultas, Versiones, PreAuditoria):
    L, N, A = f"{BD}.LIMPIO", f"{BD}.NEGOCIO", f"{BD}.APP"
    MODELO = MODELO

    def __init__(self, session):
        self.s = session

    # --------------------------------------------------------------------------------- piezas del ciclo de prevención
    def q(self, sql, params=None):
        """SQL con parámetros :nombre (se convierten a ? de Snowpark); devuelve dicts con claves en minúsculas."""
        valores = []
        if params:
            def sustituir(m):
                valores.append(params[m.group(1)])
                return "?"
            sql = re.sub(r"(?<![:\w]):([a-zA-Z_]\w*)", sustituir, sql)
        return [{k.lower(): v for k, v in r.as_dict().items()} for r in self.s.sql(sql, params=valores).collect()]

    def subir_archivo(self, contenido, ruta):
        self.s.file.put_stream(io.BytesIO(contenido), f"@{BD}.CRUDO.EXPEDIENTES/{ruta}", auto_compress=False, overwrite=True)
        self.s.sql(f"ALTER STAGE {BD}.CRUDO.EXPEDIENTES REFRESH").collect()

    def leer_pdf(self, ruta):
        r = self.s.sql(f"""SELECT ARRAY_TO_STRING(TRANSFORM(r:pages, p -> p:content::STRING), '

') AS t
            FROM (SELECT AI_PARSE_DOCUMENT(TO_FILE('@{BD}.CRUDO.EXPEDIENTES', ?), {{'mode': 'LAYOUT', 'page_split': true}}) AS r)""",
                       params=[ruta]).collect()
        return r[0]["T"] or ""

    def ia_json(self, prompt, esquema_dict):
        r = self.s.sql("SELECT AI_COMPLETE(model => ?, prompt => ?, response_format => {'type': 'json', 'schema': PARSE_JSON(?)}) AS r",
                       params=[MODELO, prompt, json.dumps(esquema_dict, ensure_ascii=False)]).collect()[0]["R"]
        if r is None:
            # con instrucciones largas y salida grande, el modo JSON con esquema a veces devuelve NULL:
            # se repite en texto libre pidiendo el mismo esquema y se lee el JSON de la respuesta
            r = self.ia_texto(prompt + "\n\nResponde SOLO con un objeto JSON válido que cumpla este esquema:\n"
                              + json.dumps(esquema_dict, ensure_ascii=False))
            r = r[r.find("{"): r.rfind("}") + 1]
        d = json.loads(r) if isinstance(r, str) else r
        return json.loads(d) if isinstance(d, str) else d

    def ia_texto(self, prompt):
        r = self.s.sql("SELECT AI_COMPLETE(?, ?) AS r", params=[MODELO, prompt]).collect()[0]["R"] or ""
        return json.loads(r) if r.startswith('"') else r   # AI_COMPLETE devuelve el texto como cadena JSON

    def enviar_correos(self):
        """Correo nativo de Snowflake: SYSTEM$SEND_EMAIL con la integración FARMA_EMAIL (solo a usuarios verificados)."""
        n = 0
        for a in self.q(f"SELECT alerta_id, para, asunto, cuerpo FROM {self.A}.alertas WHERE enviada_en IS NULL ORDER BY creada_en"):
            try:
                self.s.sql("CALL SYSTEM$SEND_EMAIL('FARMA_EMAIL', ?, ?, ?, 'text/html')",
                           params=[a["para"], a["asunto"], a["cuerpo"]]).collect()
                self.q(f"UPDATE {self.A}.alertas SET enviada_en = CURRENT_TIMESTAMP(), canal = 'Snowflake SYSTEM$SEND_EMAIL' WHERE alerta_id = :i",
                       {"i": a["alerta_id"]})
                n += 1
            except Exception as e:
                self.q(f"UPDATE {self.A}.alertas SET error = :e WHERE alerta_id = :i", {"e": str(e)[:1000], "i": a["alerta_id"]})
        return n

    def buscar_normas(self, texto, solo_vigentes=True, norma=None, n=8):
        """Cortex Search (arctic-embed-l-v2.0, búsqueda híbrida + reordenamiento)."""
        filtros = ([{"@eq": {"estatus": "Vigente"}}] if solo_vigentes else []) + ([{"@eq": {"norma": norma}}] if norma else [])
        q = {"query": texto, "limit": n * 2,
             "columns": ["clausula_id", "norma", "tipo", "estatus", "numeral", "titulo", "texto_busqueda"]}
        if filtros:
            q["filter"] = filtros[0] if len(filtros) == 1 else {"@and": filtros}
        r = self.s.sql(f"SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW('{BD}.IA.BUSCADOR_NORMAS', ?) AS r",
                       params=[json.dumps(q, ensure_ascii=False)]).collect()[0]["R"]
        return _sin_repetir(json.loads(r)["results"], n)

    def auditoria_plataforma(self):
        """Auditoría nativa de Snowflake, filtrada a la base de esta demo: permisos, consultas recientes (QUERY_HISTORY)
        y tablas más leídas (ACCESS_HISTORY). ACCOUNT_USAGE tiene retraso de hasta ~45 min a 3 h."""
        permisos = [{"privilegio": r["privilege"], "objeto": r["name"], "tipo": r["granted_on"], "otorgado_a": r["grantee_name"]}
                    for r in self.s.sql(f"SHOW GRANTS ON DATABASE {BD}").collect()]
        actividad = self.q(f"""SELECT start_time AS fecha_hora, user_name AS usuario, role_name AS rol, query_type AS tipo,
                                      LEFT(query_text, 200) AS sentencia,
                                      ROUND(total_elapsed_time / 1000, 2) AS segundos
                               FROM SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY
                               WHERE database_name = '{BD}' AND start_time > DATEADD(day, -2, CURRENT_TIMESTAMP())
                               ORDER BY start_time DESC LIMIT 40""")
        accesos = self.q(f"""SELECT f.value:"objectName"::STRING AS objeto, COUNT(*) AS lecturas, MAX(a.query_start_time) AS ultima
                             FROM SNOWFLAKE.ACCOUNT_USAGE.ACCESS_HISTORY a, LATERAL FLATTEN(a.base_objects_accessed) f
                             WHERE a.query_start_time > DATEADD(day, -3, CURRENT_TIMESTAMP())
                               AND f.value:"objectName"::STRING LIKE '{BD}.%'
                             GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
        return {"permisos": permisos, "actividad": actividad, "accesos": accesos,
                "fuente": "SHOW GRANTS · SNOWFLAKE.ACCOUNT_USAGE.QUERY_HISTORY · ACCESS_HISTORY"}

    def preguntar(self, pregunta, historial):
        """Cortex Agent (objeto ASISTENTE_REGULATORIO) por SQL: DATA_AGENT_RUN. La API REST de agentes no está
        disponible desde Streamlit in Snowflake con runtime de warehouse; la función SQL sí, y es la misma en local."""
        mensajes = [{"role": m["rol"], "content": [{"type": "text", "text": m["texto"]}]} for m in historial[-6:]]
        mensajes.append({"role": "user", "content": [{"type": "text", "text": pregunta}]})
        t = time.time()
        r = self.s.sql(f"SELECT SNOWFLAKE.CORTEX.DATA_AGENT_RUN('{BD}.IA.ASISTENTE_REGULATORIO', ?) AS r",
                       params=[json.dumps({"messages": mensajes, "stream": False}, ensure_ascii=False)]).collect()[0]["R"]
        d = json.loads(r)
        salida = {"texto": "", "fuentes": [], "sql": [], "tablas": [], "pasos": [], "segundos": round(time.time() - t, 1),
                  "tokens": sum(x["input_tokens"]["total"] + x["output_tokens"]["total"]
                                for x in d.get("metadata", {}).get("usage", {}).get("tokens_consumed", []))}
        vistas = set()
        for c in d.get("content", []):
            if c["type"] == "text":
                salida["texto"] += c["text"]
                for a in c.get("annotations") or []:
                    if a.get("doc_id") and a["doc_id"] not in vistas:
                        vistas.add(a["doc_id"])
                        salida["fuentes"].append({"tipo": "norma", "etiqueta": a["doc_id"], "detalle": a.get("doc_title", "")})
            elif c["type"] == "tool_use":
                u = c["tool_use"]
                if u.get("type") == "system_execute_sql":
                    salida["sql"].append(u["input"]["sql"].strip())
                    salida["pasos"].append("Consultó los datos (Cortex Analyst → SQL)")
                elif u.get("type") == "cortex_search":
                    salida["pasos"].append(f"Buscó en las normas: «{u['input'].get('query', '')}»")
            elif c["type"] == "table":
                rs = c["table"]["result_set"]
                salida["tablas"].append({"columnas": [x["name"].lower() for x in rs["resultSetMetaData"]["rowType"]],
                                         "filas": rs["data"]})
        if salida["sql"]:
            salida["fuentes"].append({"tipo": "datos", "etiqueta": "Vista semántica SV_REGULATORIO",
                                      "detalle": f"{len(salida['sql'])} consulta(s) SQL"})
        salida["texto"] = salida["texto"].strip()
        return salida

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


def _sin_repetir(resultados, n):
    """Varios fragmentos pueden venir de la misma cláusula: se deja el mejor de cada una."""
    vistos, salida = set(), []
    for x in resultados:
        if x["clausula_id"] not in vistos:
            vistos.add(x["clausula_id"]); salida.append({k: x[k] for k in x if not k.startswith("@")})
    return salida[:n]
