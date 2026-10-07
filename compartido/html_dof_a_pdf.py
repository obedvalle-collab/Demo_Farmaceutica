"""Convierte las páginas del DOF guardadas en HTML a PDF de texto, para que todas las normas entren
por el mismo camino (lectura de PDF con IA) en ambas plataformas.

Uso: python compartido/html_dof_a_pdf.py
"""
import html
import re
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

NORMAS = Path(__file__).resolve().parents[1] / "normas"
ESTILO = ParagraphStyle("t", fontName="Times-Roman", fontSize=10, leading=13, spaceAfter=4)
NOTA = ParagraphStyle("n", fontName="Helvetica-Oblique", fontSize=7.5, leading=9)


def texto_cuerpo(ruta):
    h = ruta.read_bytes().decode("utf-8", errors="replace")
    fin = h.find("En el documento que usted est")
    inicio = re.search(r"DOF:\s*\d{2}/\d{2}/\d{4}", h)
    cuerpo = h[inicio.start(): fin if fin > 0 else len(h)]
    cuerpo = re.sub(r"(?is)<(script|style).*?</\1>", "", cuerpo)
    cuerpo = re.sub(r"(?i)<br\s*/?>|</(p|div|tr|h\d)>", "\n", cuerpo)
    cuerpo = html.unescape(re.sub(r"<[^>]+>", "", cuerpo))
    lineas = [re.sub(r"[ \t\xa0]+", " ", l).strip() for l in cuerpo.splitlines()]
    return [l for l in lineas if l]


def convertir(ruta):
    destino = ruta.with_suffix(".pdf")
    flow = [Paragraph(f"Texto extraído de {ruta.name} (página del DOF). Conversión automática a PDF para su "
                      "lectura con IA; tomar como referencia la publicación oficial.", NOTA), Spacer(1, 6)]
    flow += [Paragraph(html.escape(l), ESTILO) for l in texto_cuerpo(ruta)]
    SimpleDocTemplate(str(destino), pagesize=letter, leftMargin=20 * mm, rightMargin=20 * mm,
                      topMargin=18 * mm, bottomMargin=18 * mm, title=ruta.stem).build(flow)
    return destino


if __name__ == "__main__":
    for r in sorted(NORMAS.glob("*.html")):
        print(convertir(r).name)
