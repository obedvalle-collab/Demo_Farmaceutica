"""Vista 6 · Control de versiones: qué cambió entre la versión anterior y la corregida, y si la corrección atiende
lo observado (hallazgos de la revisión automática y observaciones de COFEPRIS). Mismo código en ambas plataformas;
cada una aporta q(), ia_json() y MODELO (ver ciclo_prevencion.py)."""
import difflib
import json
import time

ESQUEMA_CORRECCION = {
    "type": "object",
    "properties": {
        "veredicto": {"type": "string", "enum": ["Atiende", "Parcial", "No atiende"]},
        "resumen": {"type": "string"},
        "observaciones": {"type": "array", "items": {
            "type": "object",
            "properties": {"observacion": {"type": "string"}, "atendida": {"type": "string", "enum": ["Si", "Parcial", "No"]},
                           "evidencia": {"type": "string"}},
            "required": ["observacion", "atendida", "evidencia"], "additionalProperties": False}},
        "cambios": {"type": "array", "items": {"type": "string"}},
        "riesgos_nuevos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["veredicto", "resumen", "observaciones", "cambios", "riesgos_nuevos"],
    "additionalProperties": False,
}

INSTRUCCION_CORRECCION = """Eres dictaminador de la autoridad sanitaria mexicana revisando la corrección de un documento de un expediente CTD.
Recibes: el requisito, las observaciones hechas a la versión anterior (con la norma y el texto de la cláusula), el texto de la versión anterior y el de la versión corregida.
Responde:
- observaciones: para cada observación, si la versión corregida la atiende ("Si", "Parcial" o "No") y la evidencia concreta (cita breve del texto corregido o qué falta).
- cambios: lista breve de los cambios relevantes entre ambas versiones (no menciones cambios de formato).
- riesgos_nuevos: problemas que aparecen en la versión corregida y que no estaban antes (lista vacía si no hay).
- veredicto: "Atiende" si todas se atienden, "Parcial" si alguna queda parcial o sin atender pero hay avance, "No atiende" si ninguna.
- resumen: 1–2 oraciones para el responsable del expediente.
Usa solo lo que dicen los textos; no supongas anexos que no veas.

"""

MAX_TEXTO = 7000


class Versiones:
    L = N = A = ""

    def pares_versiones(self):
        return self.q(f"""SELECT p.*, c.veredicto
                          FROM {self.N}.versiones_pares p
                          LEFT JOIN (SELECT tramite_id, requisito_id, archivo_nuevo, MAX(veredicto) AS veredicto
                                     FROM {self.A}.comparaciones GROUP BY tramite_id, requisito_id, archivo_nuevo) c
                                 ON c.tramite_id = p.tramite_id AND c.requisito_id = p.requisito_id AND c.archivo_nuevo = p.archivo_nuevo
                          ORDER BY p.tramite_id DESC, p.seccion_ctd""")

    def _crudo(self):
        return self.L.rsplit(".", 1)[0] + ".crudo"

    def detalle_versiones(self, par):
        a, n = par["archivo_anterior"], par["archivo_nuevo"]
        datos = {r["archivo"]: r for r in self.q(f"SELECT * FROM {self.L}.documentos_extraidos WHERE archivo IN (:a, :n)",
                                                  {"a": a, "n": n})}
        textos = {r["archivo"]: r["texto"] or "" for r in self.q(
            f"SELECT archivo, texto FROM {self._crudo()}.expedientes_parseados WHERE archivo IN (:a, :n)", {"a": a, "n": n})}
        hall = self.q(f"""SELECT h.archivo, h.regla, h.hallazgo, h.norma, h.clausula, h.severidad, c.texto AS texto_clausula
                          FROM {self.N}.hallazgos_ia h
                          LEFT JOIN {self.L}.normas_clausulas c ON c.norma = h.norma AND c.numeral = h.clausula
                          WHERE h.archivo IN (:a, :n)""", {"a": a, "n": n})
        cofepris = self.q(f"""SELECT o.numero, o.texto, o.norma, o.clausula, o.texto_clausula, f.numero_oficio
                              FROM {self.A}.observaciones_oficio o JOIN {self.A}.oficios f ON f.oficio_id = o.oficio_id
                              WHERE f.tramite_id = :t AND o.requisito_id = :r""",
                          {"t": par["tramite_id"], "r": par["requisito_id"]})
        guardada = self.q(f"""SELECT veredicto, resultado, modelo, segundos, generado_en FROM {self.A}.comparaciones
                              WHERE tramite_id = :t AND requisito_id = :r AND archivo_nuevo = :n
                              ORDER BY generado_en DESC LIMIT 1""", {"t": par["tramite_id"], "r": par["requisito_id"], "n": n})
        return {"anterior": datos.get(a, {}), "nuevo": datos.get(n, {}),
                "texto_anterior": textos.get(a, ""), "texto_nuevo": textos.get(n, ""),
                "hallazgos_anterior": [h for h in hall if h["archivo"] == a],
                "hallazgos_nuevo": [h for h in hall if h["archivo"] == n],
                "observaciones_cofepris": cofepris,
                "evaluacion": ({**guardada[0], "resultado": json.loads(guardada[0]["resultado"])} if guardada else None)}

    @staticmethod
    def campos_cambiados(anterior, nuevo):
        ignorar = {"archivo", "modelo", "caracteres_texto", "resumen", "tramite_id"}
        return [(k, anterior.get(k), nuevo.get(k)) for k in nuevo
                if k not in ignorar and str(anterior.get(k)) != str(nuevo.get(k))]

    @staticmethod
    def diferencias_texto(anterior, nuevo, max_lineas=80):
        lineas = list(difflib.unified_diff(anterior.splitlines(), nuevo.splitlines(), "versión anterior", "versión corregida",
                                           lineterm="", n=0))
        return "\n".join(lineas[:max_lineas]) + ("\n…" if len(lineas) > max_lineas else "")

    def evaluar_correccion(self, par, detalle, guardar=True):
        observaciones = [{"origen": "Revisión automática", "observacion": h["hallazgo"], "norma": h["norma"],
                          "clausula": h["clausula"], "texto_clausula": (h["texto_clausula"] or "")[:1200]}
                         for h in detalle["hallazgos_anterior"]]
        observaciones += [{"origen": f"COFEPRIS oficio {o['numero_oficio']}", "observacion": o["texto"], "norma": o["norma"],
                           "clausula": o["clausula"], "texto_clausula": (o["texto_clausula"] or "")[:1200]}
                          for o in detalle["observaciones_cofepris"]]
        entrada = {"requisito": f"{par['seccion_ctd']} {par['nombre_requisito']}", "observaciones": observaciones,
                   "version_anterior": detalle["texto_anterior"][:MAX_TEXTO], "version_corregida": detalle["texto_nuevo"][:MAX_TEXTO]}
        t = time.time()
        r = self.ia_json(INSTRUCCION_CORRECCION + json.dumps(entrada, ensure_ascii=False, indent=1), ESQUEMA_CORRECCION)
        seg = round(time.time() - t, 1)
        if not guardar:
            return r, seg
        self.q(f"""INSERT INTO {self.A}.comparaciones (tramite_id, requisito_id, archivo_anterior, archivo_nuevo, modelo,
                                                        veredicto, resultado, segundos, generado_en)
                   VALUES (:t, :r, :a, :n, :m, :v, :j, :s, CURRENT_TIMESTAMP())""",
               {"t": par["tramite_id"], "r": par["requisito_id"], "a": par["archivo_anterior"], "n": par["archivo_nuevo"],
                "m": self.MODELO, "v": r["veredicto"], "j": json.dumps(r, ensure_ascii=False), "s": seg})
        return r, seg


def control_versiones(d):
    """Prueba de control: cada versión anterior contra sí misma. Lo correcto es "No atiende" (nada cambió)."""
    filas = []
    for par in d.pares_versiones():
        det = d.detalle_versiones(par)
        det = {**det, "texto_nuevo": det["texto_anterior"]}
        r, seg = d.evaluar_correccion({**par, "archivo_nuevo": par["archivo_anterior"]}, det, guardar=False)
        filas.append({"requisito": f"{par['seccion_ctd']} {par['nombre_requisito']}", "segundos": seg, **r})
        print(f"  control {par['seccion_ctd']:<10} {r['veredicto']:<11} {seg:>5} s")
    print(f"  correctos (No atiende): {sum(f['veredicto'] == 'No atiende' for f in filas)}/{len(filas)}")
    return filas
