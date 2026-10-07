"""Piezas visuales compartidas por los PDF: membretes, logotipo, firmas, sellos, QR y efecto de escaneo."""
import io
import time
import math
from datetime import datetime
import random

import pymupdf
import qrcode
from PIL import Image, ImageFilter, ImageEnhance, ImageOps
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import (Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from config import AVISO_FICTICIO, AVISO_SIMULADO_AUTORIDAD, EMPRESA

rl_config.invariant = 1   # PDF idénticos byte a byte en cada corrida (sin fecha de creación aleatoria)

AZUL = colors.HexColor("#12355B")
TURQUESA = colors.HexColor("#1F8A8A")
DORADO = colors.HexColor("#C99A2E")
GRIS = colors.HexColor("#5F6B76")
GRIS_CLARO = colors.HexColor("#E9EEF2")
VINO = colors.HexColor("#5E2A35")
TINTA = colors.HexColor("#1B3A8C")

_base = getSampleStyleSheet()
E = {
    "titulo": ParagraphStyle("titulo", parent=_base["Title"], fontName="Helvetica-Bold", fontSize=15,
                             leading=19, textColor=AZUL, spaceAfter=4),
    "subtitulo": ParagraphStyle("subtitulo", parent=_base["Normal"], fontName="Helvetica", fontSize=10,
                                leading=13, textColor=GRIS, alignment=TA_CENTER, spaceAfter=8),
    "h1": ParagraphStyle("h1", parent=_base["Heading2"], fontName="Helvetica-Bold", fontSize=11.5,
                         leading=14, textColor=AZUL, spaceBefore=9, spaceAfter=4),
    "h2": ParagraphStyle("h2", parent=_base["Heading3"], fontName="Helvetica-Bold", fontSize=10,
                         leading=12.5, textColor=TURQUESA, spaceBefore=6, spaceAfter=2),
    "txt": ParagraphStyle("txt", parent=_base["Normal"], fontName="Helvetica", fontSize=9.2, leading=12.4,
                          alignment=TA_JUSTIFY, spaceAfter=4),
    "txt_c": ParagraphStyle("txt_c", parent=_base["Normal"], fontName="Helvetica", fontSize=9.2,
                            leading=12.4, alignment=TA_CENTER),
    "txt_d": ParagraphStyle("txt_d", parent=_base["Normal"], fontName="Helvetica", fontSize=9.2,
                            leading=12.4, alignment=TA_RIGHT),
    "celda": ParagraphStyle("celda", parent=_base["Normal"], fontName="Helvetica", fontSize=8.2, leading=10.2),
    "celda_b": ParagraphStyle("celda_b", parent=_base["Normal"], fontName="Helvetica-Bold", fontSize=8.2,
                              leading=10.2, textColor=colors.white),
    "nota": ParagraphStyle("nota", parent=_base["Normal"], fontName="Helvetica-Oblique", fontSize=7.6,
                           leading=9.5, textColor=GRIS),
    "oficio": ParagraphStyle("oficio", parent=_base["Normal"], fontName="Times-Roman", fontSize=10.5,
                             leading=14, alignment=TA_JUSTIFY, spaceAfter=6),
    "oficio_b": ParagraphStyle("oficio_b", parent=_base["Normal"], fontName="Times-Bold", fontSize=10.5,
                               leading=14, spaceAfter=4),
}


def P(texto, estilo="txt"):
    return Paragraph(texto, E[estilo])


# --------------------------------------------------------------------------------- tablas
def tabla(filas, anchos, encabezado=True, zebra=True, color=AZUL, alinear_centro=()):
    datos = []
    for i, fila in enumerate(filas):
        estilo = "celda_b" if (i == 0 and encabezado) else "celda"
        datos.append([c if isinstance(c, Flowable) else Paragraph(str(c), E[estilo]) for c in fila])
    t = Table(datos, colWidths=anchos, repeatRows=1 if encabezado else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4CE")),
          ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if encabezado:
        st.append(("BACKGROUND", (0, 0), (-1, 0), color))
    if zebra:
        for r in range(1 if encabezado else 0, len(filas)):
            if r % 2 == 0:
                st.append(("BACKGROUND", (0, r), (-1, r), GRIS_CLARO))
    for c in alinear_centro:
        st.append(("ALIGN", (c, 0), (c, -1), "CENTER"))
    t.setStyle(TableStyle(st))
    return t


def tabla_datos(pares, ancho_etiqueta=48 * mm, ancho_valor=126 * mm):
    """Tabla de dos columnas etiqueta: valor."""
    filas = [[Paragraph(f"<b>{a}</b>", E["celda"]), Paragraph(str(b), E["celda"])] for a, b in pares]
    t = Table(filas, colWidths=[ancho_etiqueta, ancho_valor])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C4CE")),
                           ("BACKGROUND", (0, 0), (0, -1), GRIS_CLARO),
                           ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                           ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
    return t


# --------------------------------------------------------------------------------- dibujo
def dibujar_logo(c, x, y, escala=1.0, monocromo=False):
    """Logotipo ficticio: dos montañas y un sol, con el nombre."""
    s = escala
    azul = colors.black if monocromo else AZUL
    tur = colors.HexColor("#444444") if monocromo else TURQUESA
    oro = colors.HexColor("#777777") if monocromo else DORADO
    c.saveState()
    c.setFillColor(oro)
    c.circle(x + 15 * s, y + 13 * s, 4.2 * s, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(x, y); p.lineTo(x + 11 * s, y + 15 * s); p.lineTo(x + 22 * s, y); p.close()
    c.setFillColor(azul); c.drawPath(p, stroke=0, fill=1)
    p = c.beginPath()
    p.moveTo(x + 9 * s, y); p.lineTo(x + 20 * s, y + 11 * s); p.lineTo(x + 31 * s, y); p.close()
    c.setFillColor(tur); c.drawPath(p, stroke=0, fill=1)
    c.setFillColor(azul)
    c.setFont("Helvetica-Bold", 13 * s)
    c.drawString(x + 36 * s, y + 6 * s, "ALTAMIRA")
    c.setFont("Helvetica", 6.2 * s)
    c.setFillColor(GRIS if not monocromo else colors.black)
    c.drawString(x + 36.5 * s, y - 0.5 * s, "L A B O R A T O R I O S")
    c.restoreState()


def dibujar_firma(c, x, y, ancho=42 * mm, alto=12 * mm, semilla=1, color=TINTA):
    """Rúbrica manuscrita simulada con curvas de Bézier."""
    r = random.Random(semilla)
    c.saveState()
    c.setStrokeColor(color)
    c.setLineCap(1); c.setLineJoin(1)
    px, py = x + r.uniform(0, 4 * mm), y + alto * r.uniform(0.3, 0.6)
    for _ in range(r.randint(4, 7)):
        c.setLineWidth(r.uniform(0.6, 1.25))
        nx = min(x + ancho, px + r.uniform(4 * mm, 11 * mm))
        ny = y + alto * r.uniform(0.05, 0.95)
        p = c.beginPath()
        p.moveTo(px, py)
        p.curveTo(px + r.uniform(-6, 18), py + r.uniform(-18, 22), nx + r.uniform(-18, 6),
                  ny + r.uniform(-22, 18), nx, ny)
        c.drawPath(p, stroke=1, fill=0)
        px, py = nx, ny
    c.setLineWidth(0.8)
    c.line(x + r.uniform(0, 8 * mm), y + r.uniform(0, 3), x + ancho * r.uniform(0.6, 1.0), y + r.uniform(1, 5))
    c.restoreState()


def dibujar_sello(c, cx, cy, radio, texto_circular, texto_centro, color=colors.HexColor("#2A4FA8"),
                  fecha=None, angulo=0):
    c.saveState()
    c.translate(cx, cy)
    c.rotate(angulo)
    c.setStrokeColor(color); c.setFillColor(color)
    c.setStrokeAlpha(0.8); c.setFillAlpha(0.8)
    c.setLineWidth(1.6); c.circle(0, 0, radio, stroke=1, fill=0)
    c.setLineWidth(0.7); c.circle(0, 0, radio - 4.5, stroke=1, fill=0)
    c.circle(0, 0, radio * 0.55, stroke=1, fill=0)
    texto = f"  {texto_circular}  •"
    tam = max(5.2, min(7.5, radio * 0.17))
    c.setFont("Helvetica-Bold", tam)
    paso = 360 / max(len(texto), 1)
    for i, ch in enumerate(texto):
        ang = 90 - i * paso
        c.saveState()
        c.rotate(ang)
        c.translate(0, radio - 3.2 - tam * 0.75)
        c.rotate(-90)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
    c.setFont("Helvetica-Bold", tam * 1.05)
    lineas = texto_centro.split("\n")
    for i, l in enumerate(lineas):
        c.drawCentredString(0, (len(lineas) / 2 - i - 0.75) * tam * 1.2, l)
    if fecha:
        c.setFont("Helvetica", tam * 0.9)
        c.drawCentredString(0, -radio * 0.42, fecha)
    c.restoreState()


class Dibujo(Flowable):
    """Flowable genérico que llama a una función de dibujo."""

    def __init__(self, ancho, alto, funcion):
        super().__init__()
        self.width, self.height, self.funcion = ancho, alto, funcion

    def draw(self):
        self.funcion(self.canv, self.width, self.height)


def bloque_firmas(firmantes, semilla=7):
    """firmantes: lista de (rol, nombre, puesto, fecha, firmado: bool)."""
    celdas_firma, celdas_texto = [], []
    ancho = 174 * mm / len(firmantes)
    for i, (rol, nombre, puesto, fecha, firmado) in enumerate(firmantes):
        def f(c, w, h, firmado=firmado, i=i):
            if firmado:
                dibujar_firma(c, w * 0.18, 2, w * 0.62, h - 4, semilla=semilla * 31 + i)
            c.setStrokeColor(GRIS); c.setLineWidth(0.5); c.line(w * 0.1, 1, w * 0.9, 1)
        celdas_firma.append(Dibujo(ancho - 6, 15 * mm, f))
        celdas_texto.append(Paragraph(f"<b>{rol}</b><br/>{nombre}<br/><font size=7>{puesto}</font><br/>"
                                      f"<font size=7>Fecha: {fecha if firmado else '____________'}</font>",
                                      E["txt_c"]))
    t = Table([celdas_firma, celdas_texto], colWidths=[ancho] * len(firmantes))
    t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "BOTTOM"), ("TOPPADDING", (0, 0), (-1, -1), 2)]))
    return t


def qr_imagen(contenido, tam=26 * mm):
    img = qrcode.make(contenido, box_size=4, border=1)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    reader = ImageReader(buf)

    def f(c, w, h):
        c.drawImage(reader, 0, 0, w, h)
    return Dibujo(tam, tam, f)


# --------------------------------------------------------------------------------- documento
class LienzoNumerado(rl_canvas.Canvas):
    """Canvas que conoce el total de páginas ('Página X de Y')."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._paginas = []

    def showPage(self):
        self._paginas.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._paginas)
        for estado in self._paginas:
            self.__dict__.update(estado)
            self._total_paginas = total
            self.decorar(self)
            super().showPage()
        super().save()


def documento_altamira(ruta, titulo, codigo, flowables, revision="01", subtitulo=None, area="Asuntos Regulatorios"):
    """PDF con membrete de Laboratorios Altamira."""

    def decorar(c):
        w, h = letter
        dibujar_logo(c, 20 * mm, h - 21 * mm, 0.95)
        c.setFont("Helvetica-Bold", 8); c.setFillColor(AZUL)
        c.drawRightString(w - 20 * mm, h - 13 * mm, titulo[:80])
        c.setFont("Helvetica", 7.2); c.setFillColor(GRIS)
        c.drawRightString(w - 20 * mm, h - 17 * mm, f"Código: {codigo}   Revisión: {revision}   Área: {area}")
        c.drawRightString(w - 20 * mm, h - 21 * mm, f"Página {c.getPageNumber()} de {c._total_paginas}")
        c.setStrokeColor(TURQUESA); c.setLineWidth(1.4); c.line(20 * mm, h - 24 * mm, w - 20 * mm, h - 24 * mm)
        c.setStrokeColor(DORADO); c.setLineWidth(0.6); c.line(20 * mm, h - 25 * mm, w - 20 * mm, h - 25 * mm)
        c.setStrokeColor(GRIS_CLARO); c.setLineWidth(0.6); c.line(20 * mm, 17 * mm, w - 20 * mm, 17 * mm)
        c.setFont("Helvetica", 6.6); c.setFillColor(GRIS)
        c.drawString(20 * mm, 13 * mm, f"{EMPRESA['razon_social']} · {EMPRESA['domicilio_planta']}")
        c.drawString(20 * mm, 9.5 * mm, f"RFC {EMPRESA['rfc']} · Licencia sanitaria {EMPRESA['licencia_sanitaria']} · Tel. {EMPRESA['telefono']}")
        c.setFont("Helvetica-Oblique", 6.2)
        c.drawString(20 * mm, 6 * mm, AVISO_FICTICIO)
        c.drawRightString(w - 20 * mm, 6 * mm, "Documento controlado – Uso interno y regulatorio")

    _construir(ruta, flowables, decorar, [P(titulo, "titulo")] + ([P(subtitulo, "subtitulo")] if subtitulo else []),
               margen_sup=30 * mm)


def documento_autoridad(ruta, flowables, dependencia="Comisión de Autorización Sanitaria", encabezado_extra=None,
                        institucion=("SECRETARÍA DE SALUD", "Comisión Federal para la Protección contra Riesgos Sanitarios"),
                        emisor_pie="COFEPRIS"):
    """PDF con encabezado de autoridad SIMULADA (sin escudos ni logotipos oficiales) y marca de agua."""

    def decorar(c):
        w, h = letter
        c.saveState()
        c.setFillColor(VINO); c.rect(20 * mm, h - 27 * mm, 2.2 * mm, 15 * mm, stroke=0, fill=1)
        c.setFont("Helvetica-Bold", 10.5); c.drawString(25 * mm, h - 15.5 * mm, institucion[0])
        c.setFont("Helvetica", 8.4); c.setFillColor(colors.HexColor("#3B3B3B"))
        c.drawString(25 * mm, h - 20 * mm, institucion[1])
        c.drawString(25 * mm, h - 24 * mm, dependencia)
        if encabezado_extra:
            c.setFont("Helvetica", 7.6)
            for i, l in enumerate(encabezado_extra):
                c.drawRightString(w - 20 * mm, h - 15.5 * mm - i * 4 * mm, l)
        c.setStrokeColor(VINO); c.setLineWidth(0.8); c.line(20 * mm, h - 29 * mm, w - 20 * mm, h - 29 * mm)
        # marca de agua
        c.translate(w / 2, h / 2); c.rotate(38)
        c.setFillColor(colors.HexColor("#C0392B")); c.setFillAlpha(0.10)
        c.setFont("Helvetica-Bold", 30); c.drawCentredString(0, 0, AVISO_SIMULADO_AUTORIDAD)
        c.restoreState()
        c.setFont("Helvetica-Oblique", 6.4); c.setFillColor(GRIS)
        c.drawString(20 * mm, 8 * mm, f"Documento simulado para una demostración de software. No tiene validez oficial ni proviene de {emisor_pie}.")
        c.drawRightString(w - 20 * mm, 8 * mm, f"Hoja {c.getPageNumber()} de {c._total_paginas}")

    _construir(ruta, flowables, decorar, [], margen_sup=34 * mm)


def documento_simple(ruta, flowables, decorar):
    _construir(ruta, flowables, decorar, [], margen_sup=20 * mm)


def _construir(ruta, flowables, decorar, inicio, margen_sup):
    ruta.parent.mkdir(parents=True, exist_ok=True)

    class Lienzo(LienzoNumerado):
        pass
    Lienzo.decorar = staticmethod(decorar)
    doc = SimpleDocTemplate(str(ruta), pagesize=letter, leftMargin=20 * mm, rightMargin=20 * mm,
                            topMargin=margen_sup, bottomMargin=22 * mm,
                            title=ruta.stem, author="Generador de datos ficticios – Obed Farmacéutica",
                            subject="Documento ficticio para demostración")
    doc.build(inicio + flowables, canvasmaker=Lienzo)


# --------------------------------------------------------------------------------- escaneo
def escanear(ruta, semilla=1, ilegible=False, dpi=110):
    """Convierte un PDF en 'documento escaneado': imagen gris, ligera rotación, ruido y desenfoque."""
    r = random.Random(semilla)
    origen = pymupdf.open(str(ruta))
    paginas = []
    for pagina in origen:
        pix = pagina.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        img = Image.frombytes("L", (pix.width, pix.height), pix.samples)
        img = img.rotate(r.uniform(-1.3, 1.3), resample=Image.BICUBIC, expand=False, fillcolor=246)
        if ilegible:
            img = img.resize((img.width // 3, img.height // 3)).resize((img.width, img.height))
            img = img.filter(ImageFilter.GaussianBlur(2.4))
            img = ImageEnhance.Contrast(img).enhance(0.45)
        else:
            img = img.filter(ImageFilter.GaussianBlur(0.55))
        ruido = Image.frombytes("L", img.size, r.randbytes(img.width * img.height))   # ruido con semilla fija
        img = Image.blend(img, ruido, 0.05 if not ilegible else 0.09)
        img = ImageEnhance.Brightness(img).enhance(0.97)
        img = ImageOps.autocontrast(img, cutoff=1) if not ilegible else img
        # sombra en el borde izquierdo, como en un escáner de cama plana
        borde = Image.linear_gradient("L").rotate(90).resize((max(8, img.width // 45), img.height))
        img.paste(Image.eval(borde, lambda v: 150 + v // 3), (0, 0))
        paginas.append(img.convert("RGB"))
    origen.close()
    fija = time.gmtime(datetime(2026, 10, 6, 12, 0).timestamp())   # fecha fija: PDF idéntico en cada corrida
    paginas[0].save(str(ruta), "PDF", resolution=dpi, save_all=True, append_images=paginas[1:],
                    title=ruta.stem, creationDate=fija, modDate=fija)
