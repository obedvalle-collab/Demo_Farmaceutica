"""Evalúa la bandeja de carga contra la hoja de respuestas (datos/salida/defectos_sembrados.csv).

Mide: clasificación correcta del tipo de documento, defectos detectados (recall) y falsas alarmas.
"""
import csv
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "datos" / "salida"


def _rel(ruta):
    return ruta.replace("\\", "/").removeprefix("pdf/")


def esperados_tipo():
    out = {}
    for r in csv.DictReader(open(SALIDA / "pdf" / "INDICE.csv", encoding="utf-8")):
        tipo = r["tipo_documento"]
        if tipo.startswith("Oficio de prevención"):
            tipo = "Oficio de prevención"
        out[_rel(r["archivo"])] = tipo
    return out


def defectos():
    return list(csv.DictReader(open(SALIDA / "defectos_sembrados.csv", encoding="utf-8")))


def _coincide(h, d):
    if h["tramite_id"] != d["tramite_id"] or h["seccion_ctd"] != d["seccion_ctd"]:
        return False
    if h["regla"] == "CTD-FALTANTE":
        return d["archivo"] == "(documento faltante)"
    return not d["clausula"] or h["clausula"] == d["clausula"]


def evaluar(extraidos, hallazgos):
    """extraidos: [{archivo, tipo_documento}], hallazgos: [{tramite_id, seccion_ctd, regla, clausula, ...}]"""
    esp = esperados_tipo()
    clasif = [dict(archivo=e["archivo"], esperado=esp.get(_rel(e["archivo"]), "?"), obtenido=e["tipo_documento"],
                   correcto=esp.get(_rel(e["archivo"])) == e["tipo_documento"]) for e in extraidos]
    defs = defectos()
    detalle_def = []
    usados = set()
    for d in defs:
        match = [i for i, h in enumerate(hallazgos) if _coincide(h, d)]
        usados.update(match)
        detalle_def.append(dict(defecto_id=d["defecto_id"], tramite_id=d["tramite_id"], seccion_ctd=d["seccion_ctd"],
                                descripcion=d["descripcion"], norma=d["norma"] or d["fundamento"], clausula=d["clausula"],
                                detectado=bool(match),
                                hallazgo=hallazgos[match[0]]["hallazgo"] if match else ""))
    falsas = [h for i, h in enumerate(hallazgos) if i not in usados]
    return dict(
        documentos=len(clasif),
        clasificacion_correcta=f"{sum(c['correcto'] for c in clasif)}/{len(clasif)}",
        defectos_detectados=f"{sum(d['detectado'] for d in detalle_def)}/{len(defs)}",
        falsas_alarmas=len(falsas),
        errores_clasificacion=[c for c in clasif if not c["correcto"]],
        defectos=detalle_def,
        detalle_falsas_alarmas=[{k: h[k] for k in ("tramite_id", "archivo", "regla", "hallazgo")} for h in falsas],
    )
