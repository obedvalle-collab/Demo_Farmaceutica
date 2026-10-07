"""Fase 7 en Snowflake: tablas de resultados de IA (versiones y pre-auditoría) y pruebas en lote.

Uso:
    python snowflake/fase7_preparar.py preparar
    python snowflake/fase7_preparar.py versiones     # la IA evalúa las 8 correcciones de la demo y guarda el resultado
    python snowflake/fase7_preparar.py control       # prueba de control: cada versión contra sí misma
    python snowflake/fase7_preparar.py preauditoria  # examen: predice las prevenciones de 3 trámites con oficio real
"""
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in ("app/comun", "compartido"):
    sys.path.insert(0, str(RAIZ / p))
from snowflake.snowpark import Session  # noqa: E402
from datos_snowflake import BD, DatosSnowflake  # noqa: E402

RESULTADOS = RAIZ / "docs" / "resultados" / "fase7"


def preparar(s):
    texto = (RAIZ / "compartido" / "sql" / "fase7.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto).replace("{L}", f"{BD}.LIMPIO").replace("{N}", f"{BD}.NEGOCIO").replace("{A}", f"{BD}.APP")
    for x in [y.strip() for y in texto.split(";") if y.strip()]:
        s.sql(x).collect()
    print("  tablas y vistas listas")


def versiones(d):
    filas, t0 = [], time.time()
    for par in d.pares_versiones():
        det = d.detalle_versiones(par)
        r, seg = d.evaluar_correccion(par, det)
        filas.append({"requisito": f"{par['seccion_ctd']} {par['nombre_requisito']}", "segundos": seg,
                      "hallazgos_v1": len(det["hallazgos_anterior"]), "obs_cofepris": len(det["observaciones_cofepris"]), **r})
        print(f"  {par['seccion_ctd']:<10} {r['veredicto']:<11} {seg:>5} s · {r['resumen'][:90]}")
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "versiones_snowflake.json").write_text(json.dumps(filas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  total {round(time.time() - t0, 1)} s")


def control(d):
    from versiones import control_versiones
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "versiones_control_snowflake.json").write_text(json.dumps(control_versiones(d), ensure_ascii=False, indent=1),
                                                          encoding="utf-8")


def preauditoria(d):
    from preauditoria import examen_preauditoria
    t0 = time.time()
    r = examen_preauditoria(d)
    d.preauditar("TR-2026-032", "demo")          # la sitagliptina, con su expediente actual, para la app
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    (RESULTADOS / "preauditoria_snowflake.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"  total {round(time.time() - t0, 1)} s")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "preparar"
    s = Session.builder.config("connection_name", "obed_farma").create()
    s.sql("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase7'").collect()
    d = DatosSnowflake(s)
    try:
        {"preparar": lambda: preparar(s), "versiones": lambda: versiones(d), "control": lambda: control(d), "preauditoria": lambda: preauditoria(d)}[accion]()
    finally:
        try:
            s.sql("ALTER WAREHOUSE FARMA_WH SUSPEND").collect()
        except Exception:
            pass
        s.close()


if __name__ == "__main__":
    main()
