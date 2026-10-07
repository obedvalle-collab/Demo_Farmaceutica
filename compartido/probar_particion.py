"""Prueba local de partir_clausulas.py con el texto de los PDF (extraído con PyMuPDF, sin IA).

Uso: python compartido/probar_particion.py
"""
import csv
import sys
from pathlib import Path

import pymupdf

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
from partir_clausulas import partir, fragmentar  # noqa: E402

# Cláusulas que el buscador debe encontrar en el examen de la Fase 2
ESPERADAS = [("NOM-073-SSA1-2015", "8.5.1"), ("NOM-073-SSA1-2015", "8.1"), ("NOM-072-SSA1-2012", "6.1.4"),
             ("NOM-072-SSA1-2012", "5.31.7"), ("NOM-072-SSA1-2012", "5.19"), ("NOM-177-SSA1-2013", "9.6.4"),
             ("NOM-177-SSA1-2013", "7.5.5"), ("NOM-220-SSA1-2016", "8.4.3.1.4"), ("NOM-059-SSA1-2015", "9.9.2.2.3"),
             ("NOM-257-SSA1-2014", "6.1.3"), ("RIS", "Art. 167"), ("LGS", "Art. 376")]


def main():
    res = {}
    for r in csv.DictReader(open(AQUI / "catalogo_normas.csv", encoding="utf-8")):
        d = pymupdf.open(AQUI.parent / "normas" / r["archivo"])
        cl = partir("\n".join(p.get_text() for p in d), r["clave"], r["tipo"])
        res[r["clave"]] = cl
        fr = sum(len(fragmentar(c["texto"], c["numeral"])) for c in cl)
        print(f"{r['clave']:24s} págs={d.page_count:4d} cláusulas={len(cl):5d} fragmentos={fr:5d} "
              f"últimas={[c['numeral'] for c in cl[-3:]]}")
    print()
    ok = 0
    for norma, num in ESPERADAS:
        c = next((c for c in res[norma] if c["numeral"] == num), None)
        ok += c is not None
        print(f"{'OK ' if c else 'FALTA'} {norma} {num}: " + (f"[{c['titulo'][:70]}] {c['texto'][:110]}" if c else ""))
    print(f"\n{ok}/{len(ESPERADAS)} cláusulas de control encontradas")


if __name__ == "__main__":
    main()
