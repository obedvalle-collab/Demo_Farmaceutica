"""Vista 8 · Asistente regulatorio: formato común de respuesta y examen (mismo en ambas plataformas).

Cada plataforma implementa preguntar(pregunta, historial) con sus piezas nativas y devuelve:
    {"texto": str, "fuentes": [{"tipo": "norma"|"datos", "etiqueta": str, "detalle": str}],
     "sql": [str], "tablas": [{"columnas": [...], "filas": [[...]]}], "pasos": [str], "segundos": float, "tokens": int|None}
"""
import json
import time
import unicodedata
from pathlib import Path


def respuesta_vacia():
    return {"texto": "", "fuentes": [], "sql": [], "tablas": [], "pasos": [], "segundos": 0.0, "tokens": None}


def _norm(s):
    s = str(s)
    for raro, normal in {"‑": "-", "‐": "-", "–": "-", "‒": "-", " ": " ", " ": " "}.items():
        s = s.replace(raro, normal)   # gpt-oss escribe guiones y espacios no separables
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def _esperados(d):
    """Respuestas correctas calculadas de los datos en el momento del examen (no fijas en el código)."""
    urg = d.q(f"SELECT producto FROM {d.N}.registros_vigencia WHERE semaforo = 'Rojo' ORDER BY dias_para_limite_prorroga")
    top = d.q(f"""SELECT norma FROM {d.N}.kpi_observaciones_norma WHERE norma <> 'Administrativa'
                  GROUP BY norma ORDER BY SUM(observaciones) DESC LIMIT 1""")
    total = d.q(f"SELECT COUNT(*) AS n FROM {d.L}.observaciones")[0]["n"]
    los = d.q(f"""SELECT dias_habiles_restantes AS n FROM {d.N}.plazos_prevenciones
                  WHERE tramite_id = 'TR-2026-022' AND semaforo <> 'Cerrada'""")
    falt = d.q(f"""SELECT nombre_requisito FROM {d.N}.expediente_estado WHERE tramite_id = 'TR-2026-022' AND estatus_efectivo = 'Faltante'""")
    return [
        ("¿Qué registros sanitarios hay que renovar con urgencia?", [urg[0]["producto"].split()[0]] if urg else []),
        ("¿Cuántas observaciones de COFEPRIS hay en el historial?", [str(int(total))]),
        ("¿Qué norma genera más observaciones de COFEPRIS?", [top[0]["norma"]] if top else []),
        ("¿Cuántos días hábiles le quedan a la prevención del losartán?", [str(int(los[0]["n"]))] if los else []),
        ("¿Qué documento le falta al expediente del losartán (TR-2026-022)?",
         [falt[0]["nombre_requisito"].split()[0]] if falt else []),
        ("¿Qué dice la NOM-073 sobre los estudios de estabilidad acelerada?", ["NOM-073", "acelerada"]),
        ("¿Qué leyenda de farmacovigilancia debe llevar la etiqueta según la NOM-072?", ["NOM-072", "6.1.6"]),
        ("¿Cuál es el precio de venta al público de la metformina?", ["NO_INVENTA"]),
    ]


def calificar(texto, esperado):
    t = _norm(texto)
    if esperado == ["NO_INVENTA"]:
        return any(x in t for x in ["no tengo", "no cuento", "no esta disponible", "no se encuentra", "no dispongo",
                                    "no hay informacion", "no contiene", "no incluye", "no aparece", "no puedo"])
    return all(_norm(e) in t for e in esperado)


def examen_asistente(d, plataforma):
    filas = []
    for pregunta, esperado in _esperados(d):
        t = time.time()
        try:
            r = d.preguntar(pregunta, [])
            error = None
        except Exception as e:
            r, error = respuesta_vacia(), str(e)[:300]
        r["segundos"] = r.get("segundos") or round(time.time() - t, 1)
        ok = calificar(r["texto"], esperado) if not error else False
        filas.append({"pregunta": pregunta, "esperado": esperado, "correcta": ok, "segundos": r["segundos"],
                      "pasos": r["pasos"], "fuentes": [f["etiqueta"] for f in r["fuentes"]], "sql": r["sql"],
                      "tokens": r.get("tokens"), "respuesta": r["texto"], "error": error})
        print(f"  {'✓' if ok else '✗'} [{r['segundos']} s] {pregunta} → {r['texto'][:110]!r}")
    return guardar_examen(filas, plataforma)


def guardar_examen(filas, plataforma):
    print(f"  Correctas: {sum(f['correcta'] for f in filas)}/{len(filas)} · mediana "
          f"{sorted(f['segundos'] for f in filas)[len(filas) // 2]} s")
    destino = Path(__file__).resolve().parents[1] / "docs" / "resultados" / "fase7" / f"asistente_{plataforma}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(filas, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    return filas


def recalificar(plataforma):
    """Vuelve a calificar las respuestas guardadas (sin consultar de nuevo a la IA)."""
    destino = Path(__file__).resolve().parents[1] / "docs" / "resultados" / "fase7" / f"asistente_{plataforma}.json"
    filas = json.loads(destino.read_text(encoding="utf-8"))
    for f in filas:
        f["correcta"] = calificar(f["respuesta"], f["esperado"]) if not f["error"] else False
    return guardar_examen(filas, plataforma)
