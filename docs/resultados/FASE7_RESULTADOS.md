# Fase 7 – Vistas restantes: resultados (2026-10-07)

La app queda con las 10 vistas del plan, el mismo código de pantalla en ambas plataformas (`app/comun/`) y la lógica
compartida en `compartido/` (`consultas.py`, `versiones.py`, `preauditoria.py`, `asistente.py`, `modelo_semantico.py`,
`sql/fase7.sql`). Cada plataforma solo aporta sus piezas nativas: SQL, IA, buscador, agente y auditoría.

| # | Vista | Qué usa de cada plataforma |
|---|---|---|
| 1 | Portafolio | Solo SQL compartido (vistas de negocio + estado vivo de la app: envíos y prevenciones) |
| 2 | Expediente CTD (+ bandeja, Vista 3) | Fases 4–5 |
| 4 | Pre-auditoría | IA de cada plataforma (`AI_COMPLETE` Claude Sonnet 4.5 / `ai_query` gpt-oss-120b) |
| 5 | Ciclo de prevenciones | Fase 6 |
| 6 | Versiones | IA de cada plataforma + diferencias de texto (difflib) |
| 7 | Biblioteca normativa | Cortex Search / Vector Search (Fase 2) |
| 8 | Asistente | **Cortex Agent** (Cortex Analyst + Cortex Search) / **Genie** + Vector Search con un agente en código |
| 9 | Analítica | Solo SQL compartido |
| 10 | Gobierno y bitácora | SQL compartido (bitácora única y ALCOA+) + auditoría nativa (ACCOUNT_USAGE / tablas de sistema de Unity Catalog) |

## 7.1–7.2 Portafolio y Analítica (solo SQL)

Resultados idénticos fila por fila. Tiempo de las 7 consultas: Snowflake 0.3–4.0 s, Databricks 0.9–5.3 s (la más lenta
en ambas es el portafolio, que encadena varias vistas).

## 7.3 Biblioteca normativa

Buscador con filtro de vigentes/proyectos y por norma. Al abrir una cláusula se muestran su texto completo, sus
subnumerales y, si existe, el mismo numeral en el proyecto de norma (PROY-NOM) o en la modificación publicada.
Respuesta del buscador: Snowflake 0.6–1.0 s; Databricks 0.3–1.2 s (mediana 0.4 s). Examen de la Fase 2 repetido con el índice nuevo: 11/12 en Databricks, igual que antes.
Tropiezo: en Databricks el índice tuvo que recrearse (el endpoint se había borrado para no pagar). El endpoint estuvo
listo en minutos, pero la sincronización inicial volvió a tardar más de una hora.

## 7.4 Versiones: ¿la corrección atiende lo observado?

8 pares versión enviada → versión corregida de la sitagliptina. Además se hizo una **prueba de control**: cada versión
comparada contra sí misma, donde lo correcto es "No atiende".

| | Snowflake (Claude Sonnet 4.5) | Databricks (gpt-oss-120b) |
|---|---|---|
| Correcciones reales: "Atiende" | 8/8 | 8/8 |
| Prueba de control: "No atiende" | **8/8** | 7/8 (dijo "Atiende" en un certificado sin cambios) |
| Tiempo por evaluación (mediana) | 8.5 s | 7.3 s |
| Riesgos nuevos señalados | 0 | 1 falso: "Laboratorios **Albamira**", error de **su lector de PDF** (Snowflake leyó "Altamira") |

## 7.5 Pre-auditoría ("simulador COFEPRIS")

Examen: 3 trámites que tienen un oficio de prevención real en los datos (10 observaciones de COFEPRIS). La IA revisa el
expediente **tal como se envió** (versión 1), con los hallazgos automáticos y el historial de trámites parecidos; el
propio oficio queda fuera de lo que ve.

| | Snowflake | Databricks |
|---|---|---|
| Observaciones anticipadas (misma sección CTD) | **10/10** | 7/10 |
| Con norma y numeral exactos | **7/10** | 6/10 |
| Predicciones totales (más = más ruido) | 27 | **14** |
| Tiempo por trámite | 33–96 s | **22–30 s** |

- Ambas fallan en lo que no está en el texto ni en el historial con el mismo numeral (p. ej. el plan de manejo de
  riesgos que exige la NOM-220 en una prórroga). Snowflake anticipa además las dos observaciones administrativas
  (comprobante ilegible, IPP no congruente).
- **Tropiezo Snowflake:** con instrucciones largas (≈ 18 mil caracteres) y salida grande, `AI_COMPLETE` con esquema
  JSON devolvió `NULL` sin error. Solución: si viene vacío, se repite en texto libre pidiendo el mismo esquema y se lee el
  JSON. Por eso algunos trámites tardan más (dos llamadas).

## 7.6 Asistente regulatorio

Un solo diccionario de datos compartido (`compartido/modelo_semantico.py`: 10 tablas, descripciones, sinónimos,
relaciones, métricas, instrucciones y preguntas de ejemplo) genera la **vista semántica** de Snowflake y el **espacio
Genie** de Databricks. Mismo banco de 8 preguntas con respuesta calculada de los datos (5 de datos, 2 de normas y 1 trampa:
el precio de venta, que no existe en los datos).

| | Snowflake | Databricks |
|---|---|---|
| Cómo se construye | Vista semántica + objeto **AGENT** (2 sentencias SQL, 5 s, al primer intento) | Espacio Genie por API (4 s) + **agente en código** (~80 líneas: gpt-oss-120b con herramientas → Genie y Vector Search) |
| Por qué así | La app de Snowflake (runtime de warehouse) no puede llamar la API REST de agentes; sí la función SQL `DATA_AGENT_RUN` | Agent Bricks (Supervisor) aparece como oferta "legada"; el patrón recomendado es Genie + herramientas |
| Examen (8 preguntas) | **8/8**, mediana 19.6 s | 6/8, mediana 20.4 s |
| Tokens por pregunta | 47–88 mil (el agente carga el diccionario completo; con caché) | ≈ 1.7 mil del orquestador + lo que consume Genie |

Fallas de Databricks: en "registros por renovar con urgencia" eligió el losartán (que ya tiene prórroga en trámite)
en vez de la metformina, y en "días hábiles de la prevención del losartán" buscó solo en las prevenciones detectadas por la
app y concluyó que no existe. También etiquetó como "días hábiles" una columna que son días naturales. Ambas respondieron
bien la pregunta trampa (no inventaron un precio). Nota del examen: gpt-oss escribe guiones y espacios no separables
("NOM‑072"); el calificador se ajustó para normalizarlos y se recalificaron las respuestas guardadas.

## 7.7 Gobierno y bitácora

- **Bitácora única**: 3,849 eventos históricos + todo lo hecho en la app (cargas, envíos, confirmación humana, vigía,
  apertura de oficios, análisis de IA, tareas, alertas, pre-auditorías, evaluaciones), con exportación a CSV.
- **ALCOA+** (idéntico en ambas): atribuible, original, exacto, contemporáneo y perdurable sin incidencias. **331 de
  1,754 aprobaciones las hizo quien cargó el documento** (falla de segregación de funciones, hallazgo de auditoría
  realista que surgió de los datos generados) y 19 versiones siguen sin aprobar.
- **Roles y permisos**: matriz de acciones por puesto + personal.
- **Auditoría de la plataforma**, filtrada solo a esta demo: Snowflake `SHOW GRANTS` + `ACCOUNT_USAGE.QUERY_HISTORY` +
  `ACCESS_HISTORY` (11–13 s); Databricks `SHOW GRANTS` de Unity Catalog + `system.query.history` +
  `system.access.table_lineage` (≈ 15 s). Ambas tienen retraso de minutos a horas.

## Pendiente

- Costo de la fase (IA, agente, Genie, buscador) — se mide al cierre.
