"""Genera los PDF ficticios de los trámites activos, los oficios de prevención y la hoja de respuestas
(defectos_sembrados.csv)."""
import csv
from datetime import date
from types import SimpleNamespace

import catalogos as C
import plantillas as PL
from config import SALIDA, SALIDA_PDF
from pdf_base import escanear
from perfiles import perfil

REQ = {r["requisito_id"]: r for r in C.REQUISITOS}
PROD = {p["producto_id"]: p for p in C.PRODUCTOS}


def carpeta(tramite):
    nombre = tramite["producto"].split(" ")[0].lower().translate(str.maketrans("áéíóúñ", "aeioun"))
    return SALIDA_PDF / f"{tramite['tramite_id']}_{nombre}"


def contexto(tramite_fila, tramite, usuarios, semilla, **kw):
    por_rol = lambda rol: next(u for u in usuarios if u["rol"] == rol)
    p = PROD[tramite_fila["producto_id"]]
    ns = SimpleNamespace(tramite=tramite_fila, tramite_tipo=tramite["tipo"], producto=p, perfil=perfil(p["producto_id"]),
                         fabricante=C.FABRICANTES_FARMACO[p["producto_id"]], semilla=semilla,
                         rs=por_rol("Responsable Sanitario"), rl=por_rol("Representante Legal"), usuarios_rol=por_rol,
                         extra={}, req=None, prevencion=None, observaciones=None)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def generar(tablas, tramites, usuarios):
    filas_t = {t["tramite_id"]: t for t in tablas["tramites"]}
    docs_por_tramite = {}
    for d in tablas["documentos"]:
        docs_por_tramite.setdefault(d["tramite_id"], {})[d["requisito_id"]] = d
    prev_por_tramite = {p["tramite_id"]: p for p in tablas["prevenciones"]}
    obs_por_prev = {}
    for o in tablas["observaciones"]:
        obs_por_prev.setdefault(o["prevencion_id"], []).append(o)
    usuarios_id = {u["usuario_id"]: u for u in usuarios}
    gerente = {"Asuntos Regulatorios": "Gerente de Asuntos Regulatorios", "Calidad": "Gerente de Aseguramiento de Calidad",
               "CMC": "Gerente de Aseguramiento de Calidad", "Clínico": "Gerente Médico",
               "Farmacovigilancia": "Responsable de Farmacovigilancia"}

    indice, defectos = [], []
    semilla = 100
    for t in tramites:
        activo = t.get("activo")
        if not activo:
            continue
        fila = filas_t[t["tramite_id"]]
        prev = prev_por_tramite.get(t["tramite_id"])
        observadas = set()
        if prev:
            observadas = {(o["requisito_id"], o["clausula"]) for o in obs_por_prev.get(prev["prevencion_id"], [])}
        for spec in activo["documentos"]:
            semilla += 1
            req = REQ[spec["requisito_id"]]
            d = docs_por_tramite[t["tramite_id"]][spec["requisito_id"]]
            ruta = None
            if spec["plantilla"]:
                ruta = carpeta(fila) / d["nombre_archivo"]
                autor = usuarios_id.get(d["cargado_por"]) or usuarios[0]
                x = contexto(fila, t, usuarios, semilla, req=req, extra=spec["extra"], ruta=ruta,
                             fecha=date.fromisoformat(d["fecha_carga"]), autor=autor,
                             revisor=next(u for u in usuarios if u["rol"] == gerente[req["area_responsable"]]))
                PL.PLANTILLAS[spec["plantilla"]](x)
                if spec["escaneado"]:
                    escanear(ruta, semilla=semilla, ilegible=spec["extra"].get("ilegible", False))
                indice.append(dict(archivo=str(ruta.relative_to(SALIDA)).replace("\\", "/"), tramite_id=t["tramite_id"],
                                   producto=fila["producto"], documento_id=d["documento_id"], requisito_id=req["requisito_id"],
                                   seccion_ctd=req["seccion_ctd"], tipo_documento=req["nombre"], escaneado=spec["escaneado"],
                                   defectos_sembrados=len(spec["defectos"]), origen="Expediente de la empresa"))
            for df in spec["defectos"]:
                clave = (spec["requisito_id"], df["clausula"] or "")
                origen = (f"Observado por COFEPRIS en oficio {prev['numero_oficio']}" if prev and clave in observadas
                          else "Sembrado para pre-auditoría (aún no observado)")
                defectos.append(dict(tramite_id=t["tramite_id"], producto=fila["producto"], documento_id=d["documento_id"],
                                     requisito_id=req["requisito_id"], seccion_ctd=req["seccion_ctd"],
                                     archivo=str(ruta.relative_to(SALIDA)).replace("\\", "/") if ruta else "(documento faltante)",
                                     tipo_defecto=df["tipo"], descripcion=df["descripcion"], norma=df["norma"] or "",
                                     clausula=df["clausula"] or "", fundamento=df["fundamento"] or "",
                                     como_detectarlo=df["como_detectar"], origen=origen))
        # oficio de prevención y, si ya se respondió, el escrito de respuesta
        if prev:
            semilla += 1
            obs = obs_por_prev[prev["prevencion_id"]]
            ruta = carpeta(fila) / "oficios" / f"Oficio_{prev['numero_oficio'].replace('/', '-')}_prevencion.pdf"
            x = contexto(fila, t, usuarios, semilla, ruta=ruta, prevencion=prev, observaciones=obs)
            PL.oficio_prevencion(x)
            indice.append(dict(archivo=str(ruta.relative_to(SALIDA)).replace("\\", "/"), tramite_id=t["tramite_id"],
                               producto=fila["producto"], documento_id="", requisito_id="", seccion_ctd="",
                               tipo_documento=f"Oficio de prevención ({prev['estatus']})", escaneado=False,
                               defectos_sembrados=0, origen="Autoridad (simulado)"))
            if prev["fecha_respuesta"]:
                ruta = carpeta(fila) / "oficios" / f"Respuesta_{prev['numero_oficio'].replace('/', '-')}.pdf"
                x = contexto(fila, t, usuarios, semilla + 1, ruta=ruta, prevencion=prev, observaciones=obs)
                PL.escrito_respuesta(x)
                indice.append(dict(archivo=str(ruta.relative_to(SALIDA)).replace("\\", "/"), tramite_id=t["tramite_id"],
                                   producto=fila["producto"], documento_id="", requisito_id="", seccion_ctd="",
                                   tipo_documento="Escrito de respuesta a prevención", escaneado=False,
                                   defectos_sembrados=0, origen="Expediente de la empresa"))
    for i, df in enumerate(defectos, 1):
        df["defecto_id"] = f"DEF-{i:02d}"
    _escribir(SALIDA / "defectos_sembrados.csv", [{"defecto_id": d.pop("defecto_id"), **d} for d in defectos])
    _escribir(SALIDA_PDF / "INDICE.csv", indice)
    return indice, defectos


def _escribir(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)
