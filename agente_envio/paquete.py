"""Arma el paquete de envío: un ZIP por módulo CTD con los documentos vigentes del expediente y un índice."""
import zipfile
from datetime import datetime
from pathlib import Path


def armar(cola, tramite_id, carpeta):
    carpeta = Path(carpeta)
    docs = cola.documentos(tramite_id)
    descargados = carpeta / "documentos"
    por_modulo = {f"m{i}": [] for i in range(1, 6)}
    for d in docs:
        ruta = cola.descargar(d["archivo"], descargados)
        por_modulo[f"m{str(d['modulo'])[-1]}"].append((d, ruta))
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
