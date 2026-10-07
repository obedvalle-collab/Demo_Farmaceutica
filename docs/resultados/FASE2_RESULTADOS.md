# Fase 2 – Biblioteca normativa: resultados (2026-10-06)

Mismo insumo (17 documentos, ~1,000 páginas), mismo código de partición (`compartido/partir_clausulas.py`)
y mismo examen (`compartido/examen_buscador.py`, 12 preguntas redactadas con palabras distintas a las de la norma).

## Tiempos

| Paso | Snowflake | Databricks |
|---|---|---|
| Subir 17 PDF | 18 s (PUT a stage) | 23 s (volume) |
| Leer con IA las ~1,000 páginas | **13.7 min** (`AI_PARSE_DOCUMENT` LAYOUT) | **24 min** (`ai_parse_document` v2.0) |
| · Ley General de Salud (376 pág.) | 4 min 10 s | 3 min 38 s |
| · NOM-059 (84 pág.) | 75 s | 110 s |
| · Reglamento de Investigación (31 pág.) | 25 s | > 5 min (el cliente dejó de esperar; terminó en la plataforma) |
| Partir en cláusulas y fragmentos | 8 s | 28 s |
| Cláusulas / fragmentos obtenidos | 10,055 / 10,517 | 9,987 / 10,484 |
| Encender el servidor de búsqueda | no aplica (servicio administrado) | **25 min** (endpoint de Vector Search) |
| Crear el buscador (vectorizar ~10,500 fragmentos) | **4.3 min** (1.ª vez); 24 s al recrearlo | **56 min** (`qwen3-embedding`, sincronización Delta) |
| Latencia de búsqueda (mediana) | ~0.45 s | ~0.36–0.48 s |

## Calidad del buscador (cláusula exacta entre los 3 primeros resultados)

| Modalidad | Snowflake (arctic-embed-l-v2.0) | Databricks (qwen3-embedding-0.6b, híbrido) |
|---|---|---|
| Todas las normas (incluye PROY-NOM) | 10/12 | 9/12 |
| Solo normas vigentes (filtro por estatus) | **12/12** | **11/12** |
| Norma correcta en top 3 (solo vigentes) | 12/12 | 12/12 |

Fallos:
- **Ambas:** sin filtro, el PROY-NOM-177 "le gana" a la NOM-177 vigente en preguntas de bioequivalencia (textos casi iguales).
  Decisión de producto: el buscador muestra **solo vigentes por omisión** y los proyectos como aviso aparte.
- **Databricks:** "estabilidad acelerada" devolvió 8.4.1 / 8.4 / 8.5.1.2 (vecinas) en lugar de 8.5.1 (la tabla de condiciones).

## Diferencias observadas

- **Lectura con IA:** Databricks clasifica cada elemento (encabezado de página, número de página, título, tabla), lo que
  permite quitar ruido sin reglas; Snowflake entrega markdown por página y el ruido se quita con reglas.
- **Buscador:** Cortex Search es un servicio administrado que se crea con una sola sentencia SQL y se puede **pausar**.
  Vector Search necesita un **endpoint que cobra mientras exista** (no se pausa: se borra al terminar la sesión) y
  su indexación con el modelo multilingüe de pago por uso fue ~13 veces más lenta.
- **Modelos de búsqueda en español:** Snowflake ofrece varios multilingües en su catálogo; en este workspace de
  Databricks solo `qwen3-embedding` es multilingüe (los otros dos son solo inglés).
- **Tropiezos:** Snowflake no acepta parámetros opcionales en funciones Python (se agregó un envoltorio); en Databricks
  una lectura de PDF superó los 5 minutos de espera del cliente.

## Costo real (leído de las vistas de consumo el 2026-10-07)

| Concepto | Snowflake | Databricks (precio de lista) |
|---|---|---|
| Leer 1,052 páginas con IA | 3.85 créditos (~$11.5) | 37 DBU ($2.59) |
| Buscador | 0.12 créditos (~$0.36) | ~$1.20 |
| Warehouse SQL | 0.59 créditos (~$1.75) | 2.5 DBU ($1.75) |
| **Total** | **~4.6 créditos ≈ $13.7** | **≈ $5.5** |

Snowflake a ~$3 USD/crédito (tarifa pública estándar; la tarifa real de la cuenta puede variar). En Databricks se
excluyeron consumos del workspace que no son del proyecto (jobs, Genie, optimización predictiva ≈ $0.4).
Nota: el monitor de gasto de Snowflake (`FARMA_MONITOR`) solo vigila el warehouse; el consumo de IA no cuenta para el tope.

## Experimento: vectores precalculados con `ai_query` (Databricks, 2026-10-07)

| | Sincronización administrada (06/10) | Vectores precalculados (07/10) |
|---|---|---|
| Calcular 10,484 vectores | dentro de la sincronización | **18.6 s** (`ai_query` por lotes) |
| Encender endpoint | 25 min | 23 s (esta vez estuvo listo de inmediato) |
| Índice listo | 56 min | 17.6 min, de los cuales ~14 min fueron espera de aprovisionamiento y ~2.5 min de carga real |
| Examen, solo vigentes | 11/12 | **9/12** |
| Latencia mediana | ~0.4 s | ~0.7 s (incluye vectorizar la pregunta aparte) |

Conclusión: precalcular los vectores elimina el cuello de botella de cómputo (de 56 min a segundos), pero el índice
sigue teniendo una espera fija de aprovisionamiento de ~14–25 min por cada endpoint/índice nuevo, y la calidad bajó
(fallaron NOM-073 8.5.1, NOM-177 7.5.5 y LGS art. 376). Causa probable: el vector de la pregunta se calcula fuera del
índice y la combinación híbrida pondera distinto; no se investigó más. **Recomendación para la demo:** en Databricks,
crear el endpoint al inicio de la sesión (o mantenerlo durante las demostraciones) y usar la sincronización administrada.
