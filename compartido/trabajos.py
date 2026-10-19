"""Cola de trabajos de IA en segundo plano (B5 y B6 del plan de rendimiento).

La app registra un trabajo en {A}.trabajos y despierta a la plataforma, que lo ejecuta con este mismo código (en
Snowflake: la tarea APP.TAREA_TRABAJOS llama al procedimiento APP.PROCESAR_COLA). La tarea corre por su cuenta en el
servidor, así que el trabajo sigue aunque se cierre la app. Mientras tanto la pantalla muestra el avance leyendo la tabla.

Tipos:
  procesar_documento  leer, clasificar, extraer y revisar un PDF subido a la bandeja; al terminar encadena
                      evaluar_version (si el documento es una versión nueva) y preauditoria del trámite.
  evaluar_version     ¿la corrección atiende lo observado?
  preauditoria        la IA como dictaminador sobre el expediente actual.
"""
import json
import uuid

ACTIVOS = ("En cola", "En curso")


class Trabajos:
    A = N = L = ""

    # ------------------------------------------------------------------------------------------ registro
    def crear_trabajo(self, tipo, tramite_id, parametros=None, usuario="demo"):
        tid = str(uuid.uuid4())
        self.q(f"""INSERT INTO {self.A}.trabajos (trabajo_id, tipo, tramite_id, parametros, estatus, paso, solicitado_por,
                                                   creado_en, actualizado_en)
                   VALUES (:i, :t, :r, :p, 'En cola', 'En cola', :u, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP())""",
               {"i": tid, "t": tipo, "r": tramite_id, "p": json.dumps(parametros or {}, ensure_ascii=False), "u": usuario})
        return tid

    def _avance(self, trabajo_id, paso, estatus="En curso"):
        self.q(f"UPDATE {self.A}.trabajos SET paso = :p, estatus = :e, actualizado_en = CURRENT_TIMESTAMP() WHERE trabajo_id = :i",
               {"p": paso, "e": estatus, "i": trabajo_id})

    def _terminar(self, trabajo_id, resultado=None, error=None):
        self.q(f"""UPDATE {self.A}.trabajos SET estatus = :e, paso = :p, resultado = :r, error = :x, actualizado_en = CURRENT_TIMESTAMP()
                   WHERE trabajo_id = :i""",
               {"e": "Error" if error else "Listo", "p": "Error" if error else "Listo",
                "r": json.dumps(resultado, ensure_ascii=False, default=str) if resultado is not None else None,
                "x": (str(error)[:2000] if error else None), "i": trabajo_id})

    def trabajo(self, trabajo_id):
        r = self.q(f"SELECT * FROM {self.A}.trabajos WHERE trabajo_id = :i", {"i": trabajo_id})
        if not r:
            return None
        t = r[0]
        t["resultado"] = json.loads(t["resultado"]) if t.get("resultado") else None
        return t

    def trabajos_activos(self, tramite_id, tipo=None):
        filtro = "AND tipo = :t" if tipo else ""
        return self.q(f"""SELECT trabajo_id, tipo, paso, estatus, creado_en FROM {self.A}.trabajos
                          WHERE tramite_id = :r AND estatus IN ('En cola', 'En curso') {filtro} ORDER BY creado_en""",
                      {"r": tramite_id, **({"t": tipo} if tipo else {})})

    # ------------------------------------------------------------------------------------------ ejecución
    def _reclamar(self, trabajo_id):
        """Marca el trabajo como propio solo si sigue en cola (si dos ejecuciones lo ven a la vez, solo una gana)."""
        marca = f"Tomado {uuid.uuid4().hex[:8]}"
        self.q(f"""UPDATE {self.A}.trabajos SET estatus = :m, actualizado_en = CURRENT_TIMESTAMP()
                   WHERE trabajo_id = :i AND estatus = 'En cola'""", {"m": marca, "i": trabajo_id})
        r = self.q(f"SELECT estatus FROM {self.A}.trabajos WHERE trabajo_id = :i", {"i": trabajo_id})
        if r and r[0]["estatus"] == marca:
            self._avance(trabajo_id, "Iniciando")
            return True
        return False

    def procesar_cola(self, maximo=25):
        """Ejecuta los trabajos en cola, del más antiguo al más nuevo, hasta vaciarla."""
        hechos = 0
        while hechos < maximo:
            pend = self.q(f"SELECT trabajo_id FROM {self.A}.trabajos WHERE estatus = 'En cola' ORDER BY creado_en LIMIT 1")
            if not pend:
                break
            self.ejecutar_trabajo(pend[0]["trabajo_id"])
            hechos += 1
        return hechos

    def ejecutar_trabajo(self, trabajo_id):
        """Lo corre la plataforma en segundo plano (no la pantalla)."""
        if not self._reclamar(trabajo_id):
            return
        t = self.trabajo(trabajo_id)
        p = json.loads(t["parametros"] or "{}")
        try:
            if t["tipo"] == "procesar_documento":
                r = self.procesar_documento(t["tramite_id"], p["archivo"], avance=lambda paso: self._avance(trabajo_id, paso),
                                            sha256=p.get("sha256"))
                self._terminar(trabajo_id, r, r.get("error"))
                if not r.get("error"):
                    self._posteriores(t["tramite_id"], r, t["solicitado_por"])
            elif t["tipo"] == "evaluar_version":
                self._avance(trabajo_id, "Comparando versiones contra lo observado")
                par = next((x for x in self.pares_versiones() if x["tramite_id"] == t["tramite_id"]
                            and x["archivo_nuevo"] == p["archivo"]), None)
                if not par:
                    self._terminar(trabajo_id, {"omitido": "sin versión anterior"}); return
                ev, seg = self.evaluar_correccion(par, self.detalle_versiones(par))
                self._terminar(trabajo_id, {"veredicto": ev["veredicto"], "segundos": seg})
            elif t["tipo"] == "preauditoria":
                self._avance(trabajo_id, "El dictaminador virtual revisa el expediente")
                r, seg = self.preauditar(t["tramite_id"], t["solicitado_por"])
                self._terminar(trabajo_id, {"riesgo": r["riesgo"], "prevenciones": len(r["prevenciones"]), "segundos": seg})
            else:
                self._terminar(trabajo_id, error=f"Tipo de trabajo desconocido: {t['tipo']}")
        except Exception as e:
            self._terminar(trabajo_id, error=e)

    def _posteriores(self, tramite_id, r, usuario):
        """Adelanta el trabajo de las otras vistas: cuando la persona las abra, el resultado ya está."""
        if int(r.get("version") or 1) > 1:
            self.ejecutar_trabajo(self.crear_trabajo("evaluar_version", tramite_id, {"archivo": r["archivo"]}, usuario))
        self.ejecutar_trabajo(self.crear_trabajo("preauditoria", tramite_id, {}, usuario))
