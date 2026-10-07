"""Acceso a datos de la app en Databricks (Databricks Apps o local con el perfil de la CLI)."""
import io
import json
import os
import time
import uuid

from ciclo_prevencion import CicloPrevencion
from consultas import Consultas
from preauditoria import PreAuditoria
from versiones import Versiones
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


NOMBRE_JOB_ALERTAS = "obed_farma_alertas_correo"
TITULO_GENIE = "obed_farma · datos regulatorios"


class DatosDatabricks(CicloPrevencion, Consultas, Versiones, PreAuditoria):
    L, N, A = f"{CAT}.limpio", f"{CAT}.negocio", f"{CAT}.app"
    MODELO = MODELO

    def __init__(self, w, warehouse_id):
        self.w, self.wh = w, warehouse_id

    # --------------------------------------------------------------------------------- piezas del ciclo de prevención
    def q(self, sql, params=None):
        return self._q(sql, params)

    def subir_archivo(self, contenido, ruta):
        self.w.files.upload(f"{VOL}/{ruta}", io.BytesIO(contenido), overwrite=True)

    def leer_pdf(self, ruta):
        r = self._q(f"""SELECT array_join(transform(filter(cast(r:document:elements AS ARRAY<VARIANT>),
                            e -> cast(e:type AS STRING) <> 'page_number'), e -> cast(e:content AS STRING)), '

') AS t
                        FROM (SELECT ai_parse_document(content, map('version', '2.0')) AS r FROM READ_FILES('{VOL}/{ruta}', format => 'binaryFile'))""")
        return r[0]["t"] or ""

    def ia_json(self, prompt, esquema_dict):
        fmt = json.dumps({"type": "json_schema", "json_schema": {"name": "salida", "schema": esquema_dict, "strict": True}}, ensure_ascii=False)
        r = self._q("SELECT ai_query(:m, :p, responseFormat => :f) AS r", {"m": MODELO, "p": prompt, "f": fmt})[0]["r"]
        return json.loads(r)

    def ia_texto(self, prompt):
        return self._q("SELECT ai_query(:m, :p) AS r", {"m": MODELO, "p": prompt})[0]["r"]

    def enviar_correos(self):
        """Correo nativo de Databricks: un job ejecuta una alerta SQL que avisa por correo cuando hay alertas pendientes."""
        pendientes = int(self._q(f"SELECT COUNT(*) AS n FROM {self.A}.alertas WHERE enviada_en IS NULL")[0]["n"])
        if not pendientes:
            return 0
        job = next((j for j in self.w.jobs.list(name=NOMBRE_JOB_ALERTAS)), None)
        if not job:
            raise RuntimeError("Falta configurar la alerta de correo (databricks/fase6_preparar.py)")
        run = self.w.jobs.run_now_and_wait(job.job_id)
        estado = run.state.result_state.value if run.state and run.state.result_state else "?"
        canal = f"Databricks SQL Alert (job {job.job_id}, {estado})"
        self._q(f"UPDATE {self.A}.alertas SET enviada_en = current_timestamp(), canal = :c WHERE enviada_en IS NULL", {"c": canal})
        return pendientes

    def buscar_normas(self, texto, solo_vigentes=True, norma=None, n=8):
        """Vector Search (qwen3-embedding, búsqueda híbrida). El endpoint cobra mientras existe."""
        filtro = {**({"estatus": "Vigente"} if solo_vigentes else {}), **({"norma": norma} if norma else {})}
        cols = ["clausula_id", "norma", "tipo", "estatus", "numeral", "titulo", "texto_busqueda"]
        r = self.w.vector_search_indexes.query_index(index_name=f"{CAT}.ia.buscador_normas", columns=cols, query_text=texto,
                                                     num_results=n * 2, query_type="HYBRID",
                                                     filters_json=json.dumps(filtro, ensure_ascii=False) if filtro else None)
        return _sin_repetir([dict(zip(cols, f)) for f in (r.result.data_array or [])], n)

    def auditoria_plataforma(self):
        """Auditoría nativa de Databricks (Unity Catalog y tablas de sistema), filtrada al catálogo de esta demo:
        permisos, consultas recientes (system.query.history) y linaje (system.access.table_lineage)."""
        permisos = []
        for objeto in [f"CATALOG {CAT}"] + [f"SCHEMA {CAT}.{e}" for e in ("crudo", "limpio", "negocio", "ia", "app")]:
            for r in self._q(f"SHOW GRANTS ON {objeto}"):
                permisos.append({"privilegio": r.get("ActionType"), "objeto": r.get("ObjectKey") or objeto.split()[1],
                                 "tipo": r.get("ObjectType"), "otorgado_a": r.get("Principal")})
        actividad = self._q(f"""SELECT start_time AS fecha_hora, executed_by AS usuario, statement_type AS tipo,
                                       left(statement_text, 200) AS sentencia,
                                       round(total_duration_ms / 1000, 2) AS segundos
                                FROM system.query.history
                                WHERE start_time > current_timestamp() - INTERVAL 2 DAYS
                                  AND lower(statement_text) LIKE '%{CAT}%'
                                ORDER BY start_time DESC LIMIT 40""")
        accesos = self._q(f"""SELECT source_table_full_name AS objeto, COUNT(*) AS lecturas, MAX(event_time) AS ultima
                              FROM system.access.table_lineage
                              WHERE event_date >= current_date() - 3 AND source_table_catalog = '{CAT}'
                              GROUP BY 1 ORDER BY 2 DESC LIMIT 15""")
        return {"permisos": permisos, "actividad": actividad, "accesos": accesos,
                "fuente": "SHOW GRANTS (Unity Catalog) · system.query.history · system.access.table_lineage"}

    # --------------------------------------------------------------------------------- asistente (Vista 8)
    def _genie_id(self):
        if os.environ.get("GENIE_SPACE_ID"):
            return os.environ["GENIE_SPACE_ID"]
        if not getattr(self, "_genie", None):
            self._genie = next(s.space_id for s in (self.w.genie.list_spaces().spaces or []) if s.title == TITULO_GENIE)
        return self._genie

    def _consultar_genie(self, pregunta, salida):
        m = self.w.genie.start_conversation_and_wait(self._genie_id(), pregunta)
        resultado = {"respuesta": "", "sql": None, "columnas": [], "filas": []}
        for a in m.attachments or []:
            if a.text and a.text.content:
                resultado["respuesta"] += a.text.content
            if a.query and a.query.query:
                resultado["sql"] = a.query.query
                salida["sql"].append(a.query.query.strip())
                r = self.w.genie.get_message_attachment_query_result(self._genie_id(), m.conversation_id, m.id, a.attachment_id)
                sr = r.statement_response
                if sr and sr.manifest and sr.manifest.schema:
                    resultado["columnas"] = [c.name for c in sr.manifest.schema.columns]
                    resultado["filas"] = (sr.result.data_array or [])[:50] if sr.result else []
                    salida["tablas"].append({"columnas": resultado["columnas"], "filas": resultado["filas"]})
        return resultado

    def preguntar(self, pregunta, historial):
        """Agente en código con piezas nativas: gpt-oss-120b (Foundation Model API, llamadas a herramientas) decide
        entre Genie (datos) y Vector Search (normas). Databricks no ofrece un objeto de agente equivalente fuera de
        Agent Bricks (marcado como legado)."""
        import modelo_semantico as M
        herramientas = [
            {"type": "function", "function": {"name": "consultar_datos", "description":
                "Pregunta en lenguaje natural sobre trámites, plazos, prevenciones, registros sanitarios, expedientes CTD e indicadores. Devuelve SQL y filas.",
                "parameters": {"type": "object", "properties": {"pregunta": {"type": "string"}}, "required": ["pregunta"]}}},
            {"type": "function", "function": {"name": "buscar_normas", "description":
                "Busca en el texto de las NOM, leyes, reglamentos y guías ICH partidos por cláusula. Devuelve norma, numeral y texto.",
                "parameters": {"type": "object", "properties": {"consulta": {"type": "string"}}, "required": ["consulta"]}}}]
        mensajes = [{"role": "system", "content": M.INSTRUCCIONES_AGENTE + " " + M.INSTRUCCIONES_DATOS}]
        mensajes += [{"role": "user" if m["rol"] == "user" else "assistant", "content": m["texto"]} for m in historial[-6:]]
        mensajes.append({"role": "user", "content": pregunta})
        salida = {"texto": "", "fuentes": [], "sql": [], "tablas": [], "pasos": [], "segundos": 0.0, "tokens": 0}
        t, vistas = time.time(), set()
        for _ in range(5):
            r = self.w.api_client.do("POST", f"/serving-endpoints/{MODELO}/invocations",
                                     body={"messages": mensajes, "tools": herramientas, "max_tokens": 2500})
            salida["tokens"] += (r.get("usage") or {}).get("total_tokens", 0)
            msg = r["choices"][0]["message"]
            llamadas = msg.get("tool_calls") or []
            if not llamadas:
                c = msg.get("content")
                salida["texto"] = c if isinstance(c, str) else "".join(x.get("text", "") for x in (c or []) if x.get("type") == "text")
                break
            mensajes.append({"role": "assistant", "content": msg.get("content") if isinstance(msg.get("content"), str) else "",
                             "tool_calls": llamadas})
            for ll in llamadas:
                args = json.loads(ll["function"].get("arguments") or "{}")
                if ll["function"]["name"] == "consultar_datos":
                    salida["pasos"].append(f"Consultó los datos (Genie): «{args.get('pregunta', '')}»")
                    res = self._consultar_genie(args.get("pregunta", pregunta), salida)
                    if "Espacio Genie" not in vistas:
                        vistas.add("Espacio Genie")
                        salida["fuentes"].append({"tipo": "datos", "etiqueta": "Espacio Genie (tablas de negocio)", "detalle": res["sql"] or ""})
                else:
                    salida["pasos"].append(f"Buscó en las normas: «{args.get('consulta', '')}»")
                    res = self.buscar_normas(args.get("consulta", pregunta), solo_vigentes=False, n=6)
                    for x in res:
                        if x["clausula_id"] not in vistas:
                            vistas.add(x["clausula_id"])
                            salida["fuentes"].append({"tipo": "norma", "etiqueta": x["clausula_id"], "detalle": x["titulo"] or ""})
                mensajes.append({"role": "tool", "tool_call_id": ll["id"],
                                 "content": json.dumps(res, ensure_ascii=False, default=str)[:12000]})
        salida["segundos"] = round(time.time() - t, 1)
        salida["texto"] = (salida["texto"] or "").strip()
        return salida

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
        return {"archivo": archivo, "requisito_id": r["req"], "seccion_ctd": r["sec"], "tipo_documento": r["tipo"], "version": version, "hallazgos": hall}

    def reubicar(self, tramite, archivo, requisito_id):
        self._q(f"""UPDATE {CAT}.app.cargas SET requisito_id = :q, origen = 'Bandeja (reubicado por usuario)'
                    WHERE tramite_id = :t AND archivo = :a""", {"q": requisito_id, "t": tramite, "a": archivo})

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


def _sin_repetir(resultados, n):
    """Varios fragmentos pueden venir de la misma cláusula: se deja el mejor de cada una."""
    vistos, salida = set(), []
    for x in resultados:
        if x["clausula_id"] not in vistos:
            vistos.add(x["clausula_id"]); salida.append({k: x[k] for k in x if not k.startswith("@")})
    return salida[:n]
