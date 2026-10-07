"""Vista 4 · Pre-auditoría ("simulador COFEPRIS"): la IA actúa como dictaminador y predice las prevenciones probables
antes del envío, citando la cláusula. Combina tres fuentes: el estado del expediente (documentos y datos extraídos),
los hallazgos de la revisión automática y el historial de observaciones de trámites parecidos.
Mismo código en ambas plataformas; cada una aporta q(), ia_json() y MODELO."""
import json
import time
import uuid

ESQUEMA_PREAUDITORIA = {
    "type": "object",
    "properties": {
        "riesgo": {"type": "string", "enum": ["Alto", "Medio", "Bajo"]},
        "resumen": {"type": "string"},
        "prevenciones": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "seccion_ctd": {"type": "string"}, "requisito": {"type": "string"}, "observacion": {"type": "string"},
                "norma": {"type": "string"}, "clausula": {"type": "string"},
                "probabilidad": {"type": "string", "enum": ["Alta", "Media", "Baja"]},
                "motivo": {"type": "string"}, "recomendacion": {"type": "string"}},
            "required": ["seccion_ctd", "requisito", "observacion", "norma", "clausula", "probabilidad", "motivo", "recomendacion"],
            "additionalProperties": False}},
    },
    "required": ["riesgo", "resumen", "prevenciones"],
    "additionalProperties": False,
}

INSTRUCCION_PREAUDITORIA = """Eres dictaminador de la Comisión de Autorización Sanitaria de COFEPRIS. Antes de que la empresa envíe su solicitud, haces una pre-auditoría del expediente CTD y predices las observaciones que emitirías en un oficio de prevención.

Recibes:
- tramite: producto y tipo de trámite.
- expediente: cada requisito con su estatus, versión y los datos que se extrajeron del documento.
- hallazgos_automaticos: defectos ya detectados por reglas, con norma y numeral.
- historial: las observaciones más frecuentes en trámites parecidos (frecuencia relativa), con norma y numeral.
- clausulas: texto de los numerales citados.

Instrucciones:
- Lista las prevenciones probables, de la más a la menos probable (máximo 10).
- Cada una debe citar la norma y el numeral exactos que aparecen en la información recibida (no inventes numerales).
- probabilidad "Alta" si hay evidencia directa en el expediente (hallazgo, faltante o dato extraído que incumple); "Media" si el documento existe pero el historial muestra que suele observarse y los datos no permiten descartarlo; "Baja" si es solo un patrón histórico.
- motivo: la evidencia concreta (qué dato o qué patrón). recomendacion: qué corregir antes de enviar.
- No repitas la misma observación dos veces. No inventes datos del expediente.
- riesgo: "Alto" si hay alguna prevención Alta de severidad mayor o 3 o más Altas; "Medio" si hay alguna Alta o varias Medias; "Bajo" en otro caso.
- resumen: 2 oraciones para la dirección de Asuntos Regulatorios.

Información:
"""

CAMPOS_EXTRAIDOS = ["tipo_documento", "emisor", "fabricante_farmaco", "fecha_emision", "numero_lotes_estudio", "firmas_vacias",
                    "leyenda_receta_medica", "leyenda_no_alcance_ninos", "leyenda_farmacovigilancia", "leyenda_venta_fraccionada",
                    "siglas_mbb", "codigo_postal_fabricante", "ic90_cmax_inferior", "ic90_cmax_superior", "f2_minimo",
                    "pruebas_fuera_especificacion", "conclusion_favorable", "meses_largo_plazo", "evalua_excursiones_temperatura",
                    "es_legible", "resumen"]


class PreAuditoria:
    L = N = A = ""

    def tramites_preauditables(self):
        return self.q(f"""SELECT c.tramite_id, c.producto, c.tipo_tramite, c.candado, c.requisitos, c.con_hallazgos, c.faltantes,
                                 p.riesgo, p.generado_en
                          FROM {self.N}.candado_envio c
                          LEFT JOIN (SELECT tramite_id, riesgo, generado_en,
                                            ROW_NUMBER() OVER (PARTITION BY tramite_id ORDER BY generado_en DESC) AS rn
                                     FROM {self.A}.preauditorias) p ON p.tramite_id = c.tramite_id AND p.rn = 1
                          WHERE c.tramite_id IN (SELECT tramite_id FROM {self.A}.cargas)
                          ORDER BY c.tramite_id DESC""")

    def ultima_preauditoria(self, tramite):
        r = self.q(f"""SELECT preauditoria_id, modelo, riesgo, resultado, segundos, generado_en, generado_por
                       FROM {self.A}.preauditorias WHERE tramite_id = :t ORDER BY generado_en DESC LIMIT 1""", {"t": tramite})
        return {**r[0], "resultado": json.loads(r[0]["resultado"])} if r else None

    def contexto_preauditoria(self, tramite, version_maxima=None):
        """Arma lo que ve el dictaminador. version_maxima=1 reconstruye el expediente tal como se envió."""
        t = self.q(f"""SELECT t.tramite_id, t.producto, t.tipo_tramite, t.familia, t.homoclave, p.tipo_producto,
                              p.forma_farmaceutica, p.cronico, p.fraccion_lgs_226
                       FROM {self.L}.tramites t JOIN {self.L}.productos p ON p.producto_id = t.producto_id
                       WHERE t.tramite_id = :t""", {"t": tramite})[0]
        filtro_version = f"AND c.version <= {int(version_maxima)}" if version_maxima else ""
        exp = self.q(f"""
            WITH vig AS (SELECT c.*, ROW_NUMBER() OVER (PARTITION BY c.requisito_id ORDER BY c.version DESC) AS rn
                         FROM {self.A}.cargas c WHERE c.tramite_id = :t {filtro_version})
            SELECT d.requisito_id, d.seccion_ctd, d.nombre_requisito, d.estatus AS estatus_catalogo, v.archivo, v.version,
                   {", ".join("x." + c for c in CAMPOS_EXTRAIDOS)}
            FROM {self.L}.documentos d
            LEFT JOIN vig v ON v.requisito_id = d.requisito_id AND v.rn = 1
            LEFT JOIN {self.L}.documentos_extraidos x ON x.archivo = v.archivo
            WHERE d.tramite_id = :t ORDER BY d.seccion_ctd""", {"t": tramite})
        archivos = [e["archivo"] for e in exp if e["archivo"]]
        expediente = [{"seccion_ctd": e["seccion_ctd"], "requisito": e["nombre_requisito"],
                       "estatus": f"Cargado v{e['version']}" if e["archivo"] else "Faltante"
                                  if e["estatus_catalogo"] == "Faltante" else "Presentado (contenido no disponible para revisión)",
                       "datos": {k: e[k] for k in CAMPOS_EXTRAIDOS if e.get(k) not in (None, "", "[]")} if e["archivo"] else {}}
                      for e in exp]
        hall = [h for h in self.q(f"""SELECT archivo, seccion_ctd, hallazgo, norma, clausula, severidad FROM {self.N}.hallazgos_ia
                                      WHERE tramite_id = :t""", {"t": tramite}) if h["archivo"] in archivos]
        historial = self.q(f"""
            SELECT o.seccion_ctd, o.norma, o.clausula, MIN(o.texto) AS ejemplo, MIN(o.severidad) AS severidad,
                   COUNT(*) AS veces, COUNT(DISTINCT o.tramite_id) AS tramites
            FROM {self.L}.observaciones o
            JOIN {self.L}.tramites t ON t.tramite_id = o.tramite_id
            JOIN {self.L}.productos p ON p.producto_id = t.producto_id
            WHERE t.familia = :f AND p.tipo_producto = :p AND o.tramite_id <> :t AND NOT t.es_activo
            GROUP BY o.seccion_ctd, o.norma, o.clausula ORDER BY veces DESC LIMIT 20""",
                           {"f": t["familia"], "p": t["tipo_producto"], "t": tramite})
        total = self.q(f"""SELECT COUNT(DISTINCT t.tramite_id) AS n FROM {self.L}.tramites t
                           JOIN {self.L}.productos p ON p.producto_id = t.producto_id
                           WHERE t.familia = :f AND p.tipo_producto = :p AND NOT t.es_activo""",
                       {"f": t["familia"], "p": t["tipo_producto"]})[0]["n"]
        for h in historial:
            h["frecuencia"] = f"{h.pop('tramites')} de {total} trámites parecidos"
        citas = {(h["norma"], h["clausula"]) for h in hall + historial if h["norma"] and h["clausula"]}
        clausulas = []
        for norma, numeral in sorted(citas):
            c = self.q(f"SELECT texto FROM {self.L}.normas_clausulas WHERE norma = :n AND numeral = :u",
                       {"n": norma, "u": numeral})
            if c:
                clausulas.append({"norma": norma, "numeral": numeral, "texto": (c[0]["texto"] or "")[:700]})
        return {"tramite": t, "expediente": expediente, "hallazgos_automaticos": hall, "historial": historial,
                "clausulas": clausulas}

    def preauditar(self, tramite, usuario="demo", version_maxima=None, guardar=True):
        ctx = self.contexto_preauditoria(tramite, version_maxima)
        t = time.time()
        r = self.ia_json(INSTRUCCION_PREAUDITORIA + json.dumps(ctx, ensure_ascii=False, default=str), ESQUEMA_PREAUDITORIA)
        seg = round(time.time() - t, 1)
        if guardar:
            self.q(f"""INSERT INTO {self.A}.preauditorias (preauditoria_id, tramite_id, modelo, riesgo, resultado, segundos,
                                                            generado_en, generado_por)
                       VALUES (:i, :t, :m, :r, :j, :s, CURRENT_TIMESTAMP(), :u)""",
                   {"i": str(uuid.uuid4()), "t": tramite, "m": self.MODELO, "r": r["riesgo"],
                    "j": json.dumps(r, ensure_ascii=False), "s": seg, "u": usuario})
        return r, seg


# ------------------------------------------------------------------------------------------------ examen
EXAMEN = ["TR-2026-017", "TR-2026-022", "TR-2026-025"]   # trámites con oficio de prevención real en los datos


def examen_preauditoria(d):
    """Pre-audita los expedientes tal como se enviaron (versión 1) y compara contra lo que COFEPRIS sí observó.
    El oficio real no forma parte de lo que ve la IA (el historial excluye al propio trámite)."""
    filas = []
    for tramite in EXAMEN:
        r, seg = d.preauditar(tramite, "examen", version_maxima=1)
        reales = d.q(f"""SELECT o.seccion_ctd, o.norma, o.clausula, o.texto FROM {d.L}.prevenciones pr
                         JOIN {d.L}.observaciones o ON o.prevencion_id = pr.prevencion_id
                         WHERE pr.tramite_id = :t AND pr.estatus IN ('Abierta', 'Sin abrir')""", {"t": tramite})
        pred = r["prevenciones"]
        detalle = []
        for o in reales:
            misma_seccion = [p for p in pred if p["seccion_ctd"] == o["seccion_ctd"]]
            exacta = [p for p in misma_seccion if o["norma"] and p["norma"] == o["norma"] and p["clausula"] == o["clausula"]]
            detalle.append({"real": f"{o['seccion_ctd']} {o['norma'] or 'Administrativa'} {o['clausula'] or ''}".strip(),
                            "texto": o["texto"], "anticipada_seccion": bool(misma_seccion), "anticipada_clausula": bool(exacta),
                            "probabilidad": (exacta or misma_seccion or [{"probabilidad": "—"}])[0]["probabilidad"]})
        filas.append({"tramite": tramite, "segundos": seg, "riesgo": r["riesgo"], "predichas": len(pred),
                      "reales": len(reales), "anticipadas_seccion": sum(x["anticipada_seccion"] for x in detalle),
                      "anticipadas_clausula": sum(x["anticipada_clausula"] for x in detalle), "detalle": detalle,
                      "prediccion": r})
        print(f"  {tramite}: riesgo {r['riesgo']} · {len(pred)} predichas · reales {len(reales)} · "
              f"anticipadas {filas[-1]['anticipadas_seccion']} (sección) / {filas[-1]['anticipadas_clausula']} (cláusula exacta) · {seg} s")
    tot = {k: sum(f[k] for f in filas) for k in ["reales", "anticipadas_seccion", "anticipadas_clausula", "predichas"]}
    print(f"  TOTAL: {tot['anticipadas_seccion']}/{tot['reales']} por sección · {tot['anticipadas_clausula']}/{tot['reales']} "
          f"con cláusula exacta · {tot['predichas']} predicciones")
    return {"total": tot, "tramites": filas}
