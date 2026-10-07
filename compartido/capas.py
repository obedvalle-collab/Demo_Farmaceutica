"""Piezas compartidas de la Fase 3: sentencias de negocio, controles de calidad y comparación entre plataformas."""
import csv
import re
from decimal import Decimal
from pathlib import Path

import esquema_tablas as E

AQUI = Path(__file__).resolve().parent
VISTAS_NEGOCIO = ["cobertura_ctd", "cobertura_ctd_modulo", "plazos_prevenciones", "registros_vigencia", "portafolio",
                  "kpi_observaciones_norma", "kpi_desempeno", "kpi_areas"]


def sentencias_negocio(limpio, negocio):
    texto = (AQUI / "sql" / "negocio.sql").read_text(encoding="utf-8")
    texto = re.sub(r"--[^\n]*", "", texto)
    texto = texto.replace("{L}", limpio).replace("{N}", negocio)
    return [s.strip() for s in texto.split(";") if s.strip()]


def sql_calidad(crudo, limpio):
    """Una sola consulta con todos los controles: llaves únicas, llaves foráneas y conversiones fallidas."""
    partes = []
    for t, k in E.LLAVES.items():
        partes.append(f"SELECT 'Llave única' AS control, '{t}.{k}' AS objeto, COUNT(*) - COUNT(DISTINCT {k}) AS filas_con_problema FROM {limpio}.{t}")
        partes.append(f"SELECT 'Llave no nula', '{t}.{k}', SUM(CASE WHEN {k} IS NULL THEN 1 ELSE 0 END) FROM {limpio}.{t}")
    for t, c, rt, rc in E.FORANEAS:
        partes.append(f"SELECT 'Llave foránea', '{t}.{c} → {rt}.{rc}', COUNT(*) FROM {limpio}.{t} x "
                      f"LEFT JOIN {limpio}.{rt} y ON y.{rc} = x.{c} WHERE x.{c} IS NOT NULL AND y.{rc} IS NULL")
    for t in E.tablas():
        for c in E.columnas(t):
            if E.tipo(c) != "string":   # valores con dato en crudo que quedaron vacíos al convertir
                partes.append(f"SELECT 'Conversión de tipo', '{t}.{c} ({E.tipo(c)})', "
                              f"(SELECT COUNT(*) FROM {crudo}.{t} WHERE NULLIF(TRIM({c}), '') IS NOT NULL) - "
                              f"(SELECT COUNT(*) FROM {limpio}.{t} WHERE {c} IS NOT NULL)")
        partes.append(f"SELECT 'Filas cargadas', '{t}', "
                      f"(SELECT COUNT(*) FROM {crudo}.{t}) - (SELECT COUNT(*) FROM {limpio}.{t})")
    cuerpo = "\nUNION ALL\n".join(partes)
    return (f"SELECT control, objeto, filas_con_problema, "
            f"CASE WHEN filas_con_problema = 0 THEN 'OK' ELSE 'FALLA' END AS resultado FROM (\n{cuerpo}\n) q")


def normalizar(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return str(v).lower()
    s = str(v)
    if s in ("True", "False"):
        return s.lower()
    if isinstance(v, (int, float, Decimal)) or re.fullmatch(r"-?\d+(\.\d+)?", s):
        x = float(s)
        return str(int(x)) if x.is_integer() else f"{x:.1f}"
    return s[:10] if re.fullmatch(r"\d{4}-\d{2}-\d{2}([ T]00:00:00(\.0+)?)?", s) else s


def guardar(destino, columnas, filas):
    destino.parent.mkdir(parents=True, exist_ok=True)
    norm = sorted([normalizar(v) for v in f] for f in filas)
    with open(destino, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([c.lower() for c in columnas])
        w.writerows(norm)


def comparar(dir_a, dir_b):
    """Compara las vistas exportadas por ambas plataformas. Devuelve lista de (vista, filas_a, filas_b, iguales)."""
    out = []
    for v in VISTAS_NEGOCIO:
        a = (dir_a / f"{v}.csv").read_text(encoding="utf-8").splitlines()
        b = (dir_b / f"{v}.csv").read_text(encoding="utf-8").splitlines()
        out.append((v, len(a) - 1, len(b) - 1, a == b, [x for x in a if x not in b][:3], [x for x in b if x not in a][:3]))
    return out
