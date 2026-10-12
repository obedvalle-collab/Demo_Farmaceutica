"""Robot de envío: atiende la cola APP.ENVIOS de Snowflake y Databricks.

Por cada solicitud: arma el paquete CTD, abre el navegador, el agente llena el portal simulado, sube la captura a la
plataforma y espera la confirmación de la persona en la app; al confirmar, firma, envía y registra folio y acuse.

Uso (desde la raíz del proyecto, con el portal simulado encendido):
    python agente_envio/robot.py                    # atiende ambas plataformas, modo automático
    python agente_envio/robot.py --modo guion       # respaldo sin IA
    python agente_envio/robot.py --plataforma snowflake --una-vez
"""
import argparse
import base64
import io
import threading
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
for _p in ("app/comun", "compartido"):
    sys.path.insert(0, str(AQUI.parent / _p))
import agente  # noqa: E402
import paquete  # noqa: E402
from cola import ColaDatabricks, ColaSnowflake  # noqa: E402

ESPERA_CONFIRMACION_S = 900


def leer_env():
    vals = {}
    for l in (AQUI.parent / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in l and not l.strip().startswith("#"):
            k, v = l.split("=", 1)
            vals[k.strip()] = v.strip()
    return vals


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


class Transmision(threading.Thread):
    """Sube a la plataforma el último cuadro de la pantalla del agente (≈ 1 por segundo) para verlo en vivo en la app.
    Corre en su propio hilo y con su propia conexión para no frenar al agente; si se acumulan cuadros, solo sube el último."""

    def __init__(self, clase_cola, envio_id):
        super().__init__(daemon=True)
        self.clase_cola, self.envio_id = clase_cola, envio_id
        self.cuadro, self.listo, self.fin = None, threading.Event(), threading.Event()

    def poner(self, paso, accion, png):
        self.cuadro = (paso, accion, png)
        self.listo.set()

    def run(self):
        cola = self.clase_cola()
        try:
            while not (self.fin.is_set() and not self.listo.is_set()):
                if not self.listo.wait(0.5):
                    continue
                self.listo.clear()
                paso, accion, png = self.cuadro
                try:
                    cola.vivo(self.envio_id, paso, accion, _comprimir(png))
                except Exception as e:
                    log(f"  (transmisión: {str(e)[:120]})")
                time.sleep(0.8)
        finally:
            cola.cerrar_conexion()

    def parar(self):
        self.fin.set()
        self.join(timeout=15)


def _comprimir(png, ancho=960, calidad=60):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    im = im.resize((ancho, round(im.height * ancho / im.width)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=calidad, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def atender(cola, envio, env, modo, navegador):
    eid, tramite = envio["envio_id"], envio["tramite_id"]
    if not cola.tomar(eid):
        return
    log(f"{cola.nombre}: envío {eid[:8]} del trámite {tramite} ({modo})")
    try:
        carpeta = Path(tempfile.gettempdir()) / "claude" / "paquetes" / eid
        zips, n = paquete.armar(cola, tramite, carpeta)
        log(f"  paquete armado: {n} documentos en 5 módulos")
        solicitud = cola.datos_tramite(tramite)

        def confirmar(png, resumen):
            ruta = cola.subir_captura(png, f"{eid}_confirmacion.png")
            cola.actualizar(eid, estatus="Esperando confirmación", captura=ruta, resumen_agente=resumen[:2000])
            log("  esperando confirmación en la app…")
            t = time.time()
            while time.time() - t < ESPERA_CONFIRMACION_S:
                est = cola.estatus(eid)
                if est in ("Confirmado", "Cancelado"):
                    log(f"  decisión: {est}")
                    if est == "Confirmado":
                        cola.actualizar(eid, estatus="Enviando")
                    return "CONFIRMADO" if est == "Confirmado" else "CANCELADO"
                time.sleep(3)
            cola.actualizar(eid, estatus="Cancelado", error="Tiempo de espera de confirmación agotado")
            return "CANCELADO"

        contexto = navegador.new_context(viewport={"width": agente.ANCHO, "height": agente.ALTO}, locale="es-MX")
        page = contexto.new_page()
        trans = Transmision(type(cola), eid)
        trans.start()

        def en_vivo(pg, paso, accion):
            trans.poner(paso, accion, pg.screenshot())

        if modo == "computer_use":
            try:
                r = agente.enviar_con_computer_use(page, env, solicitud, zips, confirmar, registrar=log, en_vivo=en_vivo)
            finally:
                trans.parar()
        else:
            trans.parar()   # el modo guion no transmite
            r = agente.enviar_con_guion(page, env, solicitud, zips, confirmar)
        contexto.close()
        if r.get("exito"):
            ruta = cola.subir_captura(r["acuse"], f"{eid}_acuse.png")
            cola.actualizar(eid, estatus="Enviado", folio=r.get("folio", ""), cadena_acuse=r.get("cadena", ""),
                            enviado_en=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), captura=ruta, modo=modo,
                            pasos=r.get("pasos", 0), segundos=r.get("segundos", 0), costo_usd=r.get("costo_usd", 0))
            log(f"  ✓ enviado · folio {r.get('folio')} · {r.get('pasos')} pasos · {r.get('segundos')} s · ${r.get('costo_usd')}")
        elif cola.estatus(eid) != "Cancelado":
            cola.actualizar(eid, estatus="Error", error=r.get("nota", "")[:2000], modo=modo,
                            pasos=r.get("pasos", 0), segundos=r.get("segundos", 0), costo_usd=r.get("costo_usd", 0))
            log(f"  ✗ {r.get('nota')}")
        else:
            cola.actualizar(eid, modo=modo, pasos=r.get("pasos", 0), segundos=r.get("segundos", 0), costo_usd=r.get("costo_usd", 0))
    except Exception as e:
        log(f"  ✗ error: {e}")
        cola.actualizar(eid, estatus="Error", error=str(e)[:2000])


# ------------------------------------------------------------------------------------------ Fase 6
def datos_de(cola):
    """Objeto con la lógica del ciclo de prevenciones (compartida) para la plataforma de la cola."""
    if cola.nombre == "Snowflake":
        from snowflake.snowpark import Session
        from datos_snowflake import DatosSnowflake
        return DatosSnowflake(Session.builder.config("connection_name", "obed_farma").create())
    from datos_databricks import DatosDatabricks
    return DatosDatabricks(cola.w, cola.WAREHOUSE)


def vigilar_buzon(env, ciclos, visto):
    """Vigía: lee el buzón simulado de la empresa y registra los avisos de COFEPRIS en cada plataforma."""
    try:
        r = requests.get(f"{env['PORTAL_URL']}/api/buzon", params={"desde": visto["id"]},
                         auth=(env["PORTAL_USUARIO"], env["PORTAL_PASSWORD"]), timeout=10)
        correos = r.json() if r.ok else []
    except requests.RequestException:
        return
    for correo in correos:
        visto["id"] = max(visto["id"], correo["id"])
        for cola, d in ciclos:
            if correo["id"] <= visto.get(cola.nombre, 0):
                continue
            aviso = d.registrar_aviso(correo)
            visto[cola.nombre] = correo["id"]
            if aviso:
                log(f"{cola.nombre}: aviso de COFEPRIS · folio {aviso['folio']} → {aviso['tramite_id']} · abrir antes del {aviso['fecha_limite_apertura']}")
                log(f"  alertas por correo enviadas: {d.enviar_correos()}")


def abrir_oficio(env, navegador, folio):
    """Entra al portal, abre la notificación del folio (genera el acuse) y descarga el oficio."""
    contexto = navegador.new_context(accept_downloads=True, locale="es-MX")
    page = contexto.new_page()
    page.goto(env["PORTAL_URL"])
    page.fill("#usuario", env["PORTAL_USUARIO"]); page.fill("#contrasena", env["PORTAL_PASSWORD"]); page.click("#btn-entrar")
    page.goto(f"{env['PORTAL_URL']}/notificaciones")
    fila = page.locator("tr", has_text=folio).first
    if fila.locator("button", has_text="Abrir").count():
        fila.locator("button", has_text="Abrir").click()
        fila = page.locator("tr", has_text=folio).first
    acuse = re.search(r"ACN-[0-9A-F]+", fila.inner_text())
    with page.expect_download() as d:
        fila.locator("a", has_text="Descargar oficio").click()
    descarga = d.value
    contenido = Path(descarga.path()).read_bytes()
    nombre = descarga.suggested_filename
    contexto.close()
    return nombre, contenido, acuse.group(0) if acuse else ""


def atender_acciones(env, navegador, ciclos):
    for cola, d in ciclos:
        for a in d.acciones_pendientes():
            log(f"{cola.nombre}: abrir oficio del folio {a['folio']}")
            d.actualizar_accion(a["accion_id"], "En curso")
            try:
                nombre, contenido, acuse = abrir_oficio(env, navegador, a["folio"])
                log(f"  oficio descargado ({nombre}, acuse {acuse}); analizando con IA…")
                r = d.registrar_oficio(a["aviso_id"], nombre, contenido, acuse)
                d.actualizar_accion(a["accion_id"], "Completada", f"{r['observaciones']} observaciones · vence {r['fecha_limite']}")
                log(f"  ✓ {r['observaciones']} observaciones · plazo {r['plazo']} días hábiles · vence {r['fecha_limite']}")
                log(f"  alertas por correo enviadas: {d.enviar_correos()}")
            except Exception as e:
                log(f"  ✗ {e}")
                d.actualizar_accion(a["accion_id"], "Error", str(e))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plataforma", choices=["ambas", "snowflake", "databricks"], default="ambas")
    ap.add_argument("--modo", choices=["auto", "computer_use", "guion"], default="auto")
    ap.add_argument("--una-vez", action="store_true", help="atiende lo pendiente y termina")
    ap.add_argument("--ver", action="store_true", help="muestra la ventana del navegador")
    a = ap.parse_args()
    env = leer_env()
    modo = a.modo if a.modo != "auto" else ("computer_use" if env.get("ANTHROPIC_API_KEY") else "guion")
    colas = ([ColaSnowflake()] if a.plataforma in ("ambas", "snowflake") else []) + \
            ([ColaDatabricks()] if a.plataforma in ("ambas", "databricks") else [])
    ciclos = [(c, datos_de(c)) for c in colas]
    visto = {"id": min(d.ultimo_correo() for _, d in ciclos)}
    visto.update({c.nombre: d.ultimo_correo() for c, d in ciclos})
    log(f"Robot de envío y vigía en modo {modo} · atendiendo: {', '.join(c.nombre for c in colas)} · buzón desde el correo {visto['id']}")
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=not a.ver)
        agente.MOSTRAR_PUNTERO = a.ver
        try:
            while True:
                for c in colas:
                    for envio in c.pendientes():
                        atender(c, envio, env, modo, navegador)
                vigilar_buzon(env, ciclos, visto)
                atender_acciones(env, navegador, ciclos)
                if a.una_vez:
                    break
                time.sleep(5)
        except KeyboardInterrupt:
            log("Robot detenido")
        finally:
            navegador.close()
            for c in colas:
                c.cerrar()


if __name__ == "__main__":
    main()
