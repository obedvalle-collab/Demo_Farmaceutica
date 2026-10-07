"""Preguntas de control para el buscador de normas (las mismas en ambas plataformas).

Cada pregunta está redactada con palabras distintas a las de la norma, para probar la búsqueda por
significado. Se considera acierto si la cláusula esperada aparece entre los 3 primeros resultados.
"""
PREGUNTAS = [
    ("¿A qué temperatura y por cuánto tiempo se hace la estabilidad acelerada de un medicamento genérico?", "NOM-073-SSA1-2015", "8.5.1"),
    ("¿Cuántos lotes necesito para el estudio de estabilidad de un genérico?", "NOM-073-SSA1-2015", "8.1"),
    ("Leyenda obligatoria en la caja de un medicamento que solo se vende con receta", "NOM-072-SSA1-2012", "6.1.4"),
    ("Siglas que deben aparecer en el empaque de un biocomparable", "NOM-072-SSA1-2012", "5.31.7"),
    ("Leyenda para medicamentos de enfermedades crónicas sobre no vender por partes", "NOM-072-SSA1-2012", "5.19"),
    ("Criterio estadístico del intervalo de confianza para declarar bioequivalencia", "NOM-177-SSA1-2013", "9.6.4"),
    ("Valor mínimo del factor de similitud al comparar perfiles de disolución", "NOM-177-SSA1-2013", "7.5.5"),
    ("¿Qué debe incluir el plan de minimización de riesgos en farmacovigilancia?", "NOM-220-SSA1-2016", "8.4.3.1.4"),
    ("¿Con cuántos lotes consecutivos se califica el proceso de fabricación?", "NOM-059-SSA1-2015", "9.9.2.2.3"),
    ("Programa de auditorías internas para medicamentos biotecnológicos", "NOM-257-SSA1-2014", "6.1.3"),
    ("Documentos que se presentan para obtener el registro sanitario de un medicamento alopático", "RIS", "Art. 167"),
    ("¿Cuánto dura el registro sanitario de un medicamento y su prórroga?", "LGS", "Art. 376"),
]


def calificar(resultados, norma, numeral, k=3):
    """resultados: lista de (norma, numeral) en orden. Devuelve (acierto_clausula, acierto_norma, posicion)."""
    top = resultados[:k]
    pos = next((i + 1 for i, (n, c) in enumerate(resultados) if n == norma and c == numeral), None)
    return (norma, numeral) in top, any(n == norma for n, _ in top), pos
