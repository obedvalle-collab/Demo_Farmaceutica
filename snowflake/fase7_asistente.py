"""Fase 7 · Vista 8 en Snowflake: vista semántica (Cortex Analyst) + agente (Cortex Agents) con dos herramientas:
datos del negocio y buscador de normas (Cortex Search). Todo se genera desde compartido/modelo_semantico.py.

Uso:
    python snowflake/fase7_asistente.py crear                 # vista semántica + agente
    python snowflake/fase7_asistente.py preguntar "¿...?"     # prueba una pregunta
    python snowflake/fase7_asistente.py examen                # banco de preguntas del asistente (mismo en ambas)
"""
import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in ("app/comun", "compartido"):
    sys.path.insert(0, str(RAIZ / p))
import modelo_semantico as M  # noqa: E402
from snowflake.snowpark import Session  # noqa: E402

BD = "OBED_FARMACEUTICA"
VISTA = f"{BD}.NEGOCIO.SV_REGULATORIO"
AGENTE = f"{BD}.IA.ASISTENTE_REGULATORIO"
MODELO_AGENTE = "claude-sonnet-4-5"


def _txt(s):
    return s.replace("'", "''")


def _sin(sinonimos):
    return f" WITH SYNONYMS = ({', '.join(repr(x) for x in sinonimos)})" if sinonimos else ""


def sql_vista_semantica():
    tablas, hechos, dims = [], [], []
    for t in M.TABLAS:
        tablas.append(f"{t['nombre']} AS {BD}.{t['esquema'].upper()}.{t['nombre'].upper()} PRIMARY KEY ({', '.join(t['pk'])}) "
                      f"COMMENT = '{_txt(t['descripcion'])}'")
        for col, tipo, desc, sin in t["columnas"]:
            linea = f"{t['nombre']}.{col} AS {col}{_sin(sin)} COMMENT = '{_txt(desc)}'"
            (hechos if tipo == "hecho" else dims).append(linea)
    rel = [f"{a}_{c} AS {a} ({c}) REFERENCES {b}" for a, c, b in M.RELACIONES]
    met = [f"{t}.{n} AS {e} COMMENT = '{_txt(d)}'" for t, n, e, d in M.METRICAS]
    return (f"CREATE OR REPLACE SEMANTIC VIEW {VISTA}\n  TABLES (\n    " + ",\n    ".join(tablas) +
            "\n  )\n  RELATIONSHIPS (\n    " + ",\n    ".join(rel) +
            "\n  )\n  FACTS (\n    " + ",\n    ".join(hechos) +
            "\n  )\n  DIMENSIONS (\n    " + ",\n    ".join(dims) +
            "\n  )\n  METRICS (\n    " + ",\n    ".join(met) +
            f"\n  )\n  COMMENT = '{_txt(M.INSTRUCCIONES_DATOS)}'")


def sql_agente():
    spec = {
        "models": {"orchestration": MODELO_AGENTE},
        "orchestration": {"budget": {"seconds": 90, "tokens": 32000}},
        "instructions": {"response": "Responde en español, breve, y cita la fuente (tabla, o norma y numeral).",
                         "orchestration": M.INSTRUCCIONES_AGENTE + " " + M.INSTRUCCIONES_DATOS,
                         "sample_questions": [{"question": q} for q in M.PREGUNTAS_EJEMPLO]},
        "tools": [
            {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "datos_regulatorios",
                           "description": "Trámites, plazos, prevenciones, registros sanitarios, expedientes CTD e indicadores de Laboratorios Altamira."}},
            {"tool_spec": {"type": "cortex_search", "name": "buscador_normas",
                           "description": "Texto de las NOM, leyes, reglamentos y guías ICH partidos por cláusula (vigentes y proyectos)."}}],
        "tool_resources": {
            "datos_regulatorios": {"semantic_view": VISTA, "execution_environment": {"type": "warehouse", "warehouse": "FARMA_WH"}},
            "buscador_normas": {"search_service": f"{BD}.IA.BUSCADOR_NORMAS", "id_column": "CLAUSULA_ID",
                                "title_column": "TITULO", "max_results": 6}},
    }
    return (f"CREATE OR REPLACE AGENT {AGENTE}\n  COMMENT = 'Asistente regulatorio (demo Obed Farmacéutica)'\n"
            f"  FROM SPECIFICATION $${json.dumps(spec, ensure_ascii=False)}$$")


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "crear"
    s = Session.builder.config("connection_name", "obed_farma").create()
    s.sql("ALTER SESSION SET QUERY_TAG = 'obed_farma_fase7_asistente'").collect()
    try:
        if accion == "crear":
            t = time.time()
            s.sql(sql_vista_semantica()).collect()
            print(f"  vista semántica {VISTA} ({round(time.time() - t, 1)} s)")
            t = time.time()
            s.sql(sql_agente()).collect()
            print(f"  agente {AGENTE} ({round(time.time() - t, 1)} s)")
        elif accion == "sql":
            print(sql_vista_semantica()); print(sql_agente())
        else:
            from datos_snowflake import DatosSnowflake
            d = DatosSnowflake(s)
            if accion == "preguntar":
                r = d.preguntar(sys.argv[2], [])
                print(json.dumps(r, ensure_ascii=False, indent=1, default=str)[:4000])
            elif accion == "examen":
                from asistente import examen_asistente
                examen_asistente(d, "snowflake")
    finally:
        try:
            s.sql("ALTER WAREHOUSE FARMA_WH SUSPEND").collect()
        except Exception:
            pass
        s.close()


if __name__ == "__main__":
    main()
