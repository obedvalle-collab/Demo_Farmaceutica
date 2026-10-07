"""Genera todo el paquete de datos ficticios: tablas CSV, PDF y hoja de respuestas.

Uso:  python main.py
Salida: datos/salida/ (se puede borrar y regenerar; la semilla fija da siempre el mismo resultado).
"""
import time
from collections import Counter

import gen_pdfs
import gen_tablas
from config import SALIDA, HOY


def main():
    t0 = time.time()
    tablas, tramites, usuarios = gen_tablas.generar()
    t1 = time.time()
    indice, defectos = gen_pdfs.generar(tablas, tramites, usuarios)
    t2 = time.time()

    lineas = ["# Paquete de datos ficticios – Laboratorios Altamira", "",
              f"Generado con semilla fija; fecha de referencia de la demo: {HOY.isoformat()}.", "",
              "## Tablas (`tablas/`)", "", "| Tabla | Filas |", "|---|---|"]
    lineas += [f"| {k} | {len(v):,} |" for k, v in tablas.items()]
    lineas += ["", f"## PDF (`pdf/`): {len(indice)} archivos", "",
               "| Trámite | Producto | PDF | Escaneados | Defectos |", "|---|---|---|---|---|"]
    por_tramite = {}
    for i in indice:
        r = por_tramite.setdefault(i["tramite_id"], dict(producto=i["producto"], n=0, esc=0, df=0))
        r["n"] += 1; r["esc"] += bool(i["escaneado"]); r["df"] += int(i["defectos_sembrados"])
    lineas += [f"| {k} | {v['producto']} | {v['n']} | {v['esc']} | {v['df']} |" for k, v in por_tramite.items()]
    lineas += ["", f"## Hoja de respuestas (`defectos_sembrados.csv`): {len(defectos)} defectos", "",
               "| Tipo | Cantidad |", "|---|---|"]
    lineas += [f"| {k} | {v} |" for k, v in Counter(d["tipo_defecto"] for d in defectos).most_common()]
    lineas += ["", f"Tiempo de generación: tablas {t1 - t0:.1f} s, PDF {t2 - t1:.1f} s."]
    (SALIDA / "RESUMEN.md").write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print("\n".join(lineas))


if __name__ == "__main__":
    main()
