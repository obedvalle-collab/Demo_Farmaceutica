"""Portal COFEPRIS SIMULADO para la demo (no es DIGIPRiS ni lo imita visualmente).

Flujo de la empresa: iniciar sesión → nueva solicitud → cargar los 5 módulos CTD → firmar con e.firma simulada →
acuse con folio. Bandeja de notificaciones: avisos de prevención; al abrir un oficio se genera el acuse de
notificación (en la vida real, ahí empieza a correr el plazo).

Panel del dictaminador (/dictaminador): quien presenta la demo emite prevenciones o resoluciones (Fase 6).

Uso: python -m uvicorn portal_simulado.app:app --port 8765   (desde la raíz del proyecto)
"""
import base64
import hashlib
import secrets
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
DATOS = AQUI / "datos"
ARCHIVOS = DATOS / "archivos"
DB = DATOS / "portal.db"
ARCHIVOS.mkdir(parents=True, exist_ok=True)


def _env():
    vals = {}
    ruta = AQUI.parent / ".env"
    if ruta.exists():
        for l in ruta.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, v = l.split("=", 1)
                vals[k.strip()] = v.strip()
    return vals


ENV = _env()
# Fecha "de hoy" de la demo (la misma que usa la capa de negocio) para fechar oficios y avisos
FECHA_DEMO = date.fromisoformat(ENV.get("PORTAL_FECHA_DEMO", "2026-10-06"))
MODULOS = [("m1", "Módulo 1 · Información administrativa y regional"), ("m2", "Módulo 2 · Resúmenes"),
           ("m3", "Módulo 3 · Calidad"), ("m4", "Módulo 4 · Estudios no clínicos"), ("m5", "Módulo 5 · Estudios clínicos")]
HOMOCLAVES = [("COFEPRIS-04-004-B", "Registro sanitario – medicamento genérico (nacional)"),
              ("COFEPRIS-04-004-G", "Registro sanitario – biotecnológico biocomparable (nacional)"),
              ("COFEPRIS-04-004-A", "Registro sanitario – molécula nueva (nacional)"),
              ("COFEPRIS-04-015-A", "Modificación sin cambio de proceso"),
              ("COFEPRIS-04-016-A", "Modificación con cambio de proceso"),
              ("COFEPRIS-04-023-A", "Prórroga del registro sanitario")]

app = FastAPI(title="Portal COFEPRIS simulado")
app.mount("/static", StaticFiles(directory=AQUI / "static"), name="static")
plantillas = Jinja2Templates(directory=AQUI / "templates")
SESIONES = {}   # token -> rol ('empresa' | 'dictaminador')


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


with db() as c:
    c.executescript("""
    CREATE TABLE IF NOT EXISTS solicitudes (id INTEGER PRIMARY KEY AUTOINCREMENT, referencia TEXT, homoclave TEXT,
        denominacion TEXT, tipo_producto TEXT, estatus TEXT, folio TEXT, creada TEXT, enviada TEXT, cadena TEXT);
    CREATE TABLE IF NOT EXISTS archivos (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitud_id INTEGER, modulo TEXT,
        nombre TEXT, ruta TEXT, bytes INTEGER, sha256 TEXT, cargado TEXT);
    CREATE TABLE IF NOT EXISTS notificaciones (id INTEGER PRIMARY KEY AUTOINCREMENT, solicitud_id INTEGER, folio TEXT,
        tipo TEXT, numero_oficio TEXT, texto TEXT, plazo_dias_habiles INTEGER, ruta_oficio TEXT, emitida TEXT,
        aviso_correo TEXT, abierta TEXT, acuse_apertura TEXT);
    CREATE TABLE IF NOT EXISTS correos_salientes (id INTEGER PRIMARY KEY AUTOINCREMENT, para TEXT, asunto TEXT,
        cuerpo TEXT, creado TEXT, enviado TEXT);
    """)


def ahora():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def ahora_demo():
    """Fecha de la demo con la hora real (para que los plazos cuadren con la capa de negocio)."""
    return f"{FECHA_DEMO.isoformat()} {datetime.now():%H:%M:%S}"


def rol(request):
    return SESIONES.get(request.cookies.get("sesion"))


def vista(request, nombre, **ctx):
    return plantillas.TemplateResponse(request, nombre, dict(rol=rol(request), **ctx))


def exige(request, quien):
    return None if rol(request) == quien else RedirectResponse("/" if quien == "empresa" else "/dictaminador/entrar", 303)


# ------------------------------------------------------------------------------------------ empresa
@app.get("/", response_class=HTMLResponse)
def inicio_sesion(request: Request, error: str = ""):
    if rol(request) == "empresa":
        return RedirectResponse("/inicio", 303)
    return vista(request, "login.html", error=error)


@app.post("/entrar")
def entrar(usuario: str = Form(...), contrasena: str = Form(...)):
    if usuario == ENV.get("PORTAL_USUARIO") and contrasena == ENV.get("PORTAL_PASSWORD"):
        token = secrets.token_hex(16)
        SESIONES[token] = "empresa"
        r = RedirectResponse("/inicio", 303)
        r.set_cookie("sesion", token, httponly=True)
        return r
    return RedirectResponse("/?error=Usuario+o+contraseña+incorrectos", 303)


@app.get("/salir")
def salir(request: Request):
    SESIONES.pop(request.cookies.get("sesion"), None)
    return RedirectResponse("/", 303)


@app.get("/inicio", response_class=HTMLResponse)
def inicio(request: Request):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        sols = c.execute("SELECT * FROM solicitudes ORDER BY id DESC").fetchall()
        pendientes = c.execute("SELECT COUNT(*) FROM notificaciones WHERE abierta IS NULL").fetchone()[0]
    return vista(request, "inicio.html", solicitudes=sols, pendientes=pendientes)


@app.get("/solicitud/nueva", response_class=HTMLResponse)
def nueva(request: Request):
    if (r := exige(request, "empresa")):
        return r
    return vista(request, "nueva.html", homoclaves=HOMOCLAVES)


@app.post("/solicitud/nueva")
def crear(request: Request, homoclave: str = Form(...), denominacion: str = Form(...), tipo_producto: str = Form(...),
          referencia: str = Form("")):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        cur = c.execute("INSERT INTO solicitudes (referencia, homoclave, denominacion, tipo_producto, estatus, creada) "
                        "VALUES (?,?,?,?, 'Borrador', ?)", (referencia, homoclave, denominacion, tipo_producto, ahora()))
    return RedirectResponse(f"/solicitud/{cur.lastrowid}/documentos", 303)


@app.get("/solicitud/{sid}/documentos", response_class=HTMLResponse)
def documentos(request: Request, sid: int, aviso: str = ""):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        s = c.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        cargados = {a["modulo"]: a for a in c.execute("SELECT * FROM archivos WHERE solicitud_id = ?", (sid,))}
    return vista(request, "documentos.html", s=s, modulos=MODULOS, cargados=cargados, aviso=aviso)


@app.post("/solicitud/{sid}/documentos/{modulo}")
async def cargar(request: Request, sid: int, modulo: str, archivo: UploadFile = File(...)):
    if (r := exige(request, "empresa")):
        return r
    contenido = await archivo.read()
    if len(contenido) > 100 * 1024 * 1024:
        return RedirectResponse(f"/solicitud/{sid}/documentos?aviso=El+archivo+excede+100+MB", 303)
    destino = ARCHIVOS / f"sol{sid}_{modulo}_{Path(archivo.filename).name}"
    destino.write_bytes(contenido)
    with db() as c:
        c.execute("DELETE FROM archivos WHERE solicitud_id = ? AND modulo = ?", (sid, modulo))
        c.execute("INSERT INTO archivos (solicitud_id, modulo, nombre, ruta, bytes, sha256, cargado) VALUES (?,?,?,?,?,?,?)",
                  (sid, modulo, Path(archivo.filename).name, str(destino), len(contenido),
                   hashlib.sha256(contenido).hexdigest(), ahora()))
    return RedirectResponse(f"/solicitud/{sid}/documentos", 303)


@app.get("/solicitud/{sid}/firma", response_class=HTMLResponse)
def firma(request: Request, sid: int, error: str = ""):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        s = c.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        arch = c.execute("SELECT * FROM archivos WHERE solicitud_id = ? ORDER BY modulo", (sid,)).fetchall()
    faltan = [n for m, n in MODULOS if m not in {a["modulo"] for a in arch}]
    return vista(request, "firma.html", s=s, archivos=arch, faltan=faltan, error=error)


@app.post("/solicitud/{sid}/firmar")
def firmar(request: Request, sid: int, contrasena_efirma: str = Form(...), acepto: str = Form("")):
    if (r := exige(request, "empresa")):
        return r
    if contrasena_efirma != ENV.get("PORTAL_EFIRMA_PASSWORD") or not acepto:
        return RedirectResponse(f"/solicitud/{sid}/firma?error=Contraseña+de+e.firma+incorrecta+o+falta+aceptar+la+declaración", 303)
    folio = f"DGP-{datetime.now().year}-{secrets.randbelow(90000) + 10000}"
    with db() as c:
        arch = c.execute("SELECT sha256 FROM archivos WHERE solicitud_id = ? ORDER BY modulo", (sid,)).fetchall()
        cadena = hashlib.sha256(("|".join(a[0] for a in arch) + folio).encode()).hexdigest()
        c.execute("UPDATE solicitudes SET estatus = 'Enviada', folio = ?, enviada = ?, cadena = ? WHERE id = ?",
                  (folio, ahora(), cadena, sid))
    return RedirectResponse(f"/solicitud/{sid}/acuse", 303)


@app.get("/solicitud/{sid}/acuse", response_class=HTMLResponse)
def acuse(request: Request, sid: int):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        s = c.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        arch = c.execute("SELECT * FROM archivos WHERE solicitud_id = ? ORDER BY modulo", (sid,)).fetchall()
    return vista(request, "acuse.html", s=s, archivos=arch)


@app.get("/notificaciones", response_class=HTMLResponse)
def notificaciones(request: Request):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        ns = c.execute("SELECT * FROM notificaciones ORDER BY id DESC").fetchall()
    return vista(request, "notificaciones.html", notificaciones=ns)


@app.post("/notificaciones/{nid}/abrir")
def abrir(request: Request, nid: int):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        n = c.execute("SELECT * FROM notificaciones WHERE id = ?", (nid,)).fetchone()
        if n and not n["abierta"]:
            c.execute("UPDATE notificaciones SET abierta = ?, acuse_apertura = ? WHERE id = ?",
                      (ahora(), f"ACN-{secrets.token_hex(4).upper()}", nid))
    return RedirectResponse("/notificaciones", 303)


@app.get("/notificaciones/{nid}/oficio")
def oficio(request: Request, nid: int):
    if (r := exige(request, "empresa")):
        return r
    with db() as c:
        n = c.execute("SELECT * FROM notificaciones WHERE id = ?", (nid,)).fetchone()
    if not n or not n["abierta"] or not n["ruta_oficio"]:
        return RedirectResponse("/notificaciones", 303)
    return FileResponse(n["ruta_oficio"], media_type="application/pdf", filename=Path(n["ruta_oficio"]).name)


# ------------------------------------------------------------------------------------------ dictaminador
@app.get("/dictaminador/entrar", response_class=HTMLResponse)
def dict_login(request: Request, error: str = ""):
    return vista(request, "dict_login.html", error=error)


@app.post("/dictaminador/entrar")
def dict_entrar(contrasena: str = Form(...)):
    if contrasena == ENV.get("PORTAL_DICTAMINADOR_PASSWORD"):
        token = secrets.token_hex(16)
        SESIONES[token] = "dictaminador"
        r = RedirectResponse("/dictaminador", 303)
        r.set_cookie("sesion", token, httponly=True)
        return r
    return RedirectResponse("/dictaminador/entrar?error=Contraseña+incorrecta", 303)


@app.get("/dictaminador", response_class=HTMLResponse)
def dictaminador(request: Request):
    if (r := exige(request, "dictaminador")):
        return r
    with db() as c:
        sols = c.execute("SELECT * FROM solicitudes WHERE folio IS NOT NULL ORDER BY id DESC").fetchall()
        ns = c.execute("SELECT * FROM notificaciones ORDER BY id DESC").fetchall()
    import oficio_pdf
    return vista(request, "dictaminador.html", solicitudes=sols, notificaciones=ns, catalogo=oficio_pdf.catalogo())


@app.post("/dictaminador/prevenir/{sid}")
async def prevenir(request: Request, sid: int):
    if (r := exige(request, "dictaminador")):
        return r
    import oficio_pdf
    form = await request.form()
    indices = [int(v) for v in form.getlist("obs")]
    plazo = int(form.get("plazo") or 10)
    if not indices:
        return RedirectResponse("/dictaminador", 303)
    with db() as c:
        s = c.execute("SELECT * FROM solicitudes WHERE id = ?", (sid,)).fetchone()
        n = c.execute("SELECT COUNT(*) FROM notificaciones").fetchone()[0] + 1
    numero = f"CAS/DERS/{7000 + n}/{FECHA_DEMO.year}"
    ruta = ARCHIVOS / f"oficio_{numero.replace('/', '-')}.pdf"
    obs = oficio_pdf.generar(ruta, dict(s), numero, indices, plazo, FECHA_DEMO)
    with db() as c:
        c.execute("""INSERT INTO notificaciones (solicitud_id, folio, tipo, numero_oficio, texto, plazo_dias_habiles,
                     ruta_oficio, emitida, aviso_correo) VALUES (?,?,?,?,?,?,?,?,?)""",
                  (sid, s["folio"], "Prevención", numero, f"{len(obs)} observaciones", plazo, str(ruta), ahora_demo(), ahora_demo()))
        c.execute("UPDATE solicitudes SET estatus = 'Prevenida' WHERE id = ?", (sid,))
        c.execute("INSERT INTO correos_salientes (para, asunto, cuerpo, creado) VALUES (?,?,?,?)",
                  ("regulatorio@altamira-lab.example", f"Aviso de disponibilidad de acto administrativo – Folio {s['folio']}",
                   f"Se informa que se encuentra disponible en el portal un acto administrativo relacionado con su solicitud "
                   f"con folio {s['folio']} (homoclave {s['homoclave']}). Cuenta con cinco días hábiles para consultarlo; "
                   "de no hacerlo, se notificará por estrados electrónicos.\n\nEste es un mensaje automático del portal simulado.",
                   ahora_demo()))
    return RedirectResponse("/dictaminador", 303)


# ------------------------------------------------------------------------------------------ buzón simulado
def _autorizado(request):
    """El buzón de la empresa se consulta con el usuario y contraseña del portal (autenticación básica)."""
    try:
        tipo, valor = request.headers.get("authorization", "").split(" ", 1)
        usuario, clave = base64.b64decode(valor).decode().split(":", 1)
        return tipo.lower() == "basic" and usuario == ENV.get("PORTAL_USUARIO") and clave == ENV.get("PORTAL_PASSWORD")
    except Exception:
        return False


@app.get("/api/buzon")
def buzon(request: Request, desde: int = 0):
    """Buzón simulado de regulatorio@altamira-lab.example: los correos que 'COFEPRIS' envía a la empresa."""
    if not _autorizado(request):
        return JSONResponse({"error": "no autorizado"}, status_code=401)
    with db() as c:
        filas = c.execute("SELECT * FROM correos_salientes WHERE id > ? ORDER BY id", (desde,)).fetchall()
    return [dict(id=f["id"], de="notificaciones@portal-simulado.example", para=f["para"], asunto=f["asunto"],
                 cuerpo=f["cuerpo"], fecha=f["creado"]) for f in filas]
