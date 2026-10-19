"""Memoria de lecturas para la app (la misma en ambas plataformas).

Streamlit vuelve a ejecutar la página completa en cada clic; sin memoria, cada clic repite todas las consultas. Aquí se
guardan los resultados de las lecturas por la sesión del usuario y se reutilizan hasta que:
  - la app escribe algo (cualquier INSERT/UPDATE/DELETE/MERGE vacía la memoria),
  - pasan TTL segundos, o
  - el usuario pulsa "Actualizar".
No se guarda lo que cambia el robot desde fuera (envíos, avisos, oficios, tareas, alertas) ni las llamadas a la IA.
Si memo es None (robot, scripts) no se guarda nada.
"""
import time

TTL = 120
VOLATILES = ("envio", "aviso", "accion", "oficio", "tarea", "borrador", "alerta", "prevenciones_en_curso",
             "trabajo", "preauditoria", "comparacion")   # trabajo: escritos por los trabajos en segundo plano
SIN_MEMORIA = ("ai_complete", "ai_parse", "ai_query", "ai_parse_document", "cortex", "data_agent_run", "search_preview")


class Memoria:
    memo = None

    def vaciar_memoria(self):
        if self.memo is not None:
            self.memo.clear()

    def _con_memoria(self, sql, params, ejecutar):
        texto = sql.lstrip().lower()
        if not texto.startswith(("select", "with")):
            self.vaciar_memoria()          # una escritura: lo leído antes puede estar viejo
            return ejecutar()
        if self.memo is None or any(v in texto for v in VOLATILES) or any(v in texto for v in SIN_MEMORIA):
            return ejecutar()
        clave = (sql, repr(sorted(params.items())) if isinstance(params, dict) else repr(params))
        guardado = self.memo.get(clave)
        if guardado and time.time() - guardado[0] < TTL:
            return [dict(f) for f in guardado[1]]
        filas = ejecutar()
        self.memo[clave] = (time.time(), [dict(f) for f in filas])
        return filas
