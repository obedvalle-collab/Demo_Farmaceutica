# Optimización de velocidad de la IA (Snowflake) — 15/10/2026

Medición de las tareas reales de la app con cuatro modelos disponibles en `AI_COMPLETE` (segundos).

| Tarea | Sonnet 4.5 (antes) | Sonnet 4.6 | Sonnet 5 | Haiku 4.5 | Decisión |
|---|---|---|---|---|---|
| Extraer datos de un documento (bandeja) | 7.7 | 7.1 | 9.8 | 6.5 | **Sin cambio**: con Sonnet 4.6 solo 66/72 datos iguales (Sonnet 4.5: 70/72); alimenta el candado |
| Pre-auditoría (1 trámite) | 87.5 | 62.1 | 31.1 | **23.9** | **Haiku 4.5**: examen 9/10 por sección y 7/10 con numeral (antes 10/10 y 7/10) |
| Evaluar una versión | 11.2 | 8.7 | 11.8 | 10.1 | **Sin cambio**: Sonnet 4.6 reconoció 4/8 correcciones reales (antes 8/8); Haiku dio un veredicto fuera de formato |
| Borrador de respuesta a la prevención | 20.1 | **11.9** | 14.9 | 7.1 | **Sonnet 4.6**: redacción equivalente; Haiku la deja más corta |
| Asistente (orquestador del Cortex Agent) | 19.6 (8/8) | 21.1 (7/8) | – | – | **Sin cambio**: el tiempo lo consumen las herramientas, no el modelo |

Lectura del PDF: modo LAYOUT 16 s vs OCR 3 s en la etiqueta, pero con OCR cambiaron conclusiones y pruebas fuera de
especificación en documentos con tablas → **se mantiene LAYOUT**.

Resultado en la app: la pre-auditoría pasa de 60–90 s a ≈ 22 s y el borrador de ≈ 20 s a ≈ 12 s. El resto se queda
igual para no perder precisión. Configuración en `app/comun/datos_snowflake.py` (`MODELOS_TAREA`). Databricks no
cambia: su workspace solo tiene gpt-oss-120b con calidad suficiente.
