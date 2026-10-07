"""Genera el oficio de prevención (PDF simulado) con las observaciones que elige el dictaminador en el portal."""
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "datos" / "generador"))
from catalogos import OBSERVACIONES, REQUISITOS  # noqa: E402
from pdf_base import P, Spacer, documento_autoridad, qr_imagen  # noqa: E402

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
LETRAS = {5: "CINCO", 10: "DIEZ", 15: "QUINCE", 20: "VEINTE"}
SECCION = {r["requisito_id"]: r["seccion_ctd"] for r in REQUISITOS}


def catalogo():
    """Observaciones disponibles para el dictaminador (índice, texto corto, cita)."""
    out = []
    for i, (req, norma, clausula, texto, sev, _, _) in enumerate(OBSERVACIONES):
        cita = f"{norma} {clausula}".strip() if norma else "Administrativa"
        out.append(dict(i=i, requisito=req, seccion=SECCION.get(req, ""), cita=cita, texto=texto, severidad=sev))
    return out


def fl(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def generar(ruta, solicitud, numero_oficio, indices, plazo, fecha, representante="Representante legal"):
    obs = [OBSERVACIONES[i] for i in indices]
    flow = [Spacer(1, 2),
            P(f"<b>C. {representante}</b><br/>Laboratorios Altamira, S.A. de C.V.<br/>Presente", "oficio"),
            Spacer(1, 4),
            P(f"Me refiero a su solicitud con número de folio <b>{solicitud['folio']}</b>, relativa al trámite con "
              f"homoclave <b>{solicitud['homoclave']}</b> del medicamento <b>{solicitud['denominacion']}</b>.", "oficio"),
            P(f"Del análisis de la documentación presentada, y con fundamento en los artículos 17-A de la Ley Federal de "
              f"Procedimiento Administrativo, y 153, 155 y 156 del Reglamento de Insumos para la Salud, se le <b>PREVIENE</b> "
              f"para que, en un plazo de <b>{LETRAS.get(plazo, str(plazo))} ({plazo}) DÍAS HÁBILES</b>, contados a partir del "
              f"día hábil siguiente a aquel en que surta efectos la notificación del presente oficio, subsane lo siguiente:", "oficio")]
    for n, (req, norma, clausula, texto, *_r) in enumerate(obs, 1):
        fund = f"{norma}, numeral {clausula}" if norma and clausula else (norma or next(
            (r["fundamento"] for r in REQUISITOS if r["requisito_id"] == req), ""))
        flow.append(P(f"<b>{n}.</b> {texto} <i>Fundamento: {fund}.</i> (Sección CTD {SECCION.get(req, '')})", "oficio"))
    flow += [P("Se le apercibe que, de no desahogar la presente prevención en el plazo señalado, la solicitud se tendrá por no "
               "presentada, de conformidad con el artículo 155 del Reglamento de Insumos para la Salud.", "oficio"),
             Spacer(1, 8), P("Atentamente,", "oficio"),
             P("<b>Dictaminador(a) de la demostración</b><br/>Comisión de Autorización Sanitaria (simulada)", "oficio"),
             Spacer(1, 6), qr_imagen(f"SIMULADO|{numero_oficio}|{solicitud['folio']}", 22 * 2.83465)]
    documento_autoridad(Path(ruta), flow, "Comisión de Autorización Sanitaria",
                        [f"Oficio No. {numero_oficio}", "Asunto: Se previene", f"Ciudad de México, a {fl(fecha)}"])
    return [dict(numero=n, requisito=o[0], norma=o[1] or "", clausula=o[2] or "", texto=o[3]) for n, o in enumerate(obs, 1)]
