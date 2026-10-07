"""Calendario de días hábiles para contar plazos ante COFEPRIS.

Inhábiles: sábados, domingos, descansos obligatorios de la Ley Federal del Trabajo (art. 74) y días
que la Administración Pública Federal suele declarar inhábiles. Los periodos vacacionales son una
aproximación: COFEPRIS publica cada año su acuerdo de días inhábiles en el DOF.
"""
from datetime import date, timedelta


def _pascua(anio):
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    mes = (h + l - 7 * m + 114) // 31
    dia = (h + l - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def _n_lunes(anio, mes, n):
    d = date(anio, mes, 1)
    d += timedelta(days=(0 - d.weekday()) % 7)
    return d + timedelta(weeks=n - 1)


def inhabiles_del_anio(anio):
    """Regresa {fecha: motivo}."""
    dias = {
        date(anio, 1, 1): "Año Nuevo (LFT art. 74)",
        _n_lunes(anio, 2, 1): "Día de la Constitución (LFT art. 74)",
        _n_lunes(anio, 3, 3): "Natalicio de Benito Juárez (LFT art. 74)",
        date(anio, 5, 1): "Día del Trabajo (LFT art. 74)",
        date(anio, 9, 16): "Independencia (LFT art. 74)",
        _n_lunes(anio, 11, 3): "Revolución Mexicana (LFT art. 74)",
        date(anio, 12, 25): "Navidad (LFT art. 74)",
        date(anio, 11, 2): "Día de Muertos (inhábil APF, habitual)",
        date(anio, 12, 12): "Día de la Virgen de Guadalupe (inhábil APF, habitual)",
    }
    pascua = _pascua(anio)
    dias[pascua - timedelta(days=3)] = "Jueves Santo (inhábil APF)"
    dias[pascua - timedelta(days=2)] = "Viernes Santo (inhábil APF)"
    if anio == 2024:
        dias[date(2024, 10, 1)] = "Transmisión del Poder Ejecutivo (LFT art. 74)"
    for d in range(18, 32):  # segunda quincena de diciembre (aproximado)
        dias.setdefault(date(anio, 12, d), "Periodo vacacional de fin de año (aproximado; confirmar acuerdo COFEPRIS)")
    for d in range(15, 27):  # periodo vacacional de verano (aproximado)
        f = date(anio, 7, d)
        if f.weekday() < 5:
            dias.setdefault(f, "Periodo vacacional de verano (aproximado; confirmar acuerdo COFEPRIS)")
    return dias


class Calendario:
    def __init__(self, desde=2023, hasta=2027):
        self.inhabiles = {}
        for a in range(desde, hasta + 1):
            self.inhabiles.update(inhabiles_del_anio(a))
        self.desde, self.hasta = date(desde, 1, 1), date(hasta, 12, 31)

    def es_habil(self, d):
        return d.weekday() < 5 and d not in self.inhabiles

    def siguiente_habil(self, d):
        d += timedelta(days=1)
        while not self.es_habil(d):
            d += timedelta(days=1)
        return d

    def sumar_habiles(self, d, n):
        """Día hábil número n contado a partir del día siguiente a d."""
        for _ in range(n):
            d = self.siguiente_habil(d)
        return d

    def habiles_entre(self, a, b):
        """Días hábiles en (a, b]."""
        n, d = 0, a
        while d < b:
            d += timedelta(days=1)
            n += self.es_habil(d)
        return n

    def filas(self):
        d = self.desde
        while d <= self.hasta:
            motivo = "Fin de semana" if d.weekday() >= 5 else self.inhabiles.get(d, "")
            yield dict(fecha=d.isoformat(), anio=d.year, mes=d.month, dia_semana=d.isoweekday(),
                       es_habil=self.es_habil(d), motivo_inhabil=motivo)
            d += timedelta(days=1)
