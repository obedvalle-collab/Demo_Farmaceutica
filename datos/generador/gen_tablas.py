"""Genera las tablas (CSV) de Laboratorios Altamira: productos, trámites, requisitos, documentos,
versiones, prevenciones, observaciones, tareas, respuestas, usuarios, calendario y bitácora."""
import csv
import hashlib
import random
from datetime import date, timedelta, datetime

from faker import Faker

import catalogos as C
from activos import ACTIVOS
from calendario import Calendario
from config import SEMILLA, HOY, EMPRESA, SALIDA_TABLAS, INICIO_HISTORIA

rnd = random.Random(SEMILLA)
fake = Faker("es_MX")
Faker.seed(SEMILLA)
cal = Calendario(2023, 2027)
REQ = {r["requisito_id"]: r for r in C.REQUISITOS}
PROD = {p["producto_id"]: p for p in C.PRODUCTOS}


def iso(d):
    return d.isoformat() if d else ""


def habil_desde(d):
    return d if cal.es_habil(d) else cal.siguiente_habil(d)


def dias_naturales(d, n):
    return d + timedelta(days=n)


# ----------------------------------------------------------------------------- usuarios
def gen_usuarios():
    usuarios = []
    n = 1
    for rol, area, cantidad in C.ROLES:
        for _ in range(cantidad):
            nombre, apellido1, apellido2 = fake.first_name(), fake.last_name(), fake.last_name()
            usuario = f"{nombre.split()[0]}.{apellido1}".lower()
            usuario = usuario.translate(str.maketrans("áéíóúñü ", "aeiounu_"))
            titulo = "Q.F.B." if area in ("Calidad", "CMC", "Asuntos Regulatorios") else (
                "Dr(a)." if area == "Clínico" else "Lic.")
            usuarios.append(dict(usuario_id=f"U{n:02d}", nombre=f"{nombre} {apellido1} {apellido2}",
                                 titulo=titulo, rol=rol, area=area,
                                 correo=f"{usuario}@{EMPRESA['dominio_correo']}",
                                 cedula_profesional=str(rnd.randint(10_000_000, 13_999_999)) if titulo != "Lic." else "",
                                 activo=True))
            n += 1
    return usuarios


def por_area(usuarios, area):
    return [u for u in usuarios if u["area"] == area] or usuarios


def por_rol(usuarios, rol):
    return next(u for u in usuarios if u["rol"] == rol)


# ----------------------------------------------------------------------------- requisitos
def gen_requisitos():
    filas = []
    for tipo, letra in C.APLICA_POR_TRAMITE.items():
        if tipo in ("MOD_CON", "MOD_SITIO"):
            continue   # comparten plantilla con MOD_SIN
        familia = C.TIPOS_TRAMITE[tipo]["familia"]
        etiqueta = {"REG_GEN": "Registro genérico", "REG_BIO": "Registro biocomparable",
                    "REG_NUEVA": "Registro molécula nueva", "PRORROGA": "Prórroga",
                    "MOD_SIN": "Modificación"}[tipo]
        for r in C.REQUISITOS:
            if letra in r["aplica"]:
                filas.append(dict(plantilla_id=f"{tipo}-{r['requisito_id']}", tipo_tramite=etiqueta,
                                  familia=familia, **{k: v for k, v in r.items() if k != "aplica"},
                                  obligatorio=r["requisito_id"] not in ("R014",) or tipo == "PRORROGA"))
    return filas


def requisitos_de(tipo, rnd_local):
    letra = C.APLICA_POR_TRAMITE[tipo]
    reqs = [r["requisito_id"] for r in C.REQUISITOS if letra in r["aplica"]]
    if letra == "M":   # una modificación solo trae lo administrativo y lo técnico del cambio
        base = ["R001", "R002", "R015"]
        resto = [r for r in reqs if r not in base]
        reqs = base + rnd_local.sample(resto, rnd_local.randint(2, 6))
    return reqs


# ----------------------------------------------------------------------------- trámites
def simular_historico(tipo, producto_id, ingreso, descripcion):
    """Simula la vida completa de un trámite ya concluido."""
    t = C.TIPOS_TRAMITE[tipo]
    familia = t["familia"]
    if t["tipo_plazo"] == "naturales":
        fin_plazo = dias_naturales(ingreso, t["plazo_resolucion_dias"])
    else:
        fin_plazo = cal.sumar_habiles(ingreso, t["plazo_resolucion_dias"])
    prob_prev = {"Registro nuevo": 0.80, "Prórroga": 0.55, "Modificación": 0.55}[familia]
    tr = dict(tipo=tipo, producto_id=producto_id, fecha_ingreso=ingreso, descripcion=descripcion,
              prevencion=None)
    if rnd.random() < prob_prev:
        tercio = max(5, (fin_plazo - ingreso).days // 3)
        emision = habil_desde(ingreso + timedelta(days=rnd.randint(int(tercio * 0.4), tercio)))
        dias_abrir = rnd.choices([0, 1, 2, 3, 4, 5, 6], weights=[30, 30, 15, 10, 6, 5, 4])[0]
        estrados = dias_abrir > 5
        apertura = cal.sumar_habiles(emision, min(dias_abrir, 5)) if dias_abrir else emision
        if estrados:
            apertura = None
        notificada = cal.sumar_habiles(emision, 6) if estrados else apertura
        surte = cal.siguiente_habil(notificada)
        plazo = rnd.choices([5, 10, 15, 20], weights=[1, 5, 3, 2])[0]
        limite = cal.sumar_habiles(surte, plazo - 1)
        responde = rnd.random() < 0.94
        respuesta = None
        if responde:
            respuesta = limite
            for _ in range(rnd.randint(0, min(6, plazo - 1))):
                respuesta = respuesta - timedelta(days=1)
                while not cal.es_habil(respuesta):
                    respuesta -= timedelta(days=1)
        tr["prevencion"] = dict(fecha_emision=emision, fecha_apertura=apertura, por_estrados=estrados,
                                fecha_surte_efectos=surte, plazo_dias_habiles=plazo, fecha_limite=limite,
                                fecha_respuesta=respuesta,
                                tipo=rnd.choices(["Técnica", "Administrativa"], weights=[3, 1])[0],
                                estatus="Atendida" if responde else "Vencida")
        if not responde:
            tr.update(resultado="Desechado", fecha_resolucion=cal.sumar_habiles(limite, rnd.randint(5, 20)))
        else:
            resto = max(10, (fin_plazo - emision).days)
            tr["fecha_resolucion"] = habil_desde(respuesta + timedelta(days=rnd.randint(resto // 3, resto)))
            tr["resultado"] = rnd.choices(["Aprobado", "Negado"], weights=[88, 12])[0]
    else:
        tr["fecha_resolucion"] = habil_desde(ingreso + timedelta(days=rnd.randint(
            int((fin_plazo - ingreso).days * 0.5), (fin_plazo - ingreso).days)))
        tr["resultado"] = rnd.choices(["Aprobado", "Negado", "Desistido"], weights=[95, 3, 2])[0]
    if tr["fecha_resolucion"] >= HOY:   # nada histórico puede resolverse en el futuro
        tr["fecha_resolucion"] = cal.sumar_habiles(HOY - timedelta(days=rnd.randint(8, 40)), 0)
    return tr


def gen_tramites_historicos():
    lista = []
    # Registros nuevos (incluye otras concentraciones del portafolio)
    registros = [
        ("P07", "REG_GEN", date(2023, 6, 12), "Registro Sertralina 50 mg", "Aprobado", date(2023, 12, 5)),
        ("P11", "REG_BIO", date(2023, 11, 21), "Registro Trastuzumab 440 mg", "Aprobado", date(2024, 8, 13)),
        ("P01", "REG_GEN", date(2023, 10, 16), "Registro Metformina 500 mg", None, None),
        ("P02", "REG_GEN", date(2023, 11, 27), "Registro Atorvastatina 40 mg", None, None),
        ("P03", "REG_GEN", date(2024, 1, 22), "Registro Losartán potásico 100 mg", "Desechado", None),
        ("P05", "REG_GEN", date(2024, 3, 4), "Registro Amlodipino 10 mg", None, None),
        ("P07", "REG_GEN", date(2024, 4, 15), "Registro Sertralina 100 mg", "Negado", None),
        ("P04", "REG_GEN", date(2024, 6, 3), "Registro Omeprazol 40 mg", None, None),
        ("P06", "REG_GEN", date(2024, 9, 9), "Registro Clopidogrel 300 mg", None, None),
        ("P01", "REG_GEN", date(2024, 11, 11), "Registro Metformina 1000 mg", None, None),
        ("P08", "REG_GEN", date(2025, 1, 20), "Registro Rosuvastatina 20 mg", "Desechado", None),
        ("P02", "REG_GEN", date(2025, 3, 10), "Registro Atorvastatina 80 mg", None, None),
        ("P05", "REG_GEN", date(2025, 6, 16), "Registro Amlodipino 2.5 mg", None, None),
        ("P04", "REG_GEN", date(2025, 9, 1), "Registro Omeprazol 10 mg", None, None),
    ]
    for pid, tipo, ingreso, desc, forzar, fecha_res in registros:
        tr = simular_historico(tipo, pid, ingreso, desc)
        if forzar == "Desechado":
            while not (tr["prevencion"] and tr["prevencion"]["estatus"] == "Vencida"):
                tr = simular_historico(tipo, pid, ingreso, desc)
        elif forzar:
            while not tr["prevencion"] or tr["prevencion"]["estatus"] != "Atendida":
                tr = simular_historico(tipo, pid, ingreso, desc)
            tr["resultado"] = forzar
            if fecha_res:
                tr["fecha_resolucion"] = fecha_res
        else:
            while tr["resultado"] != "Aprobado":
                tr = simular_historico(tipo, pid, ingreso, desc)
        lista.append(tr)
    # Prórrogas
    for pid, ingreso in [("P02", date(2023, 12, 18)), ("P05", date(2025, 3, 24))]:
        tr = simular_historico("PRORROGA", pid, ingreso, "Prórroga del registro sanitario")
        while tr["resultado"] != "Aprobado":
            tr = simular_historico("PRORROGA", pid, ingreso, "Prórroga del registro sanitario")
        lista.append(tr)
    # Modificaciones: completar ~150 históricos
    con_registro = [p["producto_id"] for p in C.PRODUCTOS if p["registro_sanitario"]]
    while len(lista) < 150:
        tipo = rnd.choices(["MOD_SIN", "MOD_CON", "MOD_SITIO"], weights=[78, 14, 8])[0]
        pid = rnd.choice(con_registro)
        fecha_min = max(date(2023, 10, 2), date.fromisoformat(PROD[pid]["fecha_registro"]))
        dias = (date(2026, 7, 31) - fecha_min).days
        ingreso = habil_desde(fecha_min + timedelta(days=rnd.randint(0, dias)))
        lista.append(simular_historico(tipo, pid, ingreso, rnd.choice(C.DESCRIPCIONES_MODIFICACION[tipo])))
    return lista


def gen_activos():
    lista = []
    for a in ACTIVOS:
        tr = dict(tipo=a["tipo"], producto_id=a["producto_id"], fecha_ingreso=a.get("fecha_ingreso"),
                  descripcion=a.get("descripcion") or C.TIPOS_TRAMITE[a["tipo"]]["nombre"],
                  etapa=a["etapa"], estatus=a["estatus"], activo=a, prevencion=None,
                  fecha_inicio=a.get("fecha_inicio"), fecha_objetivo_envio=a.get("fecha_objetivo_envio"))
        p = a.get("prevencion")
        if p:
            emision, apertura = p["fecha_emision"], p["fecha_apertura"]
            surte = cal.siguiente_habil(apertura) if apertura else None
            limite = cal.sumar_habiles(surte, p["plazo_dias_habiles"] - 1) if surte else None
            limite_apertura = cal.sumar_habiles(emision, 5)
            if p.get("fecha_respuesta"):
                estatus = "Atendida"
            elif apertura:
                estatus = "Abierta"
            else:
                estatus = "Sin abrir"
            tr["prevencion"] = dict(fecha_emision=emision, fecha_apertura=apertura, por_estrados=False,
                                    fecha_surte_efectos=surte, plazo_dias_habiles=p["plazo_dias_habiles"],
                                    fecha_limite=limite, fecha_limite_apertura=limite_apertura,
                                    fecha_respuesta=p.get("fecha_respuesta"), tipo=p["tipo"],
                                    estatus=estatus, observaciones_fijas=p["observaciones"])
        lista.append(tr)
    return lista


def armar_tramites(historicos, activos, usuarios):
    todos = sorted(historicos + activos,
                   key=lambda t: t.get("fecha_ingreso") or t.get("fecha_inicio") or HOY)
    regulatorios = por_area(usuarios, "Asuntos Regulatorios")
    contador_anio = {}
    for i, t in enumerate(todos, 1):
        base = t.get("fecha_ingreso") or t.get("fecha_inicio")
        contador_anio[base.year] = contador_anio.get(base.year, 0) + 1
        t["tramite_id"] = f"TR-{base.year}-{contador_anio[base.year]:03d}"
        t["responsable_id"] = rnd.choice(regulatorios)["usuario_id"]
        t["folio_digipris"] = (f"DGP-{t['fecha_ingreso'].year}-{rnd.randint(10000, 99999)}"
                               if t.get("fecha_ingreso") else "")
    return todos


def fila_tramite(t):
    tt = C.TIPOS_TRAMITE[t["tipo"]]
    p = PROD[t["producto_id"]]
    activo = "activo" in t
    if activo:
        estatus, etapa, resultado = t["estatus"], t["etapa"], ""
    else:
        resultado = t["resultado"]
        estatus, etapa = "Concluido", "Resuelto"
    fin = t.get("fecha_resolucion") if not activo else None
    ingreso = t.get("fecha_ingreso")
    dias = ((fin or HOY) - ingreso).days if ingreso else ""
    return dict(tramite_id=t["tramite_id"], producto_id=t["producto_id"],
                producto=f"{p['denominacion_generica']} {p['concentracion']}",
                homoclave=tt["homoclave"], tipo_tramite=tt["nombre"], familia=tt["familia"],
                descripcion=t["descripcion"], folio_digipris=t["folio_digipris"],
                fecha_inicio_integracion=iso(t.get("fecha_inicio") or (ingreso - timedelta(days=rnd.randint(30, 90)) if ingreso else None)),
                fecha_ingreso=iso(ingreso), fecha_objetivo_envio=iso(t.get("fecha_objetivo_envio")),
                fecha_resolucion=iso(fin), etapa=etapa, estatus=estatus, resultado=resultado,
                dias_en_cofepris=dias, tuvo_prevencion=bool(t["prevencion"]),
                plazo_resolucion=f"{tt['plazo_resolucion_dias']} días {tt['tipo_plazo']}",
                fundamento_plazo=tt["fundamento"], responsable_id=t["responsable_id"], es_activo=activo)


# ----------------------------------------------------------------------------- documentos
def nombre_archivo(tramite_id, req, version):
    r = REQ[req]
    base = r["nombre"].lower()
    base = base.translate(str.maketrans("áéíóúñü", "aeiounu"))
    base = "".join(ch if ch.isalnum() else "_" for ch in base).strip("_")
    while "__" in base:
        base = base.replace("__", "_")
    return f"{tramite_id}_{r['seccion_ctd']}_{base[:48]}_v{version}.pdf"


def gen_documentos(tramites, usuarios):
    documentos, versiones = [], []
    nd = nv = 0
    for t in tramites:
        activo = t.get("activo")
        if activo and activo["documentos"]:
            reqs = [d["requisito_id"] for d in activo["documentos"]]
            specs = {d["requisito_id"]: d for d in activo["documentos"]}
        elif activo and activo["tipo"] in ("REG_NUEVA",):
            reqs, specs = requisitos_de(t["tipo"], rnd), {}
        else:
            reqs, specs = requisitos_de(t["tipo"], rnd), {}
        t["documentos"] = {}
        ingreso = t.get("fecha_ingreso")
        inicio = t.get("fecha_inicio") or (ingreso - timedelta(days=rnd.randint(40, 120)))
        for req in reqs:
            nd += 1
            r = REQ[req]
            spec = specs.get(req)
            autor = rnd.choice(por_area(usuarios, r["area_responsable"]))
            aprobador = rnd.choice(por_area(usuarios, "Calidad") if r["area_responsable"] != "Asuntos Regulatorios"
                                   else por_area(usuarios, "Asuntos Regulatorios"))
            limite_carga = ingreso or HOY
            carga = inicio + timedelta(days=rnd.randint(0, max(1, (limite_carga - inicio).days - 3)))
            if activo and not ingreso:          # en integración
                faltante = spec and spec["estatus"] == "Faltante" or (not spec and rnd.random() < 0.25)
                estatus = "Faltante" if faltante else rnd.choices(
                    ["Aprobado", "En revisión", "Borrador"], weights=[6, 3, 1])[0]
                if spec and not faltante:
                    estatus = "En revisión" if spec["defectos"] else "Aprobado"
            elif activo:
                estatus = "Enviado"
                if spec and spec["estatus"] == "Faltante":
                    estatus = "Faltante"
            else:
                estatus = "Enviado" if t.get("resultado") != "Aprobado" else "Aprobado"
            doc_id = f"D{nd:05d}"
            documentos.append(dict(
                documento_id=doc_id, tramite_id=t["tramite_id"], requisito_id=req, modulo=r["modulo"],
                seccion_ctd=r["seccion_ctd"], nombre_requisito=r["nombre"],
                nombre_archivo="" if estatus == "Faltante" else nombre_archivo(t["tramite_id"], req, 1),
                version_actual=0 if estatus == "Faltante" else 1, estatus=estatus,
                area_responsable=r["area_responsable"], cargado_por="" if estatus == "Faltante" else autor["usuario_id"],
                fecha_carga="" if estatus == "Faltante" else iso(carga),
                aprobado_por=aprobador["usuario_id"] if estatus in ("Aprobado", "Enviado") else "",
                paginas=0 if estatus == "Faltante" else rnd.randint(2, 60),
                tamano_kb=0 if estatus == "Faltante" else rnd.randint(120, 9800),
                tiene_pdf_demo=bool(spec and spec["plantilla"]),
                escaneado=bool(spec and spec["escaneado"])))
            t["documentos"][req] = documentos[-1]
            if estatus != "Faltante":
                nv += 1
                versiones.append(dict(version_id=f"V{nv:06d}", documento_id=doc_id, version=1,
                                      fecha=iso(carga), autor_id=autor["usuario_id"],
                                      estado="Enviado" if ingreso else estatus,
                                      comentario="Versión inicial",
                                      sha256=hashlib.sha256(f"{doc_id}-1".encode()).hexdigest()))
    return documentos, versiones, nd, nv


# ----------------------------------------------------------------------------- prevenciones
def elegir_observaciones(t, n):
    letra = C.APLICA_POR_TRAMITE[t["tipo"]]
    candidatas = [o for o in C.OBSERVACIONES if letra in o[6] and o[0] in t["documentos"]]
    if len(candidatas) < n:   # observaciones sobre requisitos que no se presentaron (faltantes)
        candidatas += [o for o in C.OBSERVACIONES if letra in o[6] and o not in candidatas][: n - len(candidatas)]
    elegidas = []
    pool = list(candidatas)
    while pool and len(elegidas) < n:
        o = rnd.choices(pool, weights=[x[5] for x in pool])[0]
        pool.remove(o)
        elegidas.append(o)
    return elegidas


def buscar_obs(clave):
    req, clausula = clave.split(":")
    for o in C.OBSERVACIONES:
        if o[0] == req and (o[2] or "") == clausula:
            return o
    raise KeyError(clave)


def gen_prevenciones(tramites, usuarios, versiones, nv):
    prevenciones, observaciones, tareas, respuestas = [], [], [], []
    npv = nob = nta = nre = 0
    dictaminadores = [f"{fake.first_name()} {fake.last_name()} {fake.last_name()}" for _ in range(6)]
    for t in tramites:
        p = t["prevencion"]
        if not p:
            continue
        npv += 1
        prev_id = f"PV{npv:04d}"
        numero_oficio = f"CAS/{rnd.choice(['DERS', 'DEAPE'])}/{rnd.randint(1000, 9999)}/{p['fecha_emision'].year}"
        t["numero_oficio"] = numero_oficio
        t["prevencion_id"] = prev_id
        fijas = p.get("observaciones_fijas")
        obs_lista = [buscar_obs(c) for c in fijas] if fijas else elegir_observaciones(
            t, rnd.choices([1, 2, 3, 4, 5, 6, 7], weights=[5, 12, 20, 24, 18, 12, 9])[0])
        dictaminador = rnd.choice(dictaminadores)
        prevenciones.append(dict(
            prevencion_id=prev_id, tramite_id=t["tramite_id"], numero_oficio=numero_oficio,
            tipo=p["tipo"], fecha_emision=iso(p["fecha_emision"]), fecha_aviso_correo=iso(p["fecha_emision"]),
            fecha_limite_apertura=iso(p.get("fecha_limite_apertura") or cal.sumar_habiles(p["fecha_emision"], 5)),
            fecha_apertura=iso(p["fecha_apertura"]), notificada_por_estrados=p["por_estrados"],
            fecha_surte_efectos=iso(p["fecha_surte_efectos"]), plazo_dias_habiles=p["plazo_dias_habiles"],
            fecha_limite_respuesta=iso(p["fecha_limite"]), fecha_respuesta=iso(p["fecha_respuesta"]),
            num_observaciones=len(obs_lista), estatus=p["estatus"], dictaminador_simulado=dictaminador))
        for k, o in enumerate(obs_lista, 1):
            nob += 1
            req, norma, clausula, texto, severidad, _, _ = o
            area = REQ[req]["area_responsable"]
            documento = t["documentos"].get(req)
            if p["estatus"] == "Atendida":
                est = "Atendida"
            elif p["estatus"] == "Vencida":
                est = "No atendida"
            elif p["estatus"] == "Sin abrir":
                est = "Sin conocer"
            else:
                est = rnd.choice(["Pendiente", "En atención"])
            obs_id = f"OB{nob:05d}"
            observaciones.append(dict(
                observacion_id=obs_id, prevencion_id=prev_id, tramite_id=t["tramite_id"], numero=k,
                requisito_id=req, seccion_ctd=REQ[req]["seccion_ctd"], norma=norma or "", clausula=clausula or "",
                fundamento=REQ[req]["fundamento"], texto=texto, severidad=severidad, area_responsable=area,
                documento_id=documento["documento_id"] if documento else "", estatus=est))
            if p["estatus"] == "Sin abrir":
                continue
            # tareas
            responsable = rnd.choice(por_area(usuarios, area))
            asignacion = p["fecha_surte_efectos"] or p["fecha_emision"]
            compromiso = cal.sumar_habiles(asignacion, max(1, p["plazo_dias_habiles"] - rnd.randint(2, 4)))
            if est == "Atendida":
                cierre = min(p["fecha_respuesta"], cal.sumar_habiles(asignacion, rnd.randint(1, p["plazo_dias_habiles"])))
                estatus_t = "Cerrada"
            elif est == "No atendida":
                cierre, estatus_t = None, "Vencida"
            else:
                cierre, estatus_t = None, rnd.choice(["En curso", "Pendiente"])
            nta += 1
            tareas.append(dict(tarea_id=f"TA{nta:05d}", observacion_id=obs_id, tramite_id=t["tramite_id"],
                               descripcion=f"Atender observación {k}: corregir {REQ[req]['nombre'].lower()}",
                               responsable_id=responsable["usuario_id"], area=area,
                               fecha_asignacion=iso(asignacion), fecha_compromiso=iso(compromiso),
                               fecha_cierre=iso(cierre), estatus=estatus_t))
            # nueva versión del documento corregido
            if documento and est == "Atendida":
                documento["version_actual"] += 1
                v = documento["version_actual"]
                documento["nombre_archivo"] = nombre_archivo(t["tramite_id"], req, v)
                nv += 1
                versiones.append(dict(version_id=f"V{nv:06d}", documento_id=documento["documento_id"], version=v,
                                      fecha=iso(cierre), autor_id=responsable["usuario_id"], estado="Enviado",
                                      comentario=f"Corrección que atiende la observación {obs_id} ({norma or 'administrativa'} {clausula or ''})".strip(),
                                      sha256=hashlib.sha256(f"{documento['documento_id']}-{v}".encode()).hexdigest()))
            elif documento and est == "En atención":
                documento["estatus"] = "Observado"
        if p["fecha_respuesta"]:
            nre += 1
            respuestas.append(dict(
                respuesta_id=f"RE{nre:04d}", prevencion_id=prev_id, tramite_id=t["tramite_id"],
                fecha_envio=iso(p["fecha_respuesta"]), folio_acuse=f"ACU-{p['fecha_respuesta'].year}-{rnd.randint(100000, 999999)}",
                num_documentos_adjuntos=len(obs_lista) + rnd.randint(0, 2),
                elaborada_por=t["responsable_id"], aprobada_por=por_rol(usuarios, "Director(a) de Asuntos Regulatorios")["usuario_id"],
                dias_habiles_usados=cal.habiles_entre(p["fecha_surte_efectos"], p["fecha_respuesta"]) + 1,
                resultado_final=t.get("resultado", "En evaluación")))
    return prevenciones, observaciones, tareas, respuestas


# ----------------------------------------------------------------------------- productos
def fila_producto(p, tramites):
    fila = dict(p)
    fab, pais = C.FABRICANTES_FARMACO[p["producto_id"]]
    fila.update(fabricante_farmaco=fab, pais_fabricante_farmaco=pais, fraccion_lgs_226="IV",
                titular_registro=EMPRESA["razon_social"])
    if p["fecha_registro"]:
        reg = date.fromisoformat(p["fecha_registro"])
        venc = date(reg.year + 5, reg.month, reg.day)
        prorrogas_previas = 0
        while venc < INICIO_HISTORIA:   # prórrogas anteriores a la historia generada (aprobadas, 5 años c/u)
            venc = date(venc.year + 5, venc.month, venc.day)
            prorrogas_previas += 1
        fila["prorrogas_previas_a_2023"] = prorrogas_previas
        for t in tramites:   # prórrogas aprobadas extienden la vigencia
            if t["producto_id"] == p["producto_id"] and t["tipo"] == "PRORROGA" and t.get("resultado") == "Aprobado":
                anios = 10 if t["fecha_resolucion"] >= date(2026, 1, 15) else 5
                venc = date(venc.year + anios, venc.month, venc.day)
        fila["fecha_vencimiento_registro"] = venc.isoformat()
        fila["fecha_limite_solicitar_prorroga"] = (venc - timedelta(days=150)).isoformat()
        fila["dias_para_vencimiento"] = (venc - HOY).days
        fila["estatus_registro"] = "Vigente"
    else:
        fila.update(fecha_vencimiento_registro="", fecha_limite_solicitar_prorroga="", prorrogas_previas_a_2023="",
                    dias_para_vencimiento="", estatus_registro="En trámite" if p["producto_id"] in ("P08", "P10") else "En desarrollo")
    return fila


# ----------------------------------------------------------------------------- bitácora
def gen_bitacora(tramites, documentos, versiones, prevenciones, respuestas, usuarios):
    eventos = []
    ip = lambda: f"10.20.{rnd.randint(1, 30)}.{rnd.randint(2, 250)}"
    docs = {d["documento_id"]: d for d in documentos}
    for v in versiones:
        d = docs[v["documento_id"]]
        hora = datetime.fromisoformat(v["fecha"]) + timedelta(hours=rnd.randint(8, 18), minutes=rnd.randint(0, 59))
        eventos.append(dict(fecha_hora=hora.isoformat(), usuario_id=v["autor_id"], accion="Carga de documento",
                            objeto=v["documento_id"], tramite_id=d["tramite_id"],
                            detalle=f"{d['nombre_requisito']} v{v['version']}", sha256=v["sha256"], ip=ip()))
        if d["aprobado_por"]:
            eventos.append(dict(fecha_hora=(hora + timedelta(hours=rnd.randint(2, 70))).isoformat(),
                                usuario_id=d["aprobado_por"], accion="Aprobación de documento",
                                objeto=v["documento_id"], tramite_id=d["tramite_id"],
                                detalle=f"{d['nombre_requisito']} v{v['version']} aprobado", sha256=v["sha256"], ip=ip()))
    for t in tramites:
        if t.get("fecha_ingreso"):
            eventos.append(dict(fecha_hora=f"{iso(t['fecha_ingreso'])}T{rnd.randint(9, 17):02d}:{rnd.randint(0, 59):02d}:00",
                                usuario_id=t["responsable_id"], accion="Envío a COFEPRIS", objeto=t["tramite_id"],
                                tramite_id=t["tramite_id"], detalle=f"Folio {t['folio_digipris']}", sha256="", ip=ip()))
    for p in prevenciones:
        eventos.append(dict(fecha_hora=f"{p['fecha_aviso_correo']}T{rnd.randint(9, 19):02d}:{rnd.randint(0, 59):02d}:00",
                            usuario_id="SISTEMA", accion="Aviso de prevención detectado", objeto=p["prevencion_id"],
                            tramite_id=p["tramite_id"], detalle=f"Oficio {p['numero_oficio']}", sha256="", ip=""))
    for r in respuestas:
        eventos.append(dict(fecha_hora=f"{r['fecha_envio']}T{rnd.randint(9, 17):02d}:{rnd.randint(0, 59):02d}:00",
                            usuario_id=r["aprobada_por"], accion="Envío de respuesta a prevención", objeto=r["respuesta_id"],
                            tramite_id=r["tramite_id"], detalle=f"Acuse {r['folio_acuse']}", sha256="", ip=ip()))
    eventos.sort(key=lambda e: e["fecha_hora"])
    for i, e in enumerate(eventos, 1):
        e["evento_id"] = f"EV{i:06d}"
    return eventos


# ----------------------------------------------------------------------------- escritura
def escribir(nombre, filas):
    SALIDA_TABLAS.mkdir(parents=True, exist_ok=True)
    if not filas:
        return
    campos = list(filas[0].keys())
    for f in filas:
        for k in f:
            if k not in campos:
                campos.append(k)
    with open(SALIDA_TABLAS / f"{nombre}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)


def generar():
    usuarios = gen_usuarios()
    tramites = armar_tramites(gen_tramites_historicos(), gen_activos(), usuarios)
    documentos, versiones, _, nv = gen_documentos(tramites, usuarios)
    prevenciones, observaciones, tareas, respuestas = gen_prevenciones(tramites, usuarios, versiones, nv)
    bitacora = gen_bitacora(tramites, documentos, versiones, prevenciones, respuestas, usuarios)
    tablas = dict(
        empresa=[dict(EMPRESA, responsable_sanitario_id=por_rol(usuarios, "Responsable Sanitario")["usuario_id"],
                      representante_legal_id=por_rol(usuarios, "Representante Legal")["usuario_id"])],
        productos=[fila_producto(p, tramites) for p in C.PRODUCTOS],
        tipos_tramite=[dict(clave=k, **v) for k, v in C.TIPOS_TRAMITE.items()],
        requisitos_ctd=gen_requisitos(),
        tramites=[fila_tramite(t) for t in tramites],
        documentos=documentos, versiones=versiones, prevenciones=prevenciones,
        observaciones=observaciones, tareas=tareas, respuestas=respuestas,
        usuarios=usuarios, calendario_habil=list(cal.filas()), bitacora=bitacora,
    )
    for nombre, filas in tablas.items():
        escribir(nombre, filas)
    return tablas, tramites, usuarios


if __name__ == "__main__":
    tablas, _, _ = generar()
    for k, v in tablas.items():
        print(f"{k:18s} {len(v):6d}")
