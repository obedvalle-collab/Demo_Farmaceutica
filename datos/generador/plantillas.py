"""Plantillas de cada tipo de documento PDF. Cada función recibe un contexto `x` y escribe x.ruta."""
import math
import random
from datetime import date, timedelta

from reportlab.graphics.barcode import code128
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Paragraph, Spacer, PageBreak, KeepTogether, Table, TableStyle
import hashlib

from config import EMPRESA, AVISO_FICTICIO
from pdf_base import (AZUL, TURQUESA, DORADO, GRIS, GRIS_CLARO, VINO, E, P, tabla, tabla_datos, Dibujo,
                      bloque_firmas, dibujar_logo, dibujar_sello, dibujar_firma, qr_imagen,
                      documento_altamira, documento_autoridad, documento_simple)

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]
MES3 = ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN", "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"]


def huella(*partes, n=32):
    return hashlib.sha256("|".join(map(str, partes)).encode()).hexdigest()[:n]


def fl(d):
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fc(d):
    return d.strftime("%d/%m/%Y")


def prod(x, con_forma=True):
    p = x.producto
    forma = p["forma_farmaceutica"].lower()
    return f"{p['denominacion_generica']} {p['concentracion']}" + (f", {forma}" if con_forma else "")


def lote(x, i=0):
    return f"{x.producto['producto_id'][1:]}{x.fecha.strftime('%y')}{(x.semilla * 7 + i * 13) % 900 + 100:03d}"


def firmantes_std(x, rs_firma=True, extra=None):
    f = [("Elaboró", x.autor["nombre"], x.autor["rol"], fc(x.fecha), True),
         ("Revisó", x.revisor["nombre"], x.revisor["rol"], fc(x.fecha + timedelta(days=2)), True),
         ("Aprobó (Responsable Sanitario)", x.rs["nombre"], f"Responsable Sanitario · Céd. Prof. {x.rs['cedula_profesional']}",
          fc(x.fecha + timedelta(days=3)), rs_firma)]
    return f


def informe(x, titulo, codigo, secciones, firmantes=None, subtitulo=None, area=None, sello=None, datos_extra=()):
    flow = [tabla_datos([("Producto", prod(x)), ("Trámite", f"{x.tramite['tramite_id']} · {x.tramite['homoclave']}"),
                         ("Fecha de emisión", fl(x.fecha)), ("Sección CTD", f"{x.req['seccion_ctd']} – {x.req['nombre']}")]
                        + list(datos_extra)),
            Spacer(1, 6)]
    for i, (t, cuerpo) in enumerate(secciones):
        if sello and i == len(secciones) - 1:   # el sello de calidad va junto al dictamen final
            marca = Dibujo(34 * mm, 25 * mm, lambda c, w, h: dibujar_sello(
                c, w / 2, h / 2, 12 * mm, sello, "ASEGURAMIENTO\nDE CALIDAD", fecha=fc(x.fecha), angulo=-8))
            caja = Table([[cuerpo, marca]], colWidths=[138 * mm, 36 * mm])
            caja.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
            flow.append(KeepTogether([P(t, "h1"), caja]))
        else:   # el título nunca queda solo al pie de la página
            flow.append(KeepTogether([P(t, "h1")] + cuerpo[:1]))
            flow.extend(cuerpo[1:])
    if firmantes is not False:
        flow.append(KeepTogether([P("Aprobaciones", "h1"),
                                  bloque_firmas(firmantes or firmantes_std(x), semilla=x.semilla)]))
    documento_altamira(x.ruta, titulo, codigo, flow, subtitulo=subtitulo, area=area or x.req["area_responsable"])


# ============================================================================ administrativos
def solicitud(x):
    prorroga = x.extra.get("prorroga")
    p = x.producto
    titulo = "SOLICITUD DE PRÓRROGA DE REGISTRO SANITARIO" if prorroga else "SOLICITUD DE REGISTRO SANITARIO DE MEDICAMENTO"

    def decorar(c):
        w, h = letter
        c.setFillColor(GRIS_CLARO); c.rect(20 * mm, h - 30 * mm, w - 40 * mm, 14 * mm, stroke=0, fill=1)
        c.setFillColor(AZUL); c.setFont("Helvetica-Bold", 11)
        c.drawString(24 * mm, h - 21 * mm, titulo)
        c.setFont("Helvetica", 7.5); c.setFillColor(GRIS)
        c.drawString(24 * mm, h - 26 * mm, f"Formato de solicitud (reproducción simulada) · Homoclave {x.tramite['homoclave']}")
        c.drawRightString(w - 24 * mm, h - 21 * mm, f"Página {c.getPageNumber()} de {c._total_paginas}")
        c.setFont("Helvetica-Oblique", 6.2); c.drawString(20 * mm, 8 * mm, AVISO_FICTICIO)

    fab, pais = x.fabricante
    flow = [Spacer(1, 16 * mm),
            P("1. Datos del solicitante", "h1"),
            tabla_datos([("Razón social", EMPRESA["razon_social"]), ("RFC", EMPRESA["rfc"]),
                         ("Domicilio", EMPRESA["domicilio_planta"]), ("Licencia sanitaria", EMPRESA["licencia_sanitaria"]),
                         ("Representante legal", x.rl["nombre"]),
                         ("Responsable sanitario", f"{x.rs['titulo']} {x.rs['nombre']} (Céd. Prof. {x.rs['cedula_profesional']})"),
                         ("Correo para notificaciones", f"regulatorio@{EMPRESA['dominio_correo']}")]),
            P("2. Datos del medicamento", "h1"),
            tabla_datos([("Denominación genérica", p["denominacion_generica"]),
                         ("Denominación distintiva", p["denominacion_distintiva"] or "No aplica (genérico)"),
                         ("Forma farmacéutica", p["forma_farmaceutica"]), ("Concentración", p["concentracion"]),
                         ("Presentaciones", p["presentacion"]), ("Vía de administración", x.perfil["via"]),
                         ("Fracción (art. 226 LGS)", "IV – requiere receta médica"),
                         ("Tipo", p["tipo_producto"]), ("Fabricante del fármaco", f"{fab} ({pais})"),
                         ("Fabricante del medicamento", EMPRESA["razon_social"])]),
            ]
    if prorroga:
        flow += [P("3. Registro sanitario a prorrogar", "h1"),
                 tabla_datos([("Número de registro", f"{p['registro_sanitario']} IV"),
                              ("Fecha de otorgamiento", fl(date.fromisoformat(p["fecha_registro"]))),
                              ("Vigencia actual", "5 años"), ("Prórroga solicitada", "10 años (LGS art. 376, reforma DOF 15/01/2026)")])]
    flow += [P("Declaración", "h1"),
             P("Bajo protesta de decir verdad, manifiesto que la información y documentación que se acompaña a la "
               "presente solicitud es verídica y corresponde al medicamento descrito, y que conozco las sanciones "
               "aplicables a quienes se conducen con falsedad ante una autoridad distinta de la judicial."),
             bloque_firmas([("Representante legal", x.rl["nombre"], EMPRESA["razon_social"], fc(x.fecha), True),
                            ("Responsable sanitario", x.rs["nombre"], f"Céd. Prof. {x.rs['cedula_profesional']}", fc(x.fecha), True)],
                           semilla=x.semilla)]
    documento_simple(x.ruta, flow, decorar)


def pago_derechos(x):
    importe = {"REG_GEN": "$ 89,421.00", "REG_BIO": "$ 141,780.00", "PRORROGA": "$ 31,964.00"}.get(x.tramite_tipo, "$ 22,315.00")

    def decorar(c):
        w, h = letter
        c.setFillColor(colors.HexColor("#0E4D3A")); c.rect(20 * mm, h - 28 * mm, w - 40 * mm, 12 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawString(25 * mm, h - 24 * mm, "BANCO DEL ALTIPLANO")
        c.setFont("Helvetica", 7.5); c.drawRightString(w - 25 * mm, h - 24 * mm, "Comprobante de pago de contribuciones federales")
        c.setFont("Helvetica-Oblique", 6.2); c.setFillColor(GRIS)
        c.drawString(20 * mm, 8 * mm, "Banco y comprobante ficticios. " + AVISO_FICTICIO)

    ref = f"{x.semilla * 7919 % 10**12:012d}"
    flow = [Spacer(1, 14 * mm), P("COMPROBANTE DE PAGO DE DERECHOS", "titulo"),
            P("Pago de derechos por servicios de la Secretaría de Salud", "subtitulo"),
            tabla_datos([("Contribuyente", EMPRESA["razon_social"]), ("RFC", EMPRESA["rfc"]),
                         ("Dependencia", "Secretaría de Salud / COFEPRIS"),
                         ("Concepto", f"Derechos por estudio y, en su caso, expedición – {x.tramite['tipo_tramite'][:70]}"),
                         ("Fundamento", "Ley Federal de Derechos, art. 195-A"),
                         ("Clave de referencia", f"{ref[:4]} {ref[4:8]} {ref[8:]}"), ("Importe", importe),
                         ("Fecha y hora de pago", f"{fc(x.fecha)} 11:{x.semilla % 60:02d}:14"),
                         ("Medio de presentación", "Banca electrónica"),
                         ("Número de operación", f"{x.semilla * 104729 % 10**10:010d}"),
                         ("Llave de pago", f"{x.semilla * 15485863 % 16**10:010X}")]),
            Spacer(1, 10),
            P("Sello digital simulado:", "nota"),
            P(f"||{EMPRESA['rfc']}|{ref}|{importe}|{fc(x.fecha)}|SIMULADO|{x.semilla * 2654435761 % 16**24:024X}||", "nota")]
    documento_simple(x.ruta, flow, decorar)


def licencia_sanitaria(x):
    flow = [P("LICENCIA SANITARIA", "titulo"), P("Fábrica o laboratorio de medicamentos alopáticos", "subtitulo"),
            tabla_datos([("Número de licencia", EMPRESA["licencia_sanitaria"]), ("Razón social", EMPRESA["razon_social"]),
                         ("Domicilio del establecimiento", EMPRESA["domicilio_planta"]),
                         ("Giro", "Fábrica o laboratorio de medicamentos o productos biológicos para uso humano"),
                         ("Líneas autorizadas", "Sólidos orales no estériles (tabletas, cápsulas); acondicionamiento de inyectables"),
                         ("Responsable sanitario", f"{x.rs['titulo']} {x.rs['nombre']}"),
                         ("Fecha de expedición", fl(date(2019, 11, 4))), ("Vigencia", "Indefinida")]),
            Spacer(1, 18),
            P("Se expide la presente licencia con fundamento en el artículo 198 de la Ley General de Salud.", "oficio"),
            Spacer(1, 30), qr_imagen(f"SIMULADO|LICENCIA|{EMPRESA['licencia_sanitaria']}", 24 * mm)]
    documento_autoridad(x.ruta, flow, "Comisión de Autorización Sanitaria",
                        [f"Licencia: {EMPRESA['licencia_sanitaria']}", "Toluca, Estado de México"])


def carta_poder(x):
    firma_otorgante = x.extra.get("firma_otorgante", True)
    otorgante = x.usuarios_rol("Director(a) de Asuntos Regulatorios")

    def decorar(c):
        w, h = letter
        c.setFont("Times-Bold", 12); c.setFillColor(colors.black)
        c.drawCentredString(w / 2, h - 18 * mm, "NOTARÍA PÚBLICA NÚMERO DIECISIETE (FICTICIA)")
        c.setFont("Times-Roman", 9); c.drawCentredString(w / 2, h - 23 * mm, "Toluca de Lerdo, Estado de México")
        c.setFont("Times-Italic", 6.4); c.setFillColor(GRIS); c.drawString(20 * mm, 8 * mm, AVISO_FICTICIO)

    texto = (f"En la ciudad de Toluca de Lerdo, Estado de México, a {fl(x.fecha - timedelta(days=210))}, ante mí, "
             f"<b>Lic. Ernesto Valdivia Robles</b>, Notario Público número diecisiete (ficticio), compareció "
             f"<b>{otorgante['nombre']}</b>, en su carácter de apoderado general de <b>{EMPRESA['razon_social']}</b>, "
             f"quien otorga a favor de <b>{x.rl['nombre']}</b> PODER GENERAL PARA PLEITOS Y COBRANZAS Y ACTOS DE "
             f"ADMINISTRACIÓN, limitado a la representación de la sociedad ante la Secretaría de Salud y la Comisión "
             f"Federal para la Protección contra Riesgos Sanitarios, para presentar solicitudes, recibir notificaciones, "
             f"desahogar prevenciones y requerimientos, y realizar todos los trámites relativos a registros sanitarios, "
             f"sus modificaciones y prórrogas.")
    flow = [Spacer(1, 10 * mm), P(f"INSTRUMENTO NÚMERO {45000 + x.semilla % 900:,}", "oficio_b"),
            P("VOLUMEN ORDINARIO MIL CIENTO DOS", "oficio_b"), P(texto, "oficio"),
            P("El compareciente declara que su representada se encuentra legalmente constituida, que sus facultades no "
              "le han sido revocadas ni limitadas, y que el apoderado acepta el cargo conferido.", "oficio"),
            P("LEÍDO que fue el presente instrumento, lo ratifican y firman de conformidad.", "oficio"),
            bloque_firmas([("Otorgante", otorgante["nombre"], f"Apoderado de {EMPRESA['nombre_corto']}", fc(x.fecha - timedelta(days=210)), firma_otorgante),
                           ("Apoderado", x.rl["nombre"], "Representante legal", fc(x.fecha - timedelta(days=210)), True),
                           ("Notario", "Lic. Ernesto Valdivia Robles", "Notario Público No. 17 (ficticio)", fc(x.fecha - timedelta(days=210)), True)],
                          semilla=x.semilla),
            Dibujo(174 * mm, 34 * mm, lambda c, w, h: dibujar_sello(c, w - 30 * mm, h / 2, 15 * mm, "NOTARÍA 17 • TOLUCA • FICTICIA",
                                                                     "LIC. E.\nVALDIVIA", color=colors.HexColor("#333333"), angulo=12))]
    documento_simple(x.ruta, flow, decorar)


# ============================================================================ etiquetas
def _parrafo(c, texto, x0, y_top, ancho, tam=7.2, negrita=False, centro=False, color=colors.black):
    st = ParagraphStyle("e", fontName="Helvetica-Bold" if negrita else "Helvetica", fontSize=tam,
                        leading=tam * 1.22, alignment=1 if centro else 0, textColor=color)
    p = Paragraph(texto, st)
    _, h = p.wrap(ancho, 500)
    p.drawOn(c, x0, y_top - h)
    return y_top - h


def etiqueta_secundaria(x):
    omitir = set(x.extra.get("omitir", []))
    p, pf = x.producto, x.perfil
    bio = p["tipo_producto"] == "Biocomparable"
    x.ruta.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(x.ruta), pagesize=landscape(letter))
    c.setTitle(x.ruta.stem); c.setAuthor("Generador de datos ficticios – Obed Farmacéutica")
    W, H = landscape(letter)
    # barra de título del arte
    c.setFillColor(AZUL); c.rect(0, H - 16 * mm, W, 16 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11)
    c.drawString(12 * mm, H - 10 * mm, f"PROYECTO DE ETIQUETA · ENVASE SECUNDARIO · {prod(x, False).upper()}")
    c.setFont("Helvetica", 7.5)
    c.drawRightString(W - 12 * mm, H - 10 * mm, f"Arte {x.tramite['tramite_id']}-ES · Versión 1 · {fc(x.fecha)} · Escala 1:1 aprox.")
    # dieline
    x0, y0, alto = 18 * mm, 40 * mm, 108 * mm
    anchos = [44 * mm, 70 * mm, 44 * mm, 70 * mm]
    nombres = ["LATERAL IZQUIERDA", "CARA PRINCIPAL", "LATERAL DERECHA", "CARA POSTERIOR"]
    xs = [x0]
    for a in anchos:
        xs.append(xs[-1] + a)
    c.setStrokeColor(colors.HexColor("#999999")); c.setDash(3, 2); c.setLineWidth(0.6)
    for i in range(4):
        c.rect(xs[i], y0, anchos[i], alto)
        c.rect(xs[i], y0 + alto, anchos[i], 22 * mm if i % 2 else 14 * mm)
        c.rect(xs[i], y0 - (22 * mm if i % 2 else 14 * mm), anchos[i], 22 * mm if i % 2 else 14 * mm)
    c.rect(xs[4], y0, 9 * mm, alto)   # pestaña de pegado
    c.setDash()
    c.setFont("Helvetica", 5.5); c.setFillColor(GRIS)
    for i, n in enumerate(nombres):
        c.drawCentredString(xs[i] + anchos[i] / 2, y0 - (22 * mm if i % 2 else 14 * mm) - 4 * mm, n)
    c.drawCentredString(xs[4] + 4.5 * mm, y0 + alto / 2, "PEGADO")
    # cara principal
    cx, cw = xs[1] + 4 * mm, anchos[1] - 8 * mm
    c.setFillColor(TURQUESA); c.rect(xs[1], y0 + alto - 9 * mm, anchos[1], 9 * mm, stroke=0, fill=1)
    c.setFillColor(colors.HexColor("#E3F1F1")); c.rect(xs[1], y0, anchos[1], 17 * mm, stroke=0, fill=1)
    c.setFillColor(TURQUESA); c.rect(xs[1], y0 + 17 * mm, anchos[1], 0.8 * mm, stroke=0, fill=1)
    dibujar_logo(c, xs[1] + 4 * mm, y0 + 6 * mm, 0.8)
    c.setFont("Helvetica-Bold", 6.2); c.setFillColor(AZUL)
    c.drawRightString(xs[1] + anchos[1] - 4 * mm, y0 + 4 * mm, "Hecho en México")
    # silueta del contenido (tabletas o jeringa) como apoyo visual
    c.saveState(); c.setFillColor(colors.HexColor("#D5E4EE")); c.setStrokeColor(colors.HexColor("#9FB6C8"))
    if pf["unidad"] == "jeringa prellenada":
        c.roundRect(xs[1] + 12 * mm, y0 + 30 * mm, 40 * mm, 5 * mm, 2, stroke=1, fill=1)
        c.rect(xs[1] + 52 * mm, y0 + 31.8 * mm, 7 * mm, 1.4 * mm, stroke=1, fill=1)
    else:
        for k in range(3):
            c.ellipse(xs[1] + 16 * mm + k * 13 * mm, y0 + 28 * mm, xs[1] + 26 * mm + k * 13 * mm, y0 + 36 * mm, stroke=1, fill=1)
    c.restoreState()
    y = y0 + alto - 14 * mm
    if p["denominacion_distintiva"]:
        y = _parrafo(c, f"<b>{p['denominacion_distintiva']}</b>", cx, y, cw, 13, True, True, AZUL) - 2
    y = _parrafo(c, p["denominacion_generica"].upper(), cx, y, cw, 15 if not p["denominacion_distintiva"] else 10, True, True, AZUL) - 3
    y = _parrafo(c, p["forma_farmaceutica"], cx, y, cw, 9, False, True) - 1
    y = _parrafo(c, p["concentracion"], cx, y, cw, 11, True, True) - 5
    y = _parrafo(c, p["presentacion"], cx, y, cw, 7.5, False, True) - 3
    y = _parrafo(c, f"Vía de administración: {pf['via']}", cx, y, cw, 7.5, False, True) - 3
    if bio and "mbb" not in omitir:
        c.setFillColor(DORADO); c.roundRect(xs[1] + anchos[1] - 24 * mm, y0 + 20 * mm, 20 * mm, 9 * mm, 2, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 12)
        c.drawCentredString(xs[1] + anchos[1] - 14 * mm, y0 + 23 * mm, "M.B.B.")
    # lateral izquierda: fórmula, dosis
    lx, lw = xs[0] + 3 * mm, anchos[0] - 6 * mm
    y = y0 + alto - 4 * mm
    y = _parrafo(c, "<b>Fórmula:</b>", lx, y, lw, 7)
    unidad = "La jeringa prellenada contiene" if pf["unidad"] == "jeringa prellenada" else f"Cada {pf['unidad']} contiene"
    exc = "Vehículo cbp 0.4 mL" if bio else f"Excipiente cbp 1 {pf['unidad']}"
    y = _parrafo(c, f"{unidad}:<br/>{pf['sal']} equivalente a {pf['equivalente'].split(' de ')[0]} de {p['denominacion_generica'].split(' ')[0].lower()}<br/>{exc}", lx, y, lw, 6.6) - 4
    y = _parrafo(c, "<b>Dosis:</b> la que el médico señale.", lx, y, lw, 6.6) - 3
    y = _parrafo(c, f"<b>Vía de administración:</b> {pf['via']}. Léase instructivo anexo.", lx, y, lw, 6.6) - 3
    y = _parrafo(c, f"<b>Conservación:</b> {pf['conservacion']}", lx, y, lw, 6.6) - 3
    # lateral derecha: leyendas
    rx, rw = xs[2] + 3 * mm, anchos[2] - 6 * mm
    y = y0 + alto - 4 * mm
    y = _parrafo(c, "<b>Leyendas:</b>", rx, y, rw, 7) - 1
    leyendas = []
    if "receta" not in omitir:
        leyendas.append("Su venta requiere receta médica.")
    leyendas.append("No se deje al alcance de los niños.")
    if "farmacovigilancia" not in omitir:
        leyendas.append("Reporte las sospechas de reacción adversa al correo: farmacovigilancia@cofepris.gob.mx")
    if p["cronico"] and "venta_fraccionada" not in omitir:
        leyendas.append("Prohibida la venta fraccionada del producto.")
    leyendas.append("No se use en el embarazo ni en la lactancia." if p["producto_id"] in ("P08", "P03") else
                    "En caso de embarazo o lactancia, consulte a su médico.")
    for l in leyendas:
        y = _parrafo(c, f"• {l}", rx, y, rw, 6.6) - 2
    y = _parrafo(c, "Precio máximo al público: $ ________", rx, y - 4, rw, 6.6)
    # cara posterior: fabricante, registro, lote, código
    px_, pw = xs[3] + 4 * mm, anchos[3] - 8 * mm
    y = y0 + alto - 5 * mm
    domicilio = EMPRESA["domicilio_anterior"] if x.extra.get("domicilio_anterior") else EMPRESA["domicilio_planta"]
    if bio:
        fab, pais = x.fabricante
        y = _parrafo(c, f"<b>Denominación Común Internacional:</b> {p['denominacion_generica']}", px_, y, pw, 6.6) - 2
        y = _parrafo(c, f"<b>Fabricante del biofármaco:</b> {fab}, {pais}.", px_, y, pw, 6.6) - 2
        y = _parrafo(c, f"<b>Hecho en México por / Acondicionado por:</b> {EMPRESA['razon_social']}<br/>{domicilio}", px_, y, pw, 6.6) - 4
    else:
        y = _parrafo(c, f"<b>Hecho en México por:</b><br/>{EMPRESA['razon_social']}<br/>{domicilio}", px_, y, pw, 6.6) - 4
    reg = f"Reg. No. {p['registro_sanitario']} IV" if p["registro_sanitario"] else "Reg. No. _______ SSA IV"
    y = _parrafo(c, f"<b>{reg}</b>", px_, y, pw, 7.5) - 4
    c.setStrokeColor(colors.black); c.setLineWidth(0.5)
    c.rect(px_, y - 13 * mm, pw * 0.55, 13 * mm)
    c.setFont("Helvetica", 6.6); c.setFillColor(colors.black)
    c.drawString(px_ + 2 * mm, y - 5 * mm, "Lote: ____________")
    c.drawString(px_ + 2 * mm, y - 10 * mm, "Cad.: ___ / __ (MES/AA)")
    bc = code128.Code128(f"20{x.semilla:011d}"[:13], barHeight=10 * mm, barWidth=0.32)
    bc.drawOn(c, px_ + pw * 0.58, y - 13 * mm)
    c.setFont("Helvetica", 5); c.drawString(px_ + pw * 0.6, y - 16 * mm, f"20{x.semilla:011d}"[:13] + " (código interno)")
    # bloque de control inferior
    c.setFillColor(GRIS_CLARO); c.rect(12 * mm, 6 * mm, W - 24 * mm, 13 * mm, stroke=0, fill=1)
    c.setFillColor(GRIS); c.setFont("Helvetica", 6.8)
    c.drawString(15 * mm, 14 * mm, f"Dimensiones: 70 × 44 × 108 mm · Tintas: Pantone 2955 C, 7716 C, 7563 C, negro · Sustrato: cartulina sulfatada 14 pts · Elaboró: {x.autor['nombre']}")
    c.setFont("Helvetica-Oblique", 6.2)
    c.drawString(15 * mm, 9 * mm, AVISO_FICTICIO + " Arte ficticio sujeto a autorización.")
    c.showPage(); c.save()


def etiqueta_primaria(x):
    p, pf = x.producto, x.perfil
    x.ruta.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(x.ruta), pagesize=landscape(letter))
    c.setTitle(x.ruta.stem)
    W, H = landscape(letter)
    c.setFillColor(AZUL); c.rect(0, H - 16 * mm, W, 16 * mm, stroke=0, fill=1)
    c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11)
    c.drawString(12 * mm, H - 10 * mm, f"PROYECTO DE ETIQUETA · ENVASE PRIMARIO · {prod(x, False).upper()}")
    c.setFont("Helvetica", 7.5); c.drawRightString(W - 12 * mm, H - 10 * mm, f"Arte {x.tramite['tramite_id']}-EP · Versión 1 · {fc(x.fecha)}")
    reg = f"Reg. {p['registro_sanitario']} IV" if p["registro_sanitario"] else "Reg. ______ SSA IV"
    if pf["unidad"] == "jeringa prellenada":
        x0, y0 = 40 * mm, 80 * mm
        c.setStrokeColor(colors.HexColor("#888888")); c.setDash(3, 2); c.rect(x0, y0, 120 * mm, 32 * mm); c.setDash()
        y = y0 + 29 * mm
        for t, tam, b in [(p["denominacion_generica"].upper(), 10, True), (f"{p['concentracion']} · Solución inyectable", 7.5, False),
                          ("SC · Léase instructivo", 7, False), (reg, 7, True), ("Lote: ________   Cad.: ___/__", 7, False),
                          ("M.B.B. · " + EMPRESA["nombre_corto"], 7, True)]:
            y = _parrafo(c, t, x0 + 4 * mm, y, 112 * mm, tam, b) - 1
        c.setFont("Helvetica", 6.5); c.setFillColor(GRIS)
        c.drawString(x0, y0 - 6 * mm, "Etiqueta envolvente para jeringa prellenada de 1 mL (dimensiones 120 × 32 mm)")
    else:
        x0, y0, cw, ch = 30 * mm, 50 * mm, 46 * mm, 26 * mm
        c.setFillColor(colors.HexColor("#D9DEE3")); c.roundRect(x0 - 4 * mm, y0 - 4 * mm, 4 * cw + 8 * mm, 4 * ch + 8 * mm, 6, stroke=0, fill=1)
        for i in range(4):
            for j in range(4):
                bx, by = x0 + i * cw, y0 + j * ch
                c.setStrokeColor(colors.HexColor("#AAB4BE")); c.rect(bx, by, cw, ch)
                c.setFillColor(AZUL); c.setFont("Helvetica-Bold", 6.6)
                c.drawCentredString(bx + cw / 2, by + ch - 6 * mm, p["denominacion_generica"].upper())
                c.setFillColor(colors.black); c.setFont("Helvetica", 5.6)
                c.drawCentredString(bx + cw / 2, by + ch - 10 * mm, f"{p['concentracion']} · Tabletas")
                c.drawCentredString(bx + cw / 2, by + ch - 14 * mm, reg)
                c.drawCentredString(bx + cw / 2, by + ch - 18 * mm, EMPRESA["nombre_corto"])
                c.drawCentredString(bx + cw / 2, by + 3 * mm, "Lote ______  Cad. ___/__")
        c.setFont("Helvetica", 6.5); c.setFillColor(GRIS)
        c.drawString(x0, y0 - 9 * mm, f"Impresión continua sobre foil de aluminio para {pf['empaque'].lower()}. Lote y caducidad grabados en línea de acondicionamiento.")
    c.setFillColor(GRIS_CLARO); c.rect(12 * mm, 6 * mm, W - 24 * mm, 9 * mm, stroke=0, fill=1)
    c.setFillColor(GRIS); c.setFont("Helvetica-Oblique", 6.2); c.drawString(15 * mm, 9.5 * mm, AVISO_FICTICIO)
    c.showPage(); c.save()


# ============================================================================ información para prescribir
def _ipp(x, amplia):
    p, pf = x.producto, x.perfil
    secciones = [
        ("1. Denominación distintiva", [P(p["denominacion_distintiva"] or "No aplica (medicamento genérico).")]),
        ("2. Denominación genérica", [P(p["denominacion_generica"])]),
        ("3. Forma farmacéutica y formulación", [P(f"{p['forma_farmaceutica']}. {('La jeringa prellenada' if pf['unidad']=='jeringa prellenada' else 'Cada ' + pf['unidad'])} contiene: {pf['sal']} equivalente a {pf['equivalente']}. Excipiente cbp."),]),
        ("4. Indicaciones terapéuticas", [P(pf["indicacion"])]),
    ]
    if amplia:
        secciones += [
            ("5. Farmacocinética y farmacodinamia", [P(f"Clase terapéutica: {pf['clase']}. Tiempo al pico de concentración: {pf['pk']['tmax']}. "
                                                      f"Vida media de eliminación aproximada: {pf['pk']['t12']}. La información farmacocinética "
                                                      "corresponde a la del medicamento de referencia y a la obtenida en el estudio de "
                                                      "intercambiabilidad del expediente.")]),
            ("6. Contraindicaciones", [P(pf["contraindicaciones"])]),
            ("7. Precauciones generales", [P("Vigilar la función renal y hepática antes y durante el tratamiento. Suspender ante signos de "
                                             "reacción de hipersensibilidad grave y valorar alternativas terapéuticas.")]),
            ("8. Restricciones de uso durante el embarazo y la lactancia", [P("No se recomienda su uso durante el embarazo ni la lactancia, salvo que el beneficio potencial justifique el riesgo, a juicio del médico.")]),
            ("9. Reacciones secundarias y adversas", [P(pf["adversas"])]),
            ("10. Interacciones medicamentosas", [P("Pueden presentarse interacciones con medicamentos que modifiquen su metabolismo o su eliminación renal. Consultar la información del medicamento de referencia.")]),
            ("11. Dosis y vía de administración", [P(f"{pf['dosis_texto']} Vía de administración: {pf['via'].lower()}.")]),
            ("12. Manifestaciones y manejo de la sobredosificación", [P("Instaurar medidas generales de soporte y vigilancia clínica. No se conoce antídoto específico.")]),
            ("13. Presentaciones", [P(p["presentacion"])]),
            ("14. Recomendaciones de almacenamiento", [P(pf["conservacion"])]),
            ("15. Leyendas de protección", [P("Su venta requiere receta médica. No se deje al alcance de los niños. Reporte las sospechas de reacción adversa al correo: farmacovigilancia@cofepris.gob.mx")]),
            ("16. Nombre y domicilio del laboratorio", [P(f"{EMPRESA['razon_social']}. {EMPRESA['domicilio_planta']}.")]),
        ]
    else:
        secciones += [("5. Contraindicaciones", [P(pf["contraindicaciones"])]),
                      ("6. Reacciones adversas", [P(pf["adversas"])]),
                      ("7. Dosis y vía de administración", [P(pf["dosis_texto"])]),
                      ("8. Presentación y leyendas", [P(f"{p['presentacion']}. Su venta requiere receta médica. No se deje al alcance de los niños.")])]
    informe(x, "INFORMACIÓN PARA PRESCRIBIR " + ("AMPLIA" if amplia else "REDUCIDA"), "RA-IPP-" + ("A" if amplia else "R"),
            secciones, firmantes=[("Elaboró", x.autor["nombre"], x.autor["rol"], fc(x.fecha), True),
                                  ("Revisión médica", x.usuarios_rol("Gerente Médico")["nombre"], "Gerente Médico", fc(x.fecha), True)])


def ipp_amplia(x):
    _ipp(x, True)


def ipp_reducida(x):
    _ipp(x, False)


# ============================================================================ farmacovigilancia
def pmr(x):
    p, pf = x.producto, x.perfil
    secciones = [
        ("1. Descripción del producto", [tabla_datos([("Denominación distintiva", p["denominacion_distintiva"] or "No aplica"),
                                                       ("Denominación genérica", p["denominacion_generica"]),
                                                       ("Forma farmacéutica y formulación", f"{p['forma_farmaceutica']}, {p['concentracion']}"),
                                                       ("Indicaciones terapéuticas", pf["indicacion"]),
                                                       ("Categoría de PMR", "Categoría I (NOM-220-SSA1-2016, 8.4.3.1)")])]),
        ("2. Especificaciones de seguridad", [
            P("<b>2.1 Poblaciones sin información de seguridad:</b> embarazo y lactancia, población pediátrica, insuficiencia hepática grave."),
            P("<b>2.2 Información post-comercialización disponible:</b> se considera la información pública del medicamento de referencia."),
            P("<b>2.3 Usos fuera de indicación, sobredosis y errores de medicación:</b> sin señales identificadas."),
            tabla([["Riesgo importante", "Tipo", "Fuente"],
                   [pf["adversas"].split(",")[0].strip().capitalize(), "Identificado", "Información de referencia"],
                   ["Reacciones de hipersensibilidad", "Potencial", "Clase terapéutica"],
                   ["Uso en embarazo y lactancia", "Información faltante", "Ausencia de estudios"]], [70 * mm, 45 * mm, 59 * mm]),
            P("<b>2.4 Alertas internacionales:</b> sin alertas vigentes a la fecha de elaboración.")]),
        ("3. Plan de farmacovigilancia", [P("Actividades de rutina: recepción, evaluación y notificación de sospechas de reacciones adversas "
                                            "al Centro Nacional de Farmacovigilancia en los plazos de la NOM-220-SSA1-2016; elaboración de "
                                            "informes periódicos de seguridad; seguimiento de literatura científica.")]),
    ]
    if not x.extra.get("omitir_minimizacion"):
        secciones.append(("4. Plan de minimización de riesgos", [P("Actividades de rutina: información para prescribir y etiquetado con "
                                                                      "leyendas de seguridad; capacitación a la fuerza de ventas sobre el "
                                                                      "reporte de eventos adversos.")]))
    secciones.append(("Anexos", [P("Anexo A. Procedimiento de la Unidad de Farmacovigilancia (PNO-FV-001). Anexo B. Formato de reporte de sospecha de RAM.")]))
    informe(x, "PLAN DE MANEJO DE RIESGOS", "FV-PMR-" + x.producto["producto_id"], secciones,
            firmantes=[("Elaboró", x.usuarios_rol("Responsable de Farmacovigilancia")["nombre"], "Responsable de Farmacovigilancia", fc(x.fecha), True),
                       ("Aprobó", x.rs["nombre"], "Responsable Sanitario", fc(x.fecha), True)], area="Farmacovigilancia")


def informe_seguridad(x):
    filas = [["Periodo", "Unidades vendidas", "Reportes recibidos", "Graves", "Señales"]]
    r = random.Random(x.semilla)
    for a in range(2021, 2026):
        filas.append([str(a), f"{r.randint(400, 900) * 1000:,}", str(r.randint(3, 18)), str(r.randint(0, 2)), "Ninguna"])
    informe(x, "INFORME PERIÓDICO DE SEGURIDAD", "FV-IPS-" + x.producto["producto_id"],
            [("1. Resumen", [P("Durante el periodo evaluado no se identificaron señales nuevas de seguridad y el balance beneficio-riesgo permanece favorable.")]),
             ("2. Exposición y notificaciones", [tabla(filas, [30 * mm, 38 * mm, 38 * mm, 30 * mm, 38 * mm], alinear_centro=(1, 2, 3))]),
             ("3. Conclusión", [P("Se mantienen las actividades de rutina del plan de farmacovigilancia.")])],
            firmantes=[("Elaboró", x.usuarios_rol("Responsable de Farmacovigilancia")["nombre"], "Responsable de Farmacovigilancia", fc(x.fecha), True)],
            area="Farmacovigilancia")


# ============================================================================ certificados de autoridad (simulados)
def _certificado_bpf(x, farmaco):
    fab, pais = x.fabricante if farmaco else (EMPRESA["razon_social"], "México")
    emision = x.extra.get("fecha_emision") or date(2025, 3, 3)
    folio = f"CBPF-{'F' if farmaco else 'M'}-{emision.year}-{x.semilla % 9000 + 1000}"
    flow = [P("CERTIFICADO DE BUENAS PRÁCTICAS DE FABRICACIÓN", "titulo"),
            P("de fármacos" if farmaco else "de medicamentos", "subtitulo"),
            P(f"La Comisión Federal para la Protección contra Riesgos Sanitarios, con fundamento en el artículo 167, fracción VI, "
              f"del Reglamento de Insumos para la Salud, y con base en la verificación sanitaria practicada, hace constar que el "
              f"establecimiento que se indica cumple con las Buenas Prácticas de Fabricación establecidas en la "
              f"{'NOM-164-SSA1-2015' if farmaco else 'NOM-059-SSA1-2015'}.", "oficio"),
            tabla_datos([("Folio", folio), ("Establecimiento", fab), ("País", pais),
                         ("Domicilio", "Plot 42, Phase II, GIDC Industrial Estate (ficticio)" if pais == "India" else
                          ("Industriestraße 17, Mannheim (ficticio)" if pais == "Alemania" else
                           ("No. 88 Binhai Road, Taizhou (ficticio)" if pais == "China" else EMPRESA["domicilio_planta"]))),
                         ("Producto(s)", x.producto["denominacion_generica"] if farmaco else "Sólidos orales no estériles; acondicionamiento de inyectables"),
                         ("Fecha de verificación", fl(emision - timedelta(days=41))), ("Fecha de emisión", fl(emision))]),
            Spacer(1, 14),
            P("La vigencia del presente certificado se sujeta a lo dispuesto en las disposiciones jurídicas aplicables.", "oficio"),
            Spacer(1, 18), qr_imagen(f"SIMULADO|{folio}|{emision.isoformat()}", 24 * mm),
            P(f"Cadena de verificación simulada: {huella(folio, emision)}", "nota")]
    documento_autoridad(x.ruta, flow, "Comisión de Operación Sanitaria", [f"Folio: {folio}", f"Ciudad de México, {fc(emision)}"])


def certificado_bpf_farmaco(x):
    _certificado_bpf(x, True)


def certificado_bpf_medicamento(x):
    _certificado_bpf(x, False)


def documento_impi(x):
    folio = f"LIC-{x.fecha.year}-{x.semilla % 9000 + 1000}"
    flow = [P("CONSTANCIA DE INSCRIPCIÓN DE LICENCIA DE EXPLOTACIÓN", "titulo"),
            P("Patente relacionada con el principio activo (datos ficticios)", "subtitulo"),
            tabla_datos([("Folio de la constancia", folio), ("Patente", "MX 000000 B (ficticia)"),
                         ("Titular de la patente", "Innovaciones Terapéuticas del Norte, S.A. (ficticia)"),
                         ("Licenciatario", EMPRESA["razon_social"]),
                         ("Objeto", f"Licencia no exclusiva para fabricar y comercializar {prod(x, False)} en México"),
                         ("Fecha de inscripción", fl(x.fecha)), ("Vigencia de la licencia", "Hasta el vencimiento de la patente")]),
            Spacer(1, 12),
            P("Se presenta en cumplimiento del artículo 167, fracción I Bis, del Reglamento de Insumos para la Salud "
              "(reforma DOF 24/04/2026).", "oficio"),
            Spacer(1, 20), qr_imagen(f"SIMULADO|{folio}", 22 * mm)]
    documento_autoridad(x.ruta, flow, "Dirección Divisional de Patentes (simulada)", [f"Folio: {folio}", fc(x.fecha)],
                        institucion=("INSTITUTO MEXICANO DE LA PROPIEDAD INDUSTRIAL", "Entorno simulado de demostración"),
                        emisor_pie="el IMPI")


def registro_sanitario(x):
    p = x.producto
    otorg = date.fromisoformat(p["fecha_registro"])
    flow = [P("REGISTRO SANITARIO DE MEDICAMENTO", "titulo"),
            tabla_datos([("Número de registro", f"{p['registro_sanitario']} IV"), ("Titular", EMPRESA["razon_social"]),
                         ("Domicilio del titular y fabricante", EMPRESA["domicilio_planta"]),
                         ("Denominación genérica", p["denominacion_generica"]),
                         ("Denominación distintiva", p["denominacion_distintiva"] or "—"),
                         ("Forma farmacéutica y concentración", f"{p['forma_farmaceutica']}, {p['concentracion']}"),
                         ("Presentaciones", p["presentacion"]), ("Fecha de otorgamiento", fl(otorg)),
                         ("Vigencia", f"5 años, al {fl(date(otorg.year + 5, otorg.month, otorg.day))}")]),
            Spacer(1, 12),
            P("Se otorga el presente registro con fundamento en los artículos 222 y 376 de la Ley General de Salud y 166 y 167 del Reglamento de Insumos para la Salud.", "oficio"),
            Spacer(1, 20), qr_imagen(f"SIMULADO|REGISTRO|{p['registro_sanitario']}", 24 * mm)]
    documento_autoridad(x.ruta, flow, "Comisión de Autorización Sanitaria", [f"Registro {p['registro_sanitario']}", fc(otorg)])


def autorizacion_tercero(x):
    flow = [P("AUTORIZACIÓN COMO TERCERO AUTORIZADO", "titulo"),
            P("Unidad clínica y analítica para estudios de intercambiabilidad", "subtitulo"),
            tabla_datos([("Tercero autorizado", "Unidad de Farmacología Clínica del Centro, S.C. (ficticia)"),
                         ("Número de autorización", "TA-UFC-031-2024 (ficticio)"),
                         ("Alcance", "Fase clínica y analítica de estudios de bioequivalencia y perfiles de disolución"),
                         ("Fecha de autorización", fl(date(2024, 2, 19))), ("Vigencia", "Dos años a partir de su emisión; renovada el 18/02/2026")]),
            Spacer(1, 10), P("Con fundamento en la NOM-177-SSA1-2013, numeral 4.97, y en las disposiciones aplicables a terceros autorizados.", "oficio"),
            Spacer(1, 20), qr_imagen("SIMULADO|TA-UFC-031-2024", 22 * mm)]
    documento_autoridad(x.ruta, flow, "Comisión de Autorización Sanitaria", ["Oficio TA-UFC-031-2024", "19/02/2024"])


def dictamen_etica(x):
    def decorar(c):
        w, h = letter
        c.setFont("Helvetica-Bold", 11); c.setFillColor(colors.HexColor("#2C5F2D"))
        c.drawString(20 * mm, h - 16 * mm, "CENTRO MÉDICO DEL VALLE DE TOLUCA (ficticio)")
        c.setFont("Helvetica", 8.5); c.setFillColor(GRIS)
        c.drawString(20 * mm, h - 21 * mm, "Comité de Ética en Investigación · Registro CONBIOÉTICA simulado 15-CEI-099-2022")
        c.setFont("Helvetica-Oblique", 6.2); c.drawString(20 * mm, 8 * mm, AVISO_FICTICIO)

    flow = [Spacer(1, 12 * mm), P("DICTAMEN DE APROBACIÓN", "titulo"),
            tabla_datos([("Protocolo", f"ALT-{x.producto['producto_id']}-BC-01: Estudio comparativo de eficacia, seguridad e inmunogenicidad de {x.producto['denominacion_generica']} (Altamira) frente al medicamento de referencia"),
                         ("Patrocinador", EMPRESA["razon_social"]), ("Investigador principal", "Dr. Héctor Salcedo Montiel (ficticio)"),
                         ("Versión del protocolo", "2.0 del 14/01/2025"), ("Sesión", "Ordinaria 03/2025, 11/02/2025"),
                         ("Dictamen", "APROBADO")]),
            Spacer(1, 8),
            P("El Comité revisó el protocolo, el consentimiento informado y el manual del investigador, y determinó que el estudio "
              "cumple con los principios éticos y con la NOM-012-SSA3-2012. La aprobación tiene vigencia de un año.", "oficio"),
            bloque_firmas([("Presidente del Comité", "Dra. Inés Carrillo Benítez (ficticia)", "CEI", "11/02/2025", True),
                           ("Secretario", "Dr. Raúl Esquivel Torres (ficticio)", "CEI", "11/02/2025", True)], semilla=x.semilla)]
    documento_simple(x.ruta, flow, decorar)


# ============================================================================ calidad: certificados de análisis
def coa_lote(x):
    pf = x.perfil
    fuera = x.extra.get("disolucion_fuera")
    lt = lote(x)
    pruebas = [["Prueba", "Especificación", "Resultado", "Dictamen"],
               ["Descripción", "Conforme a la descripción del producto", "Conforme", "Cumple"],
               ["Identidad (HPLC)", "Corresponde a la SRef", "Corresponde", "Cumple"],
               ["Valoración", pf["valoracion"], "99.2%", "Cumple"],
               ["Uniformidad de contenido (VA)", "VA ≤ 15.0", "4.1", "Cumple"],
               ["Disolución", pf["disolucion_q"], "76% (mín. 72%, máx. 81%)" if fuera else "91% (mín. 87%, máx. 95%)", "Cumple"],
               ["Impurezas (individual / totales)", "≤ 0.20% / ≤ 1.0%", "0.06% / 0.21%", "Cumple"],
               ["Límites microbianos (RAM / hongos)", "≤ 1000 UFC/g / ≤ 100 UFC/g", "< 10 / < 10 UFC/g", "Cumple"]]
    datos_lote = [("Lote · tamaño", f"{lt} · {pf['tamano_lote']}"),
                  ("Fabricación · caducidad", f"{fc(x.fecha - timedelta(days=60))} · {MES3[(x.fecha.month - 1)]}/{(x.fecha.year + 2) % 100:02d}"),
                  ("Referencia analítica", "Monografía FEUM vigente y método interno MA-CC-118")]
    secciones = [("Resultados analíticos", [tabla(pruebas, [44 * mm, 52 * mm, 46 * mm, 32 * mm], alinear_centro=(3,))]),
                 ("Dictamen final", [P("<b>APROBADO.</b> El lote cumple con las especificaciones establecidas y se libera para su uso en los fines declarados.")])]
    informe(x, "CERTIFICADO DE ANÁLISIS DE PRODUCTO TERMINADO", f"CC-CA-{lt}", secciones,
            firmantes=[("Analizó", x.usuarios_rol("Analista de Calidad")["nombre"], "Analista de Calidad", fc(x.fecha), True),
                       ("Liberó", x.usuarios_rol("Gerente de Aseguramiento de Calidad")["nombre"], "Gerente de Aseguramiento de Calidad", fc(x.fecha), True)],
            area="Calidad", sello="LABORATORIOS ALTAMIRA • CONTROL DE CALIDAD", datos_extra=datos_lote)


def coa_farmaco(x):
    fab, pais = x.fabricante
    if x.extra.get("fabricante_distinto"):
        fab, pais = "Shreya Organics Pvt. Ltd.", "India"
    pf = x.perfil
    lt = f"API{x.fecha.strftime('%y%m')}{x.semilla % 90 + 10}"

    def decorar(c):
        w, h = letter
        c.setFillColor(colors.HexColor("#4A3C8C")); c.rect(20 * mm, h - 24 * mm, w - 40 * mm, 10 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11); c.drawString(24 * mm, h - 20.5 * mm, fab.upper())
        c.setFont("Helvetica", 7); c.drawRightString(w - 24 * mm, h - 20.5 * mm, f"Quality Control Department · {pais}")
        c.setFont("Helvetica-Oblique", 6.2); c.setFillColor(GRIS); c.drawString(20 * mm, 8 * mm, "Fabricante ficticio. " + AVISO_FICTICIO)

    flow = [Spacer(1, 10 * mm), P("CERTIFICATE OF ANALYSIS / CERTIFICADO DE ANÁLISIS", "titulo"),
            tabla_datos([("Product / Producto", pf["sal"]), ("Batch / Lote", lt), ("Batch size", "250 kg"),
                         ("Mfg. date", fc(x.fecha - timedelta(days=150))), ("Retest date", fc(x.fecha + timedelta(days=580))),
                         ("Manufacturer / Fabricante", f"{fab}, {pais}")]),
            Spacer(1, 6),
            tabla([["Test / Prueba", "Specification", "Result", "Status"],
                   ["Description", "White to off-white powder", "Complies", "Pass"],
                   ["Identification (IR)", "Concordant with reference", "Complies", "Pass"],
                   ["Assay (HPLC, dried basis)", "98.0 – 102.0%", "99.6%", "Pass"],
                   ["Water (KF)", "3.3 – 3.9%", "3.52%", "Pass"],
                   ["Any unspecified impurity", "≤ 0.10%", "0.04%", "Pass"],
                   ["Total impurities", "≤ 0.50%", "0.15%", "Pass"],
                   ["Residual solvents", "ICH Q3C", "Complies", "Pass"]], [52 * mm, 50 * mm, 40 * mm, 32 * mm], alinear_centro=(3,)),
            Spacer(1, 8), P("The batch complies with the specifications. / El lote cumple con las especificaciones."),
            bloque_firmas([("Checked by", "R. Venkataraman (fictitious)", "QC Officer", fc(x.fecha - timedelta(days=140)), True),
                           ("Approved by", "M. Iyer (fictitious)", "Head QA", fc(x.fecha - timedelta(days=139)), True)], semilla=x.semilla)]
    documento_simple(x.ruta, flow, decorar)


# ============================================================================ estabilidad
def _serie(r, base, meses, deriva):
    return [f"{base - deriva * m + r.uniform(-0.4, 0.4):.1f}" for m in meses]


def estabilidad(x):
    pf = x.perfil
    r = random.Random(x.semilla)
    n_lotes = x.extra.get("lotes", 3)
    refrig = x.extra.get("refrigeracion")
    meses_lp = [0, 3, 6, 9, 12] if not x.extra.get("meses_largo_plazo") else [0, x.extra["meses_largo_plazo"]]
    lotes = [lote(x, i) for i in range(n_lotes)]
    tabla_lotes = [["Lote", "Tipo", "Tamaño", "Fecha de fabricación", "Lote de fármaco"]] + [
        [l, "Piloto" if i == 0 else "Producción", pf["tamano_lote"], fc(x.fecha - timedelta(days=420 - i * 15)), f"API24{i + 3:02d}{r.randint(10, 99)}"]
        for i, l in enumerate(lotes)]
    if refrig:
        condiciones = [["Estudio", "Condición", "Periodo", "Frecuencia"],
                       ["Largo plazo", "5 °C ± 3 °C", "12 meses (continúa a 24)", "0, 3, 6, 9, 12 meses"],
                       ["Acelerada", "25 °C ± 2 °C / 60% ± 5% HR", "6 meses", "0, 1, 3, 6 meses"]]
        acel = [0, 1, 3, 6]
    else:
        condiciones = [["Estudio", "Condición", "Periodo mínimo", "Frecuencia"],
                       ["Acelerada", "40 °C ± 2 °C / 75% ± 5% HR", "3 meses", "0, 1, 3 meses"],
                       ["Largo plazo", "30 °C ± 2 °C / 65% ± 5% HR", "12 meses", "0, 3, 6, 9, 12 meses"]]
        acel = [0, 1, 3]
    param = "Potencia (%)" if refrig else "Valoración (%)"
    res_acel = [["Lote", "Parámetro"] + [f"{m} m" for m in acel]]
    res_lp = [["Lote", "Parámetro"] + [f"{m} m" for m in meses_lp]]
    for l in lotes:
        res_acel.append([l, param] + _serie(r, 99.6, acel, 0.35))
        res_acel.append([l, "Impurezas totales (%)" if not refrig else "Agregados SEC (%)"] + [f"{0.12 + 0.05 * m + r.uniform(0, 0.03):.2f}" for m in acel])
        res_lp.append([l, param] + _serie(r, 99.6, meses_lp, 0.08))
        res_lp.append([l, "Disolución (%)" if not refrig else "pH"] + ([f"{r.uniform(88, 94):.0f}" for _ in meses_lp] if not refrig else [f"{5.2 + r.uniform(-0.05, 0.05):.2f}" for _ in meses_lp]))
    ancho_cols = [24 * mm, 40 * mm] + [110 * mm / len(acel)] * len(acel)
    ancho_lp = [24 * mm, 40 * mm] + [110 * mm / len(meses_lp)] * len(meses_lp)
    secciones = [
        ("1. Objetivo", [P(f"Establecer el periodo de caducidad de {prod(x)} en su sistema contenedor-cierre propuesto para comercialización, conforme a la NOM-073-SSA1-2015.")]),
        ("2. Lotes del estudio", [tabla(tabla_lotes, [26 * mm, 26 * mm, 38 * mm, 40 * mm, 44 * mm])]),
        ("3. Sistema contenedor-cierre", [P(f"{pf['empaque']}, idéntico al propuesto para comercialización.")]),
        ("4. Condiciones del estudio", [tabla(condiciones, [34 * mm, 54 * mm, 40 * mm, 46 * mm])]),
        ("5. Resultados – estabilidad acelerada", [tabla(res_acel, ancho_cols, alinear_centro=tuple(range(2, 2 + len(acel))))]),
        ("6. Resultados – estabilidad a largo plazo", [tabla(res_lp, ancho_lp, alinear_centro=tuple(range(2, 2 + len(meses_lp))))]),
    ]
    if refrig and not x.extra.get("sin_excursiones"):
        secciones.append(("7. Excursiones de temperatura", [P("Se evaluaron excursiones de 25 °C por 72 h y de 30 °C por 24 h sin cambios significativos en potencia ni en agregados.")]))
    secciones.append(("Conclusión", [P(f"Con base en los resultados, se propone un periodo de caducidad tentativo de {pf['caducidad_meses']} meses "
                                       f"en las condiciones de conservación: {pf['conservacion']} El estudio a largo plazo continúa.")]))
    informe(x, "INFORME DEL ESTUDIO DE ESTABILIDAD", f"CMC-EST-{x.producto['producto_id']}", secciones,
            firmantes=firmantes_std(x, rs_firma=x.extra.get("firma_rs", True)), area="CMC")


def estabilidad_farmaco(x):
    r = random.Random(x.semilla)
    filas = [["Lote", "Condición", "0 m", "6 m", "12 m", "24 m"]]
    for i in range(2):
        filas.append([f"API23{i + 1:02d}{r.randint(10, 99)}", "25 °C / 60% HR"] + [f"{99.5 - 0.05 * m + r.uniform(-0.2, 0.2):.1f}" for m in (0, 6, 12, 24)])
    informe(x, "ESTABILIDAD DEL FÁRMACO (RESUMEN DEL FABRICANTE)", f"CMC-ESTF-{x.producto['producto_id']}",
            [("Resumen", [P(f"Información de estabilidad del fármaco proporcionada por {x.fabricante[0]}, fármaco conocido (NOM-073-SSA1-2015, punto 6.1.1, opción 1: dos lotes de producción).")]),
             ("Valoración (%)", [tabla(filas, [30 * mm, 40 * mm, 26 * mm, 26 * mm, 26 * mm, 26 * mm], alinear_centro=(2, 3, 4, 5))]),
             ("Conclusión", [P("Se establece un periodo de reanálisis de 36 meses a no más de 25 °C.")])], area="CMC")


# ============================================================================ bioequivalencia
def bioequivalencia(x):
    pf = x.perfil
    lo, hi = x.extra.get("ic_cmax", (93.1, 108.7))
    cmax_t, cmax_r = pf["pk"]["cmax"]
    abc_t, abc_r = pf["pk"]["abc"]
    ratio_c = (lo * hi) ** 0.5
    secciones = [
        ("1. Datos generales", [tabla_datos([("Tercero autorizado", "Unidad de Farmacología Clínica del Centro, S.C. (ficticia) – TA-UFC-031-2024"),
                                             ("Medicamento de prueba", f"{prod(x)}, lote {lote(x)}, {EMPRESA['nombre_corto']}"),
                                             ("Medicamento de referencia", "Medicamento de referencia designado por COFEPRIS (lote R-2291)"),
                                             ("Diseño", "Cruzado 2×2, dosis única, en ayuno, aleatorizado, abierto"),
                                             ("Sujetos", "26 incluidos; 26 evaluables (número definido en protocolo v1.0)"),
                                             ("Periodo de lavado", "7 días")])]),
        ("2. Parámetros farmacocinéticos (medias geométricas)", [tabla(
            [["Parámetro", "Prueba", "Referencia", "Cociente P/R (%)", "IC 90% (%)"],
             ["Cmáx (ng/mL)", f"{cmax_t:,.1f}", f"{cmax_r:,.1f}", f"{ratio_c:.2f}", f"{lo:.2f} – {hi:.2f}"],
             ["ABC0-t (ng·h/mL)", f"{abc_t:,.1f}", f"{abc_r:,.1f}", f"{abc_t / abc_r * 100:.2f}", "94.18 – 106.31"],
             ["ABC0-∞ (ng·h/mL)", f"{abc_t * 1.04:,.1f}", f"{abc_r * 1.04:,.1f}", f"{abc_t / abc_r * 100:.2f}", "94.40 – 106.52"]],
            [38 * mm, 30 * mm, 30 * mm, 34 * mm, 42 * mm], alinear_centro=(1, 2, 3, 4))]),
        ("3. Criterio de aceptación", [P("Los intervalos de confianza al 90% de las medias geométricas de los cocientes prueba/referencia de Cmáx y ABC deben encontrarse entre 80 y 125% (NOM-177-SSA1-2013, numeral 9.6.4).")]),
        ("4. Seguridad", [P("Se registraron 3 eventos adversos leves (cefalea, náusea), resueltos sin secuelas. No hubo eventos adversos serios.")]),
        ("5. Conclusión", [P(f"<b>Los medicamentos de prueba y de referencia son bioequivalentes</b> y, por lo tanto, {prod(x, False)} de {EMPRESA['nombre_corto']} se considera intercambiable.")]),
    ]
    informe(x, "INFORME FINAL DEL ESTUDIO DE BIOEQUIVALENCIA", f"BE-{x.producto['producto_id']}-01", secciones,
            firmantes=[("Investigador principal", "Dr. Joaquín Medrano Lugo (ficticio)", "Tercero autorizado", fc(x.fecha), True),
                       ("Responsable analítico", "Q.F.B. Laura Peniche Ortiz (ficticia)", "Tercero autorizado", fc(x.fecha), True),
                       ("Revisión del patrocinador", x.usuarios_rol("Gerente Médico")["nombre"], "Gerente Médico", fc(x.fecha), True)], area="Clínico")


def perfiles_disolucion(x):
    f2s = x.extra.get("f2", (60.1, 58.3, 62.7))
    tiempos = [10, 15, 20, 30, 45]
    secciones = [("1. Condiciones", [tabla_datos([("Aparato", "USP 2 (paletas), 50 rpm, 900 mL, 37 ± 0.5 °C"),
                                                   ("Unidades por producto", "12"), ("Medios", "pH 1.2, pH 4.5 y pH 6.8"),
                                                   ("Criterio", "f2 ≥ 50 en cada medio (NOM-177-SSA1-2013, 7.5.5)")])])]
    resumen = [["Medio", "f2", "Conclusión"]]
    for medio, f2 in zip(["pH 1.2", "pH 4.5", "pH 6.8"], f2s):
        ref = [38, 55, 68, 84, 95] if medio != "pH 4.5" else [30, 46, 60, 77, 91]
        dif = math.sqrt(max((100 / 10 ** (f2 / 50)) ** 2 - 1, 0))
        prueba = [max(0, v - dif) for v in ref]
        filas = [["Tiempo (min)"] + [str(t) for t in tiempos],
                 ["Referencia (% disuelto)"] + [f"{v:.1f}" for v in ref],
                 ["Prueba (% disuelto)"] + [f"{v:.1f}" for v in prueba]]
        secciones.append((f"Perfil en {medio}", [tabla(filas, [44 * mm] + [26 * mm] * 5, alinear_centro=(1, 2, 3, 4, 5))]))
        resumen.append([medio, f"{f2:.1f}", "Similar"])
    secciones.append(("Resumen y conclusión", [tabla(resumen, [50 * mm, 40 * mm, 84 * mm], alinear_centro=(1,)),
                                                P("<b>Los perfiles de disolución del medicamento de prueba y del de referencia son similares en los tres medios.</b>")]))
    informe(x, "INFORME DE PERFILES DE DISOLUCIÓN COMPARATIVOS", f"CMC-PD-{x.producto['producto_id']}", secciones, area="CMC")


# ============================================================================ informes técnicos breves
def _generico(x, titulo, codigo, secciones, area=None):
    informe(x, titulo, codigo, secciones, area=area)


def resumen_calidad(x):
    pf = x.perfil
    _generico(x, "RESUMEN GLOBAL DE CALIDAD (MÓDULO 2.3)", "CMC-RGC-01", [
        ("2.3.S Fármaco", [P(f"{pf['sal']}, fabricado por {x.fabricante[0]} ({x.fabricante[1]}). Controlado conforme a farmacopea y especificaciones internas.")]),
        ("2.3.P Medicamento", [P(f"{prod(x)}. {pf['apariencia']} Empaque: {pf['empaque']}.")]),
        ("Puntos críticos", [P("Disolución y uniformidad de contenido controladas en proceso; estabilidad conforme a NOM-073-SSA1-2015.")])])


def info_general_farmaco(x):
    pf = x.perfil
    _generico(x, "INFORMACIÓN GENERAL DEL FÁRMACO (3.2.S.1)", "CMC-S1-01", [
        ("Nomenclatura", [tabla_datos([("Nombre", pf["sal"]), ("Clase", pf["clase"]), ("Fabricante", f"{x.fabricante[0]} ({x.fabricante[1]})")])]),
        ("Propiedades generales", [P("Polvo cristalino blanco a blanquecino, soluble en agua, polimorfo declarado forma I.")])])


def fabricacion_farmaco(x):
    _generico(x, "FABRICACIÓN DEL FÁRMACO (3.2.S.2)", "CMC-S2-01", [
        ("Fabricante", [tabla_datos([("Razón social", x.fabricante[0]), ("País", x.fabricante[1]),
                                     ("Certificado de BPF", "Ver sección 1.7.2 del expediente")])]),
        ("Descripción del proceso", [P("Síntesis en cuatro etapas con purificación final por cristalización; controles en proceso de pureza quiral y solventes residuales.")])])


def composicion(x):
    pf = x.perfil
    filas = [["Componente", "Función", "Cantidad por unidad"], [pf["sal"], "Fármaco", pf["cantidad_sal"]]]
    for e in pf["excipientes"]:
        filas.append([e, "Excipiente", "cbp"])
    _generico(x, "DESCRIPCIÓN Y COMPOSICIÓN DEL MEDICAMENTO (3.2.P.1)", "CMC-P1-01",
              [("Composición cualicuantitativa", [tabla(filas, [96 * mm, 38 * mm, 40 * mm])]),
               ("Descripción", [P(pf["apariencia"])])])


def validacion_proceso(x):
    filas = [["Lote", "Tamaño", "Uniformidad (VA)", "Disolución (%)", "Valoración (%)", "Resultado"]]
    r = random.Random(x.semilla)
    for i in range(3):
        filas.append([lote(x, 10 + i), x.perfil["tamano_lote"], f"{r.uniform(2.5, 5.0):.1f}", f"{r.uniform(88, 94):.0f}", f"{r.uniform(98.5, 100.8):.1f}", "Cumple"])
    _generico(x, "INFORME DE VALIDACIÓN DEL PROCESO DE FABRICACIÓN", "CC-VP-01", [
        ("Enfoque", [P("Validación con enfoque de ciclo de vida (NOM-059-SSA1-2015, 9.9): diseño, calificación del proceso y verificación continua.")]),
        ("Calificación del desempeño del proceso", [tabla(filas, [26 * mm, 32 * mm, 30 * mm, 28 * mm, 30 * mm, 28 * mm], alinear_centro=(2, 3, 4, 5))]),
        ("Conclusión", [P("Tres lotes consecutivos de tamaño comercial demostraron que el proceso es capaz, estable y consistente.")])], area="Calidad")


def validacion_limpieza(x):
    _generico(x, "INFORME DE VALIDACIÓN DE LIMPIEZA", "CC-VL-01", [
        ("Criterio", [P("Límite de residuo calculado por dosis terapéutica (1/1000) y límite general de 10 ppm; peor caso por solubilidad y potencia.")]),
        ("Resultados", [tabla([["Equipo", "Residuo (µg/hisopo)", "Límite", "Resultado"],
                               ["Granulador de alto corte", "1.8", "12.5", "Cumple"], ["Tableteadora rotativa", "2.4", "12.5", "Cumple"],
                               ["Bombo de recubrimiento", "0.9", "12.5", "Cumple"]], [60 * mm, 40 * mm, 34 * mm, 40 * mm], alinear_centro=(1, 2, 3))])], area="Calidad")


def validacion_metodos(x):
    _generico(x, "INFORME DE VALIDACIÓN DE MÉTODOS ANALÍTICOS", "CC-VM-01", [
        ("Método", [P("Valoración y sustancias relacionadas por HPLC-UV (MA-CC-118).")]),
        ("Parámetros", [tabla([["Parámetro", "Criterio", "Resultado"], ["Linealidad", "r² ≥ 0.999", "0.9997"],
                               ["Exactitud", "98.0 – 102.0%", "99.4%"], ["Precisión (repetibilidad)", "CV ≤ 2.0%", "0.6%"],
                               ["Especificidad", "Sin interferencias", "Cumple"], ["Robustez", "Sin cambios significativos", "Cumple"]],
                              [60 * mm, 60 * mm, 54 * mm])])], area="Calidad")


def contenedor_cierre(x):
    _generico(x, "SISTEMA CONTENEDOR-CIERRE (3.2.P.7)", "CMC-P7-01", [
        ("Descripción", [P(f"{x.perfil['empaque']}. Materiales conformes a farmacopea; especificaciones de proveedor anexas.")]),
        ("Compatibilidad", [P("El mismo sistema se empleó en los estudios de estabilidad (NOM-073-SSA1-2015, 8.2).")])])


def programa_aseguramiento(x):
    secciones = [("6.1.1 Programa de validaciones y revalidaciones", [P("Revalidación anual del proceso de purificación y de la cadena de frío.")]),
                 ("6.1.2 Parámetros críticos de validación", [tabla([["Parámetro", "Rango validado"], ["Temperatura de biorreactor", "36.5 ± 0.5 °C"],
                                                                     ["pH de cultivo", "7.0 ± 0.1"], ["Rendimiento de proteína A", "≥ 85%"]], [90 * mm, 84 * mm])])]
    if not x.extra.get("sin_auditorias"):
        secciones.append(("6.1.3 Programa de auditorías internas", [P("Auditorías semestrales al proceso y al producto.")]))
    secciones += [("6.1.4 Acciones preventivas y correctivas", [P("Se reportan las CAPA asociadas a parámetros críticos.")]),
                  ("6.1.5 Reporte anual", [P("Se presentará anualmente a partir de la emisión del registro.")])]
    _generico(x, "PROGRAMA DE ASEGURAMIENTO DE CALIDAD DEL PRODUCTO BIOTECNOLÓGICO", "CC-PAC-01", secciones, area="Calidad")


def caracterizacion(x):
    _generico(x, "CARACTERIZACIÓN FISICOQUÍMICA Y BIOLÓGICA COMPARATIVA", "CMC-CAR-01", [
        ("Atributos evaluados", [tabla([["Atributo", "Método", "Resultado vs. referencia"],
                                        ["Estructura primaria", "Mapeo peptídico LC-MS", "Idéntica"],
                                        ["Glicosilación", "HILIC-FLR", "Dentro del rango de la referencia"],
                                        ["Variantes de carga", "cIEF", "Comparable"],
                                        ["Unión a TNF-α", "ELISA / SPR", "Equivalente (IC 90%)"]], [56 * mm, 56 * mm, 62 * mm])])], area="CMC")


def estudio_biocomparabilidad(x):
    _generico(x, "INFORME DEL ESTUDIO CLÍNICO DE BIOCOMPARABILIDAD", "CL-BC-01", [
        ("Diseño", [P("Estudio aleatorizado, doble ciego, en 412 pacientes con artritis reumatoide moderada a grave, 52 semanas.")]),
        ("Resultado primario", [P("Respuesta ACR20 a la semana 24: 71.8% (Altamira) vs. 72.9% (referencia); diferencia −1.1% (IC 95%: −9.6 a 7.4), dentro del margen de equivalencia de ±15%.")]),
        ("Inmunogenicidad y seguridad", [P("Incidencia de anticuerpos antifármaco comparable; perfil de seguridad similar.")])], area="Clínico")


# ============================================================================ oficios y respuestas
def oficio_prevencion(x):
    pv, obs = x.prevencion, x.observaciones
    plazo = int(pv["plazo_dias_habiles"])
    letras = {5: "CINCO", 10: "DIEZ", 15: "QUINCE", 20: "VEINTE"}[plazo]
    fecha = date.fromisoformat(pv["fecha_emision"])
    flow = [Spacer(1, 2 * mm),
            P(f"<b>C. {x.rl['nombre']}</b><br/>Representante legal de {EMPRESA['razon_social']}<br/>{EMPRESA['domicilio_planta']}<br/>Presente", "oficio"),
            Spacer(1, 4),
            P(f"Me refiero a su solicitud con número de folio <b>{x.tramite['folio_digipris']}</b>, ingresada el "
              f"{fl(date.fromisoformat(x.tramite['fecha_ingreso']))}, relativa a <b>{x.tramite['tipo_tramite']}</b> "
              f"(homoclave {x.tramite['homoclave']}) del medicamento <b>{prod(x)}</b>.", "oficio"),
            P(f"Del análisis de la documentación presentada, y con fundamento en los artículos 17-A de la Ley Federal de "
              f"Procedimiento Administrativo, y 153, 155 y 156 del Reglamento de Insumos para la Salud, se le <b>PREVIENE</b> "
              f"para que, en un plazo de <b>{letras} ({plazo}) DÍAS HÁBILES</b>, contados a partir del día hábil siguiente a "
              f"aquel en que surta efectos la notificación del presente oficio, subsane lo siguiente:", "oficio")]
    for i, o in enumerate(obs, 1):
        fund = f"{o['norma']}, numeral {o['clausula']}" if o["norma"] and o["clausula"] else (o["norma"] or o["fundamento"])
        flow.append(P(f"<b>{i}.</b> {o['texto']} <i>Fundamento: {fund}.</i> (Sección CTD {o['seccion_ctd']})", "oficio"))
    flow += [P("Se le apercibe que, de no desahogar la presente prevención en el plazo señalado, la solicitud se tendrá por no "
               "presentada, de conformidad con el artículo 155 del Reglamento de Insumos para la Salud. El plazo para resolver "
               "se suspende a partir de la notificación del presente y se reanudará al día siguiente de que se desahogue.", "oficio"),
             P("La respuesta deberá presentarse por la misma plataforma digital, en una sola entrega, identificando cada punto.", "oficio"),
             Spacer(1, 8), P("Atentamente,", "oficio"),
             Dibujo(174 * mm, 18 * mm, lambda c, w, h: dibujar_firma(c, 4 * mm, 2, 46 * mm, 14 * mm, semilla=x.semilla, color=colors.black)),
             P(f"<b>{pv['dictaminador_simulado']}</b><br/>Dictaminador(a) – Comisión de Autorización Sanitaria (nombre ficticio)", "oficio"),
             Spacer(1, 6), qr_imagen(f"SIMULADO|{pv['numero_oficio']}|{x.tramite['folio_digipris']}|{pv['fecha_emision']}", 24 * mm),
             P(f"Cadena de verificación simulada: {huella(pv['numero_oficio'], pv['fecha_emision'])} · "
               f"UUID simulado: {(u := huella(pv['prevencion_id'], n=32))[:8]}-{u[8:12]}-4{u[13:16]}-a{u[17:20]}-{u[20:32]}", "nota")]
    documento_autoridad(x.ruta, flow, "Comisión de Autorización Sanitaria",
                        [f"Oficio No. {pv['numero_oficio']}", "Asunto: Se previene", f"Ciudad de México, a {fl(fecha)}"])


def escrito_respuesta(x):
    pv, obs = x.prevencion, x.observaciones
    fecha = date.fromisoformat(pv["fecha_respuesta"])
    respuestas = {
        "7.5.5": ("Se repitió el perfil de disolución en pH 4.5 con 12 unidades por producto y el lote de producción actual; "
                  "el f2 obtenido es de 58.6. Se anexa el informe completo (Anexo 1)."),
        "9.9.2.2.3": ("Se completó la calificación del desempeño del proceso con un tercer lote consecutivo de tamaño comercial "
                      "(lote 0626118). Se anexa el informe de validación actualizado (Anexo 2)."),
    }
    flow = [P(f"Toluca, Estado de México, a {fl(fecha)}", "txt_d"),
            P("<b>Comisión Federal para la Protección contra Riesgos Sanitarios</b><br/>Comisión de Autorización Sanitaria<br/>Presente", "txt"),
            P(f"<b>Asunto:</b> Desahogo de la prevención contenida en el oficio {pv['numero_oficio']}. Folio {x.tramite['folio_digipris']}.", "txt"),
            P(f"{x.rl['nombre']}, en mi carácter de representante legal de {EMPRESA['razon_social']}, personalidad que tengo "
              f"debidamente acreditada, en atención al oficio citado, notificado el {fl(date.fromisoformat(pv['fecha_apertura']))}, "
              f"y dentro del plazo concedido, manifiesto lo siguiente:", "txt")]
    for i, o in enumerate(obs, 1):
        flow.append(P(f"Observación {i} – {o['norma']} {o['clausula']}", "h2"))
        flow.append(P(f"<i>{o['texto']}</i>", "txt"))
        flow.append(P(f"<b>Respuesta:</b> {respuestas.get(o['clausula'], 'Se atiende la observación y se anexa la documentación corregida.')}", "txt"))
    flow += [P("Por lo expuesto, solicito tener por desahogada en tiempo y forma la prevención y continuar con la evaluación del trámite.", "txt"),
             bloque_firmas([("Representante legal", x.rl["nombre"], EMPRESA["razon_social"], fc(fecha), True),
                            ("Responsable sanitario", x.rs["nombre"], f"Céd. Prof. {x.rs['cedula_profesional']}", fc(fecha), True)], semilla=x.semilla)]
    documento_altamira(x.ruta, "ESCRITO DE RESPUESTA A PREVENCIÓN", f"RA-RP-{pv['prevencion_id']}", flow)


PLANTILLAS = {k: v for k, v in globals().items() if callable(v) and not k.startswith("_") and k not in (
    "fl", "fc", "prod", "lote", "firmantes_std", "informe", "P", "tabla", "tabla_datos", "Dibujo", "bloque_firmas",
    "dibujar_logo", "dibujar_sello", "dibujar_firma", "qr_imagen", "documento_altamira", "documento_autoridad",
    "documento_simple", "Paragraph", "Spacer", "PageBreak", "KeepTogether", "ParagraphStyle", "date", "timedelta",
    "Table", "TableStyle", "huella")}
