"""Utilidades de pantalla compartidas por las vistas (mismo código en ambas plataformas)."""
from datetime import date, datetime
from decimal import Decimal

import pandas as pd
import streamlit as st

SEMAFORO = {"Verde": "#1e6b42", "Amarillo": "#b7791f", "Rojo": "#c0392b", "Vencido": "#6b0f1a",
            "En trámite": "#2f6690", "Sin prevención": "#9aa5b1", "Cerrada": "#9aa5b1"}
ICONO = {"Verde": "🟢", "Amarillo": "🟡", "Rojo": "🔴", "Vencido": "⛔", "En trámite": "🔵", "Sin prevención": "⚪"}


def tabla(filas):
    """Filas (dicts) → DataFrame con números y fechas tipados.
    Databricks devuelve todo como texto y Snowflake como Decimal; así ambas se ven igual."""
    df = pd.DataFrame(filas)
    for c in df.columns:
        muestra = df[c].dropna()
        if muestra.empty:
            continue
        v = muestra.iloc[0]
        if isinstance(v, Decimal):
            df[c] = df[c].astype(float)
        elif isinstance(v, (date, datetime)):
            continue
        elif isinstance(v, str):
            num = pd.to_numeric(df[c], errors="coerce")
            if num.notna().sum() == muestra.size:
                df[c] = num
            elif muestra.str.match(r"\d{4}-\d{2}-\d{2}T\d{2}:").all():   # marca de tiempo ISO (Databricks)
                df[c] = pd.to_datetime(df[c], errors="coerce", utc=True).dt.tz_localize(None)
            elif muestra.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all():
                df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
            elif muestra.isin(["true", "false"]).all():
                df[c] = df[c].map({"true": True, "false": False})
    return df


def encabezado(titulo, plataforma, subtitulo=""):
    st.title(titulo)
    st.caption(f"Laboratorios Altamira (ficticio) · Plataforma: **{plataforma}** · Fecha de la demo: 06/10/2026"
               + (f" · {subtitulo}" if subtitulo else ""))


def tarjeta(col, titulo, valor, detalle="", color="#12355B"):
    col.markdown(f"""<div style="border-top:4px solid {color};background:#f7f8fa;padding:10px 14px;border-radius:6px;height:100%">
        <div style="font-size:12px;color:#5f6b76">{titulo}</div>
        <div style="font-size:26px;font-weight:700;color:{color}">{valor}</div>
        <div style="font-size:12px;color:#5f6b76">{detalle}</div></div>""", unsafe_allow_html=True)
