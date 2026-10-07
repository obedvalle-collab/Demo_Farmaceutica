"""Fase 7 · Vista 8 en Databricks: espacio Genie (datos del negocio) + agente con herramientas (gpt-oss-120b) que
combina Genie y el buscador de normas (Vector Search). El espacio Genie se genera desde compartido/modelo_semantico.py,
el mismo diccionario que la vista semántica de Snowflake.

Uso:
    python databricks/fase7_asistente.py crear                 # crea o actualiza el espacio Genie
    python databricks/fase7_asistente.py preguntar "¿...?"
    python databricks/fase7_asistente.py examen
"""
import json
import sys
import time
import uuid
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
for p in ("databricks", "app/comun", "compartido"):
    sys.path.insert(0, str(RAIZ / p))
import fase2_normas as F  # noqa: E402
import modelo_semantico as M  # noqa: E402
from datos_databricks import TITULO_GENIE, DatosDatabricks  # noqa: E402

CAT = F.CAT
w = F.w


def _id(texto):
    return uuid.uuid5(uuid.NAMESPACE_URL, texto).hex   # 32 hex en minúsculas, estable


def espacio_serializado():
    tablas = []
    for t in M.TABLAS:
        tablas.append({"identifier": f"{CAT}.{t['esquema']}.{t['nombre']}", "description": [t["descripcion"]],
                       "column_configs": sorted([{"column_name": c, "description": [d], **({"synonyms": s} if s else {})}
                                                 for c, _, d, s in t["columnas"]], key=lambda x: x["column_name"])})
    relaciones = "; ".join(f"{a}.{c} = {b}.{c}" for a, c, b in M.RELACIONES)
    instrucciones = [M.INSTRUCCIONES_DATOS, f"Relaciones entre tablas: {relaciones}.",
                     "Métricas habituales: " + "; ".join(f"{n} = {e} ({d})" for _, n, e, d in M.METRICAS) + "."]
    return json.dumps({
        "version": 2,
        "config": {"sample_questions": sorted([{"id": _id(q), "question": [q]} for q in M.PREGUNTAS_EJEMPLO], key=lambda x: x["id"])},
        "data_sources": {"tables": sorted(tablas, key=lambda x: x["identifier"])},
        "instructions": {"text_instructions": [{"id": _id("instrucciones"), "content": instrucciones}]},
    }, ensure_ascii=False)


def crear():
    t = time.time()
    existente = next((s for s in (w.genie.list_spaces().spaces or []) if s.title == TITULO_GENIE), None)
    if existente:
        w.genie.update_space(existente.space_id, serialized_space=espacio_serializado(), warehouse_id=F.WAREHOUSE)
        sid = existente.space_id
    else:
        sid = w.genie.create_space(F.WAREHOUSE, espacio_serializado(), title=TITULO_GENIE,
                                   description="Datos regulatorios de Laboratorios Altamira (demo Obed Farmacéutica)").space_id
    print(f"  espacio Genie {sid} ({round(time.time() - t, 1)} s)")
    return sid


def main():
    accion = sys.argv[1] if len(sys.argv) > 1 else "crear"
    try:
        if accion == "crear":
            crear()
        else:
            d = DatosDatabricks(w, F.WAREHOUSE)
            if accion == "preguntar":
                print(json.dumps(d.preguntar(sys.argv[2], []), ensure_ascii=False, indent=1, default=str)[:4000])
            elif accion == "examen":
                from asistente import examen_asistente
                examen_asistente(d, "databricks")
    finally:
        w.warehouses.stop(F.WAREHOUSE)


if __name__ == "__main__":
    main()
