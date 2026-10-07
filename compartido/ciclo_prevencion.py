"""Ciclo de prevenciones (Fase 6): la misma lógica para Snowflake y Databricks.

Cada plataforma implementa solo cinco piezas (ver app/comun/datos_*.py):
    q(sql, params)            ejecutar SQL con parámetros :nombre y devolver filas como dict (claves en minúsculas)
    subir_archivo(bytes, ruta) guardar un archivo en su almacenamiento (stage / volume)
    leer_pdf(ruta)            texto del PDF leído con su IA de documentos
    ia_json(prompt, esquema)  respuesta estructurada de su modelo de lenguaje
    ia_texto(prompt)          texto libre de su modelo de lenguaje
    enviar_correos()          mandar las alertas pendientes por el mecanismo nativo de la plataforma
"""
import json
import re
import uuid

import oficio as O

CORREO_ALERTAS = "obed.valle@dataiq.com.mx"


class CicloPrevencion:
    L = N = A = ""   # nombres de los esquemas limpio / negocio / app (los define cada plataforma)

    # ------------------------------------------------------------------------------------------ consultas
    def prevenciones(self):
        return self.q(f"SELECT * FROM {self.N}.prevenciones_en_curso ORDER BY fecha_limite_accion")

    def detalle_oficio(self, oficio_id):
        return {"observaciones": self.q(f"SELECT * FROM {self.A}.observaciones_oficio WHERE oficio_id = :o ORDER BY numero", {"o": oficio_id}),
                "tareas": self.q(f"SELECT * FROM {self.A}.tareas_oficio WHERE oficio_id = :o ORDER BY numero", {"o": oficio_id}),
                "borrador": (self.q(f"SELECT texto FROM {self.A}.borradores WHERE oficio_id = :o", {"o": oficio_id}) or [{"texto": ""}])[0]["texto"]}

    def alertas_enviadas(self, tramite):
        return self.q(f"SELECT tipo, asunto, creada_en, enviada_en, canal FROM {self.A}.alertas WHERE tramite_id = :t ORDER BY creada_en DESC",
                      {"t": tramite})

    def _fecha_demo(self):
        return str(self.q(f"SELECT fecha_demo FROM {self.N}.parametros")[0]["fecha_demo"])[:10]

    def _habil(self, desde, n):
        """Día hábil número n contado a partir del día siguiente a `desde` (n=1 → siguiente día hábil)."""
        r = self.q(f"""SELECT MIN(c.fecha) AS f FROM {self.N}.calendario_indice c
                       WHERE c.es_habil AND c.indice_habil = (SELECT indice_habil FROM {self.N}.calendario_indice
                                                              WHERE fecha = CAST(:d AS DATE)) + {int(n)}""", {"d": desde})
        return str(r[0]["f"])[:10]

    def _tramite(self, tramite_id):
        return self.q(f"SELECT tramite_id, producto, homoclave, tipo_tramite FROM {self.L}.tramites WHERE tramite_id = :t",
                      {"t": tramite_id})[0]

    def _alerta(self, tipo, tramite_id, referencia, asunto, cuerpo):
        self.q(f"""INSERT INTO {self.A}.alertas (alerta_id, tipo, tramite_id, referencia, para, asunto, cuerpo, creada_en)
                   VALUES (:i, :tipo, :t, :r, :p, :a, :c, CURRENT_TIMESTAMP())""",
               {"i": str(uuid.uuid4()), "tipo": tipo, "t": tramite_id, "r": referencia, "p": CORREO_ALERTAS, "a": asunto, "c": cuerpo})

    # ------------------------------------------------------------------------------------------ 1. aviso
    def ultimo_correo(self):
        r = self.q(f"SELECT COALESCE(MAX(correo_id), 0) AS m FROM {self.A}.avisos")
        return int(r[0]["m"])

    def registrar_aviso(self, correo):
        """Lo llama el vigía por cada correo nuevo del buzón. Devuelve el aviso o None si no es de COFEPRIS."""
        m = re.search(r"[Ff]olio\s+(DGP-\d{4}-\d+)", correo["asunto"] + " " + correo["cuerpo"])
        if not m:
            return None
        folio = m.group(1)
        t = self.q(f"""SELECT tramite_id FROM {self.A}.envios WHERE folio = :f
                       UNION SELECT tramite_id FROM {self.L}.tramites WHERE folio_digipris = :f""", {"f": folio})
        if not t:
            return None
        fecha = correo["fecha"][:10]
        aviso = dict(aviso_id=str(uuid.uuid4()), folio=folio, tramite_id=t[0]["tramite_id"], fecha_aviso=fecha,
                     fecha_limite_apertura=self._habil(fecha, 5))
        self.q(f"""INSERT INTO {self.A}.avisos VALUES (:i, :c, :t, :f, :asunto, CURRENT_TIMESTAMP(), CAST(:fa AS DATE),
                   CAST(:fl AS DATE), 'Nuevo', CURRENT_TIMESTAMP())""",
               {"i": aviso["aviso_id"], "c": correo["id"], "t": aviso["tramite_id"], "f": folio, "asunto": correo["asunto"],
                "fa": fecha, "fl": aviso["fecha_limite_apertura"]})
        tr = self._tramite(aviso["tramite_id"])
        resp = self.q(f"SELECT responsable FROM {self.N}.responsables_area WHERE area = 'Asuntos Regulatorios'")
        asunto, cuerpo = O.alerta_aviso(aviso, tr, resp[0]["responsable"] if resp else "Asuntos Regulatorios")
        self._alerta("Aviso de prevención", aviso["tramite_id"], aviso["aviso_id"], asunto, cuerpo)
        return aviso

    # ------------------------------------------------------------------------------------------ 2. abrir oficio
    def solicitar_apertura(self, tramite_id, aviso_id, usuario):
        self.q(f"""INSERT INTO {self.A}.acciones VALUES (:i, 'abrir_oficio', :t, :a, 'Solicitada', :u, CURRENT_TIMESTAMP(),
                   NULL, CURRENT_TIMESTAMP())""", {"i": str(uuid.uuid4()), "t": tramite_id, "a": aviso_id, "u": usuario})
        self.q(f"UPDATE {self.A}.avisos SET estatus = 'Apertura solicitada' WHERE aviso_id = :a", {"a": aviso_id})

    def acciones_pendientes(self):
        return self.q(f"""SELECT x.accion_id, x.tramite_id, x.aviso_id, a.folio FROM {self.A}.acciones x
                          JOIN {self.A}.avisos a ON a.aviso_id = x.aviso_id WHERE x.estatus = 'Solicitada'""")

    def actualizar_accion(self, accion_id, estatus, resultado=""):
        self.q(f"UPDATE {self.A}.acciones SET estatus = :e, resultado = :r, actualizado_en = CURRENT_TIMESTAMP() WHERE accion_id = :i",
               {"e": estatus, "r": resultado[:2000], "i": accion_id})

    def registrar_oficio(self, aviso_id, nombre, contenido, acuse):
        """El robot abrió el oficio en el portal y lo descargó: guardarlo y analizarlo."""
        av = self.q(f"SELECT * FROM {self.A}.avisos WHERE aviso_id = :a", {"a": aviso_id})[0]
        ruta = f"oficios/{av['tramite_id']}/{nombre}"
        self.subir_archivo(contenido, ruta)
        apertura = self._fecha_demo()
        oficio_id = str(uuid.uuid4())
        self.q(f"""INSERT INTO {self.A}.oficios (oficio_id, aviso_id, tramite_id, folio, archivo, acuse_apertura, fecha_apertura,
                   fecha_surte_efectos) VALUES (:o, :a, :t, :f, :r, :ac, CAST(:fa AS DATE), CAST(:fs AS DATE))""",
               {"o": oficio_id, "a": aviso_id, "t": av["tramite_id"], "f": av["folio"], "r": ruta, "ac": acuse,
                "fa": apertura, "fs": self._habil(apertura, 1)})
        self.q(f"UPDATE {self.A}.avisos SET estatus = 'Abierto', actualizado_en = CURRENT_TIMESTAMP() WHERE aviso_id = :a", {"a": aviso_id})
        return self.procesar_oficio(oficio_id)

    # ------------------------------------------------------------------------------------------ 3. IA sobre el oficio
    def procesar_oficio(self, oficio_id):
        of = self.q(f"SELECT * FROM {self.A}.oficios WHERE oficio_id = :o", {"o": oficio_id})[0]
        texto = self.leer_pdf(of["archivo"])
        datos = self.ia_json(O.INSTRUCCION_OFICIO + texto, O.ESQUEMA_OFICIO)
        plazo = int(datos.get("plazo_dias_habiles") or 10)
        surte = str(of["fecha_surte_efectos"])[:10]
        limite = self._habil(surte, plazo - 1) if plazo > 1 else surte
        self.q(f"""UPDATE {self.A}.oficios SET numero_oficio = :n, plazo_dias_habiles = {plazo}, fecha_limite = CAST(:l AS DATE),
                   texto = :tx, procesado_en = CURRENT_TIMESTAMP() WHERE oficio_id = :o""",
               {"n": datos.get("numero_oficio", ""), "l": limite, "tx": texto[:60000], "o": oficio_id})
        docs = self.q(f"SELECT requisito_id, seccion_ctd, nombre_requisito, area_responsable FROM {self.L}.documentos WHERE tramite_id = :t",
                      {"t": of["tramite_id"]})
        resp = {r["area"]: r for r in self.q(f"SELECT * FROM {self.N}.responsables_area")}
        compromiso = self._habil(surte, max(1, plazo - 3))
        obs_detalle, areas = [], set()
        for ob in datos.get("observaciones", []):
            req = self._requisito(ob, docs)
            area = req["area_responsable"] if req else "Asuntos Regulatorios"
            areas.add(area)
            cl = self.q(f"SELECT texto FROM {self.L}.normas_clausulas WHERE norma = :n AND numeral = :c",
                        {"n": ob.get("norma", ""), "c": ob.get("clausula", "")}) if ob.get("clausula") else []
            texto_cl = cl[0]["texto"][:1500] if cl else ""
            self.q(f"""INSERT INTO {self.A}.observaciones_oficio VALUES (:o, :t, {int(ob['numero'])}, :tx, :n, :c, :s, :q, :a, :tc)""",
                   {"o": oficio_id, "t": of["tramite_id"], "tx": ob["texto"], "n": ob.get("norma", ""), "c": ob.get("clausula", ""),
                    "s": ob.get("seccion_ctd", ""), "q": req["requisito_id"] if req else "", "a": area, "tc": texto_cl})
            r = resp.get(area, {"usuario_id": "", "responsable": area})
            self.q(f"""INSERT INTO {self.A}.tareas_oficio VALUES (:i, :o, :t, {int(ob['numero'])}, :d, :a, :ru, :rn,
                       CAST(:fc AS DATE), 'Pendiente', NULL)""",
                   {"i": str(uuid.uuid4()), "o": oficio_id, "t": of["tramite_id"],
                    "d": f"Atender observación {ob['numero']}: {(req or {}).get('nombre_requisito', ob['texto'][:60])}",
                    "a": area, "ru": r["usuario_id"], "rn": r["responsable"], "fc": compromiso})
            obs_detalle.append({**ob, "requisito": (req or {}).get("nombre_requisito", ""), "texto_clausula": texto_cl})
        # borrador del escrito de respuesta
        tramite = self._tramite(of["tramite_id"])
        oficio_info = {"numero_oficio": datos.get("numero_oficio"), "folio": of["folio"], "plazo_dias_habiles": plazo,
                       "fecha_limite": limite}
        borrador = self.ia_texto(O.contexto_borrador(oficio_info, tramite, obs_detalle))
        self.q(f"DELETE FROM {self.A}.borradores WHERE oficio_id = :o", {"o": oficio_id})
        self.q(f"INSERT INTO {self.A}.borradores VALUES (:o, :t, :tx, :m, CURRENT_TIMESTAMP())",
               {"o": oficio_id, "t": of["tramite_id"], "tx": borrador, "m": self.MODELO})
        asunto, cuerpo = O.alerta_oficio({**oficio_info, "numero_oficio": datos.get("numero_oficio")}, tramite,
                                         len(obs_detalle), ", ".join(sorted(areas)))
        self._alerta("Oficio analizado", of["tramite_id"], oficio_id, asunto, cuerpo)
        return {"oficio_id": oficio_id, "observaciones": len(obs_detalle), "plazo": plazo, "fecha_limite": limite}

    @staticmethod
    def _requisito(ob, docs):
        cands = [d for d in docs if d["seccion_ctd"] == ob.get("seccion_ctd")]
        if len(cands) <= 1:
            return cands[0] if cands else None
        palabras = set(re.findall(r"\w{5,}", ob["texto"].lower()))
        return max(cands, key=lambda d: len(palabras & set(re.findall(r"\w{5,}", d["nombre_requisito"].lower()))))

    # ------------------------------------------------------------------------------------------ 4. seguimiento
    def cerrar_tarea(self, tarea_id):
        self.q(f"UPDATE {self.A}.tareas_oficio SET estatus = 'Cerrada', cerrada_en = CURRENT_TIMESTAMP() WHERE tarea_id = :i", {"i": tarea_id})

    def guardar_borrador(self, oficio_id, texto):
        self.q(f"UPDATE {self.A}.borradores SET texto = :tx, generado_en = CURRENT_TIMESTAMP() WHERE oficio_id = :o",
               {"tx": texto, "o": oficio_id})

    def generar_recordatorios(self, umbral=3):
        n = 0
        for p in self.q(f"SELECT * FROM {self.N}.prevenciones_en_curso WHERE dias_habiles_restantes <= {int(umbral)}"):
            ref = f"{p['aviso_id']}|{p['accion_pendiente']}|{p['dias_habiles_restantes']}"
            if self.q(f"SELECT 1 AS x FROM {self.A}.alertas WHERE referencia = :r", {"r": ref}):
                continue
            asunto, cuerpo = O.alerta_recordatorio(p)
            self._alerta("Recordatorio de plazo", p["tramite_id"], ref, asunto, cuerpo)
            n += 1
        return n

    def reiniciar_prevenciones(self):
        for t in ["avisos", "acciones", "oficios", "observaciones_oficio", "tareas_oficio", "borradores", "alertas"]:
            self.q(f"DELETE FROM {self.A}.{t}")
