"""Parámetros generales del generador de datos ficticios (Laboratorios Altamira).

Todo lo de la empresa es inventado. Las NOM, cláusulas, artículos y homoclaves son reales
(ver normas/README.md y docs/INVESTIGACION_FASE0.md).
"""
from datetime import date
from pathlib import Path

SEMILLA = 20261006          # misma semilla → mismos datos en cada corrida
HOY = date(2026, 10, 6)     # "fecha actual" de la demo
INICIO_HISTORIA = date(2023, 10, 1)

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "datos" / "salida"
SALIDA_TABLAS = SALIDA / "tablas"
SALIDA_PDF = SALIDA / "pdf"

EMPRESA = {
    "razon_social": "Laboratorios Altamira, S.A. de C.V.",
    "nombre_corto": "Laboratorios Altamira",
    "rfc": "LAL971103AB7",
    "domicilio_planta": "Av. de los Laboratorios No. 1200, Parque Industrial Santa Clara, "
                        "Toluca, Estado de México, C.P. 50071",
    # domicilio anterior: sirve para sembrar el defecto de domicilio que no coincide con el registro
    "domicilio_anterior": "Calle Química No. 245, Col. Industrial Vallejo, Azcapotzalco, "
                          "Ciudad de México, C.P. 02300",
    "licencia_sanitaria": "LS-15-AM-2019-0417",
    "telefono": "(722) 555 0148",
    "dominio_correo": "altamira-lab.example",   # dominio reservado para ejemplos: no existe
}

AVISO_FICTICIO = ("Documento ficticio generado para demostración. Laboratorios Altamira y todas las "
                  "personas mencionadas no existen.")
AVISO_SIMULADO_AUTORIDAD = "SIMULADO – NO ES UN DOCUMENTO OFICIAL"
