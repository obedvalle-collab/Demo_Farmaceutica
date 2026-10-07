"""Fase 6 en Snowflake: tablas y vistas del ciclo de prevenciones (el correo usa la integración FARMA_EMAIL).

Uso:
    python snowflake/fase6_preparar.py preparar
    python snowflake/fase6_preparar.py reiniciar      # borra avisos, oficios, tareas y alertas (demo en cero)
    python snowflake/fase6_preparar.py probar_correo  # manda una alerta de prueba a tu correo
"""
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in ("app/comun", "compartido"):
    sys.path.insert(0, str(RAIZ / p))
from snowflake.snowpark import Session  # noqa: E402
from datos_snowflake import BD, DatosSnowflake  # noqa: E402


def preparar(s):
    texto = (RAIZ / "compartido" / "sql" / "prevenciones.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{BD}.LIMPIO").replace("{N}", f"{BD}.NEGOCIO").replace("{A}", f"{BD}.APP")
    for x in [y.strip() for y in texto.split(";") if y.strip()]:
        s.sql(x).collect()
    print("  tablas y vistas listas")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "preparar"
    s = Session.builder.config("connection_name", "obed_farma").create()
    s.sql("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase6'").collect()
    d = DatosSnowflake(s)
    try:
        if accion == "preparar":
            preparar(s)
        elif accion == "reiniciar":
            d.reiniciar_prevenciones(); print("  prevenciones en cero")
        elif accion == "probar_correo":
            d._alerta("Prueba", "TR-2026-032", "prueba", "[Prueba] Correo de alertas desde Snowflake",
                      "<p>Prueba del canal de alertas de la demo <b>Obed Farmacéutica</b>.</p>")
            print("  enviadas:", d.enviar_correos())
    finally:
        try:
            s.sql("ALTER WAREHOUSE FARMA_WH SUSPEND").collect()
        except Exception:
            pass
        s.close()


if __name__ == "__main__":
    main()
