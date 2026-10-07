"""Parte el texto de una norma en cláusulas (numerales) o artículos, y las cláusulas en fragmentos para
el buscador. Es el MISMO código en Snowflake y en Databricks: solo cambia la IA que lee el PDF.

Sin dependencias externas (solo `re`), para poder registrarlo como función en ambas plataformas.

Funciones públicas:
    partir(texto, norma, tipo)      -> lista de cláusulas (dict)
    fragmentar(texto, encabezado)   -> lista de fragmentos de texto para el buscador
tipo: 'NOM' | 'PROY-NOM' | 'MODIFICACION' | 'LEY' | 'REGLAMENTO' | 'GUIA'
"""
import re

# ------------------------------------------------------------------ limpieza de ruido de página
_RUIDO = [
    r"^\(?\s*(primera|segunda|tercera|cuarta|quinta|sexta|s[eé]ptima|octava)\s+secci[oó]n\s*\)?(\s+\d{1,3})?$",
    r"^\d{1,3}\s+\(?(primera|segunda|tercera|cuarta|quinta)\s+secci[oó]n\)?$",
    r"^diario oficial$",
    r"^(lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\s+\d{1,2}\s+de\s+\w+\s+de\s+\d{4}$",
    r"^\d{1,4}$",
    r"^\d{1,4}\s+de\s+\d{1,4}$",
    r"^p[aá]gina\s+\d+(\s+de\s+\d+)?$",
    r"^dof\s*-\s*diario oficial de la federaci[oó]n$",
    r"^https?://\S+$",
    r"^\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}(\s*[ap]\.?\s*m\.?)?$",
    r"^\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}\s*[ap]\.\s*m\.\s*\d*$",
    r"^<!--.*-->$",
    r"^c[aá]mara de diputados del h\. congreso de la uni[oó]n$",
    r"^secretar[ií]a general$",
    r"^secretar[ií]a de servicios parlamentarios$",
]
_RUIDO_RE = [re.compile(p, re.I) for p in _RUIDO]


def _limpiar(texto):
    lineas = []
    for l in texto.replace("\r", "").split("\n"):
        s = l.strip()
        s = re.sub(r"^#{1,6}\s*", "", s)              # encabezados markdown
        s = s.replace("**", "").replace("__", "")     # negritas markdown
        if any(r.match(s) for r in _RUIDO_RE):
            continue
        lineas.append(s)
    return lineas


# ------------------------------------------------------------------ numerales tipo NOM / ICH
_NUM_RE = re.compile(r"^((?:[A-H]|\d{1,2})(?:\.\d{1,3}){0,7})\.?\s+([A-ZÁÉÍÓÚÑ¿\"“(].*)$")


def _partes(numeral):
    out = []
    for i, p in enumerate(numeral.split(".")):
        out.append(100 + ord(p) - ord("A") if (i == 0 and p.isalpha()) else int(p))
    return out


def _es_siguiente(prev, cand):
    if prev is None:
        return len(cand) == 1 and cand[0] in (0, 1)
    if cand[: len(prev)] == prev and len(cand) == len(prev) + 1 and cand[-1] in (1, 2):
        return True                                            # primer hijo
    for k in range(len(prev) - 1, -1, -1):                     # hermano o hermano de un ancestro
        if len(cand) == k + 1 and cand[:k] == prev[:k] and 1 <= cand[k] - prev[k] <= 3:
            return True
    if len(cand) == 2 and cand[0] >= 100 and cand[1] == 1 and cand[0] != prev[0]:
        return True                                            # inicio de apéndice (A.1, B.1, ...)
    return False


def _titulo(texto_linea):
    t = texto_linea.strip()
    m = re.match(r"^(.{3,110}?)[.:](\s+[A-ZÁÉÍÓÚÑ¿\"“(]|$)", t)
    if m:
        return m.group(1).strip()
    return t[:90].rstrip() + ("…" if len(t) > 90 else "")


def _parece_indice(corrida):
    """Un índice tiene sus numerales en renglones consecutivos; el cuerpo tiene texto entre ellos."""
    if len(corrida) < 2:
        return True
    huecos = [b[0] - a[0] for a, b in zip(corrida, corrida[1:])]
    return sum(huecos) / len(huecos) <= 2.5


def _partir_numerales(lineas, permisivo=False):
    candidatos = []
    for i, l in enumerate(lineas):
        m = _NUM_RE.match(l)
        if m:
            try:
                candidatos.append((i, m.group(1), _partes(m.group(1)), m.group(2)))
            except ValueError:
                pass
    # corridas: cada vez que la numeración "vuelve a empezar" (índice vs. cuerpo) se abre otra corrida
    corridas, actual, prev = [], [], None
    for c in candidatos:
        if permisivo or _es_siguiente(prev, c[2]):
            actual.append(c); prev = c[2]
        elif len(c[2]) == 1 and c[2][0] in (0, 1) and _parece_indice(actual):
            # solo se reinicia mientras la corrida actual parezca un índice (renglones seguidos, sin texto entre
            # ellos); ya dentro del cuerpo, un "1." suelto es una nota al pie o una lista y se queda como texto
            if actual:
                corridas.append(actual)
            actual, prev = [c], c[2]
    if actual:
        corridas.append(actual)
    if not corridas:
        return []

    # el cuerpo de la norma es la corrida con más numerales (el índice inicial solo trae los de primer nivel)
    mejor = max(corridas, key=len)
    clausulas = []
    for j, (i, numeral, partes, resto) in enumerate(mejor):
        fin = mejor[j + 1][0] if j + 1 < len(mejor) else len(lineas)
        cuerpo = " ".join(x for x in [resto] + lineas[i + 1: fin] if x)
        clausulas.append(dict(numeral=numeral, nivel=len(partes),
                              numeral_padre=".".join(numeral.split(".")[:-1]),
                              titulo=_titulo(_normalizar(cuerpo)), texto=_normalizar(cuerpo)))
    return clausulas


# ------------------------------------------------------------------ artículos de leyes y reglamentos
_ART_RE = re.compile(
    r"^ART[IÍ]CULO\s+(\d+(?:\s*[oº°])?\.?(?:\s*-?\s*(?:BIS|TER|QU[AÁ]TER)(?:\s*\d+)?)?)\s*[.\-–]+\s*(.*)$", re.I)
_CAP_RE = re.compile(r"^(T[IÍ]TULO|CAP[IÍ]TULO|SECCI[OÓ]N)\s+[\wÁÉÍÓÚ]+", re.I)


def _norm_articulo(n):
    n = re.sub(r"\s+", " ", n.replace("º", "o").replace("°", "o")).strip(" .-")
    n = re.sub(r"(?i)\s*-?\s*(bis|ter|qu[aá]ter)", lambda m: " " + m.group(1).capitalize(), n)
    return n


def _partir_articulos(lineas):
    clausulas, actual, contexto, ultimo_cap = [], None, "", None
    for i, l in enumerate(lineas):
        if _CAP_RE.match(l):
            ultimo_cap = i
            contexto = l
            continue
        if ultimo_cap is not None and i == ultimo_cap + 1 and l and not _ART_RE.match(l):
            contexto = f"{contexto} – {l}"
            continue
        if re.match(r"^TRANSITORIOS?$", l, re.I):
            if actual:
                clausulas.append(actual)
            actual = dict(numeral=f"Transitorios {sum(1 for c in clausulas if c['numeral'].startswith('Transitorios')) + 1}",
                          nivel=1, numeral_padre="", titulo="Artículos transitorios", contexto="Transitorios", lineas=[])
            continue
        m = _ART_RE.match(l)
        if m:
            if actual:
                clausulas.append(actual)
            num = _norm_articulo(m.group(1))
            actual = dict(numeral=f"Art. {num}", nivel=1, numeral_padre="", titulo="",
                          contexto=contexto, lineas=[m.group(2)])
        elif actual:
            actual["lineas"].append(l)
    if actual:
        clausulas.append(actual)
    for c in clausulas:
        c["texto"] = _normalizar(" ".join(x for x in c.pop("lineas") if x))
        c["titulo"] = c["titulo"] or _titulo(c["texto"] or c["contexto"])
    return clausulas


def _normalizar(t):
    t = re.sub(r"(\w)-\s+(\w)", r"\1\2", t)    # palabras cortadas con guion al final de línea
    return re.sub(r"\s{2,}", " ", t).strip()


# ------------------------------------------------------------------ API pública
def partir(texto, norma, tipo):
    lineas = _limpiar(texto or "")
    if tipo in ("LEY", "REGLAMENTO"):
        clausulas = _partir_articulos(lineas)
    else:
        clausulas = _partir_numerales(lineas, permisivo=(tipo == "MODIFICACION"))
    # ruta de títulos (ancestros) para dar contexto al buscador
    titulos = {}
    for orden, c in enumerate(clausulas, 1):
        c["orden"] = orden
        c["norma"] = norma
        titulos[c["numeral"]] = c["titulo"]
        if "contexto" not in c:
            partes = c["numeral"].split(".")
            ruta = [f"{'.'.join(partes[:k])} {titulos.get('.'.join(partes[:k]), '')}".strip() for k in range(1, len(partes))]
            c["contexto"] = " › ".join(ruta)
        c["caracteres"] = len(c["texto"])
    return clausulas


def fragmentar(texto, encabezado, maximo=1500, traslape=150):
    """Parte el texto de una cláusula larga en trozos; cada trozo lleva el encabezado para no perder contexto."""
    texto = texto or ""
    if len(texto) <= maximo:
        return [f"{encabezado}\n{texto}"]
    trozos, inicio = [], 0
    while inicio < len(texto):
        fin = min(len(texto), inicio + maximo)
        if fin < len(texto):
            corte = max(texto.rfind(". ", inicio, fin), texto.rfind("; ", inicio, fin))
            if corte > inicio + maximo // 2:
                fin = corte + 1
        trozos.append(f"{encabezado}\n{texto[inicio:fin].strip()}")
        if fin >= len(texto):
            break
        inicio = max(fin - traslape, inicio + 1)
    return trozos


def fragmentar_udf(texto, encabezado):
    """Versión de dos argumentos para registrarla como función (Snowflake no admite parámetros opcionales)."""
    return fragmentar(texto, encabezado)
