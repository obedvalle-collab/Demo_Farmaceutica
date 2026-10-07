# Fase 4 – Bandeja de carga inteligente: resultados (2026-10-07)

54 PDF de expedientes (7 escaneados, 1 ilegible a propósito) con 20 defectos sembrados. Misma instrucción y esquema de
extracción (`compartido/extraccion.py`), mismas 18 reglas de revisión (`compartido/sql/hallazgos.sql`) y mismo evaluador
(`compartido/evaluar_bandeja.py`). Cambia la IA de cada plataforma:

| | Snowflake | Databricks |
|---|---|---|
| Lectura del PDF | `AI_PARSE_DOCUMENT` LAYOUT (+ OCR si hay imágenes) | `ai_parse_document` v2.0 |
| Clasificación y extracción | `AI_COMPLETE` con **Claude Sonnet 4.5**, salida JSON con esquema | `ai_query` con **gpt-oss-120b** (mejor modelo disponible; sin Claude) |

## Resultado del examen

| | Snowflake | Databricks |
|---|---|---|
| Documentos bien clasificados | **52/54** | 42/54 |
| Defectos sembrados detectados | **19/20** | 16/20 |
| Falsas alarmas | **0** | **0** |
| Tiempo total (4 en paralelo) | 15.5 min | **8.7 min** |
| Lectura por documento (mediana) | 24.4 s | **10.4 s** |
| Extracción por documento (mediana) | **10.6 s** | 18.2 s |

**Defectos no detectados**
- Ambas: el comprobante de pago **ilegible** (DEF-06). El OCR "adivinó" un texto con apariencia plausible pero equivocado
  ("BANCO DEL ALTEPLANO", contribuyente inventado) y el modelo lo consideró legible. Riesgo real a explicar en la demo.
- Databricks además: estabilidad con 1 mes de datos (DEF-02) y sin excursiones de temperatura (DEF-08), porque clasificó el
  informe como "Estabilidad del fármaco"; y la disolución fuera de especificación (DEF-17), que el modelo no extrajo.

**Errores de clasificación**
- Snowflake (2): no fueron del modelo. Claude respondió bien, pero el validador de formato de Snowflake rechazó la respuesta
  por una "ó" mal codificada en el valor ("Autorización…"), y la función devolvió vacío. Tropiezo de la plataforma.
- Databricks (12): confundió tipos parecidos (estabilidad del medicamento vs del fármaco; BPF del fármaco vs del
  medicamento), clasificó los 4 oficios de prevención como "Otro" y corrompió un acento ("peri༽ico").

## Diferencias observadas

- **Lectura de escaneados:** Databricks reconoce **firmas manuscritas** como elementos propios (`signature`) y describe sellos;
  Snowflake convierte esas zonas en imágenes y necesitó un segundo paso de OCR para leer el bloque de firmas.
- **Encabezados:** Databricks clasifica el texto de arriba de la página como encabezado; filtrarlo como "ruido" (1.ª corrida)
  quitó títulos clave ("ENVASE SECUNDARIO", "Asunto: Se previene") y bajó la clasificación a 36/54 y la detección a 9/20.
  Lección: no filtrar encabezados en documentos regulatorios.
- **Modelo:** la diferencia de calidad se explica sobre todo por el modelo (Claude en Snowflake vs gpt-oss en Databricks).
- **Diseño:** la IA solo extrae; las reglas deciden y citan la cláusula. Por eso hubo **0 falsas alarmas** en ambas y cada
  hallazgo es explicable.

## Tropiezos de la medición (corregidos)

- El evaluador convertía cláusulas como "5.19" en "5.2" al normalizar números; se corrigió y se recalculó sin reprocesar.
- Primera corrida de Databricks con encabezados filtrados: `fase4/databricks/evaluacion_corrida1_sin_encabezados.json`.
