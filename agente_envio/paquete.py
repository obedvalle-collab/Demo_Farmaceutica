"""Arma el paquete de envío: un ZIP por módulo CTD con los documentos vigentes del expediente y un índice.

Para que la ventana del agente se abra de inmediato, el paquete se arma en segundo plano (PaqueteDiferido) mientras el
agente inicia sesión y llena la solicitud; solo se espera cuando el agente va a adjuntar el primer módulo.
Los PDF se guardan en una caché local: cada versión es un archivo distinto, así que se descargan una sola vez.
"""
import tempfile
import threading
import time
import zipfile
from datetime import datetime
from pathlib import Path

CACHE = Path(tempfile.gettempdir()) / "claude" / "cache_expedientes"


def _documento(cola, archivo):
    ruta = CACHE / archivo
    if ruta.exists() and ruta.stat().st_size > 0:
        return ruta
    return cola.descargar(archivo, ruta.parent)


def armar(cola, tramite_id, carpeta):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    docs = cola.documentos(tramite_id)
    por_modulo = {f"m{i}": [] for i in range(1, 6)}
    for d in docs:
        por_modulo[f"m{str(d['modulo'])[-1]}"].append((d, _documento(cola, d["archivo"])))
    zips = {}
    for m, items in por_modulo.items():
        z = carpeta / f"{tramite_id}_CTD_{m.upper()}.zip"
        with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as fh:
            indice = [f"Expediente {tramite_id} · Módulo {m[-1].upper()} · generado {datetime.now():%Y-%m-%d %H:%M}", ""]
            for d, ruta in items:
                nombre = f"{d['seccion_ctd']}_{ruta.name}"
                fh.write(ruta, nombre)
                indice.append(f"{d['seccion_ctd']:10s} v{d['version']}  {nombre}")
            if not items:
                indice.append("Sin documentos aplicables a este módulo para el tipo de trámite.")
            fh.writestr("00_INDICE.txt", "\n".join(indice))
        zips[m] = z
    return zips, len(docs)


class PaqueteDiferido(threading.Thread):
    """Arma el paquete en otro hilo, con su propia conexión. Se usa como el dict de ZIPs: zips["m1"] espera si hace falta."""

    def __init__(self, clase_cola, tramite_id, carpeta, registrar=print):
        super().__init__(daemon=True)
        self.clase_cola, self.tramite_id, self.carpeta, self.registrar = clase_cola, tramite_id, carpeta, registrar
        self.zips, self.n, self.error = None, 0, None
        self.start()

    def run(self):
        t = time.time()
        try:
            cola = self.clase_cola()
            try:
                self.zips, self.n = armar(cola, self.tramite_id, self.carpeta)
            finally:
                cola.cerrar_conexion()
            self.registrar(f"  paquete armado en segundo plano: {self.n} documentos en 5 módulos ({time.time() - t:.1f} s)")
        except Exception as e:
            self.error = e
            self.registrar(f"  ✗ no se pudo armar el paquete: {e}")

    def esperar(self):
        self.join()
        if self.error:
            raise RuntimeError(f"No se pudo armar el paquete: {self.error}")
        return self.zips

    def __getitem__(self, modulo):
        return self.esperar()[modulo]

    def items(self):
        return self.esperar().items()
