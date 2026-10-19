"""Manejador del procedimiento OBED_FARMACEUTICA.APP.EJECUTAR_TRABAJO: ejecuta en Snowflake, en segundo plano, un
trabajo de IA registrado por la app (compartido/trabajos.py), con el mismo código que usa la pantalla."""
from datos_snowflake import DatosSnowflake


def cola(session):
    """Manejador de APP.PROCESAR_COLA (lo llama la tarea APP.TAREA_TRABAJOS)."""
    return f"{DatosSnowflake(session).procesar_cola()} trabajos"


def principal(session, trabajo_id):
    DatosSnowflake(session).ejecutar_trabajo(trabajo_id)
    return "ok"
