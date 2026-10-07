"""Experimento Fase 2 (Databricks): precalcular los vectores con ai_query por lotes y crear el índice de
Vector Search con vectores ya hechos ("self-managed embeddings"), para comparar contra los 56 min de la
sincronización administrada.

Uso: python databricks/fase2_vectores_precalculados.py
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fase2_normas as F  # noqa: E402  (reutiliza conexión, sql(), endpoint y examen)
from databricks.sdk.service.vectorsearch import (DeltaSyncVectorIndexSpecRequest, EmbeddingVectorColumn,  # noqa: E402
                                                 PipelineType, VectorIndexType)

TABLA_VEC = f"{F.CAT}.limpio.normas_fragmentos_vec"
INDICE_VEC = f"{F.CAT}.ia.buscador_normas_vec"
T = {}


def vectorizar_consulta(texto):
    r = F.w.serving_endpoints.query(name=F.MODELO_EMB, input=[texto])
    return r.data[0].embedding


def main():
    t0 = time.time()
    F.iniciar_endpoint()                          # arranca el endpoint mientras se calculan los vectores
    print("▶ Vectores por lotes con ai_query")
    t = time.time()
    F.sql(f"""CREATE OR REPLACE TABLE {TABLA_VEC} TBLPROPERTIES (delta.enableChangeDataFeed = true) AS
              SELECT *, ai_query('{F.MODELO_EMB}', texto_busqueda) AS embedding
              FROM {F.CAT}.limpio.normas_fragmentos""", espera=7200)
    T["vectores_ai_query_s"] = round(time.time() - t, 1)
    filas, dim = F.sql(f"SELECT count(*), max(size(embedding)) FROM {TABLA_VEC}")[0]
    print(f"  ✓ {filas} vectores de dimensión {dim} en {T['vectores_ai_query_s']} s")

    print("▶ Esperando endpoint")
    while F.w.vector_search_endpoints.get_endpoint(F.ENDPOINT_VS).endpoint_status.state.value != "ONLINE":
        time.sleep(20)
    T["endpoint_listo_desde_inicio_s"] = round(time.time() - t0, 1)
    print(f"  ✓ endpoint listo a los {T['endpoint_listo_desde_inicio_s']} s")

    print("▶ Índice con vectores precalculados")
    t = time.time()
    F.w.vector_search_indexes.create_index(
        name=INDICE_VEC, endpoint_name=F.ENDPOINT_VS, primary_key="fragmento_id",
        index_type=VectorIndexType.DELTA_SYNC,
        delta_sync_index_spec=DeltaSyncVectorIndexSpecRequest(
            source_table=TABLA_VEC, pipeline_type=PipelineType.TRIGGERED,
            embedding_vector_columns=[EmbeddingVectorColumn(name="embedding", embedding_dimension=int(dim))],
            columns_to_sync=["fragmento_id", "clausula_id", "norma", "tipo", "estatus", "numeral", "titulo",
                             "texto_busqueda", "embedding"]))
    ultimo = None
    while True:
        s = F.w.vector_search_indexes.get_index(INDICE_VEC).status
        if s.indexed_row_count != ultimo:
            print(f"  {time.strftime('%H:%M:%S')} filas indexadas: {s.indexed_row_count}")
            ultimo = s.indexed_row_count
        if s.ready:
            break
        time.sleep(20)
    T["indice_vectores_precalculados_s"] = round(time.time() - t, 1)
    print(f"  ✓ índice listo en {T['indice_vectores_precalculados_s']} s")

    print("▶ Examen (vector de la pregunta calculado con el mismo modelo)")
    from examen_buscador import PREGUNTAS, calificar
    resumen = {}
    for modo, filtro in [("todas_las_normas", None), ("solo_vigentes", '{"estatus": "Vigente"}')]:
        ok_c = ok_n = 0; lat = []; filas_ex = []
        for pregunta, norma, numeral in PREGUNTAS:
            t = time.time()
            r = F.w.vector_search_indexes.query_index(
                index_name=INDICE_VEC, columns=["norma", "numeral", "titulo"], query_text=pregunta,
                query_vector=vectorizar_consulta(pregunta), num_results=5, query_type="HYBRID", filters_json=filtro)
            lat.append(round((time.time() - t) * 1000))
            res = [(x[0], x[1]) for x in (r.result.data_array or [])]
            ok, okn, pos = calificar(res, norma, numeral)
            ok_c += ok; ok_n += okn
            filas_ex.append(dict(pregunta=pregunta, esperada=f"{norma} {numeral}", acierto_top3=ok, posicion=pos,
                                 latencia_ms=lat[-1], top3=[f"{n} {c}" for n, c in res[:3]]))
        resumen[modo] = dict(acierto_clausula_top3=f"{ok_c}/{len(PREGUNTAS)}", acierto_norma_top3=f"{ok_n}/{len(PREGUNTAS)}",
                             latencia_ms_mediana=sorted(lat)[len(lat) // 2], preguntas=filas_ex)
        print(f"  {modo}: cláusula {ok_c}/{len(PREGUNTAS)} · norma {ok_n}/{len(PREGUNTAS)} · mediana {sorted(lat)[len(lat)//2]} ms")
    salida = dict(plataforma="Databricks (vectores precalculados con ai_query)", fecha=datetime.now().isoformat(timespec="seconds"),
                  tiempos_s=T, **resumen)
    (F.RESULTADOS / "fase2_databricks_vectores_precalculados.json").write_text(
        json.dumps(salida, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
