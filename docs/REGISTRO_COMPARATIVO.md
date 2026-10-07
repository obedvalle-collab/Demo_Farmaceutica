# Registro comparativo Snowflake vs Databricks

Una fila por tarea y plataforma. Las horas son de trabajo efectivo; el costo, en créditos/DBU y su equivalente en USD cuando se conozca.

| Fecha | Fase | Tarea | Plataforma | Horas | Latencia observada | Costo | Tropiezos / notas |
|---|---|---|---|---|---|---|---|
| 2026-10-06 | 0 | Planificación y estructura del proyecto | Ambas | | – | – | Sin recursos creados aún |
| 2026-10-06 | 0 | Investigación (NOM, plazos, DIGIPRiS, herramientas) | Ambas | | – | – | 3 investigaciones en paralelo; varios PDF oficiales de COFEPRIS no se pudieron leer como texto |
| 2026-10-06 | 0 | Perfil CLI `obed_farma` (OAuth en navegador) | Databricks | | < 1 min | 0 | Sin fricción |
| 2026-10-06 | 0 | Crear catálogo `obed_farmaceutica` | Databricks | | 3.8 s (SQL, incluye arranque serverless) | mínimo | `databricks catalogs create` falla con *Default Storage*; **solución:** `CREATE CATALOG` por SQL en un warehouse serverless propio (`farma_wh`, 2X-Small, auto-stop 5 min) |
| 2026-10-06 | 0 | Rol, warehouse, base, monitor de gasto, integración de correo, llave RSA | Snowflake | | – | – | Requiere ACCOUNTADMIN → script `snowflake/sql/00_setup_accountadmin.sql` ejecutado por el usuario. La llave va en `RSA_PUBLIC_KEY_2` porque el espacio 1 está ocupado |
| 2026-10-06 | 0 | Conexión local `obed_farma` (llave RSA) + prueba | Snowflake | | conexión 4.8 s · consulta 0.21 s · Cortex COMPLETE 3.9 s | mínimo | Funciona con rol `FARMA_BUILDER`, warehouse `FARMA_WH`; Cortex responde |
| 2026-10-06 | 0 | Repositorio GitHub | – | | – | 0 | Git no estaba instalado (se instaló con winget); el primer `push` necesita inicio de sesión interactivo en GitHub |
| 2026-10-06 | 0 | Descarga de normas a `normas/` | – | | – | 0 | El enlace de "Reglamento de Insumos" en diputados.gob.mx era en realidad el de Investigación; el RIS vigente (reforma 24/04/2026) se tomó de gob.mx. Dos documentos solo existen como página del DOF (HTML) |
| 2026-10-06 | 1 | Generador de datos ficticios (tablas + 54 PDF + hoja de respuestas) | Local (Python) | | generación completa ≈ 2 s | 0 | Independiente de plataforma. Se leyeron las NOM para citar cláusulas reales. Ajustes de maquetación de PDF (firmas y sellos que saltaban de página) |
| 2026-10-06 | 2 | Leer ~1,000 páginas de normas con IA | Snowflake | | 13.7 min | 3.85 créditos (~$11.5) | `AI_PARSE_DOCUMENT` LAYOUT; sin errores. 3.66 créditos por 1,000 páginas |
| 2026-10-06 | 2 | Leer ~1,000 páginas de normas con IA | Databricks | | 24 min | 37 DBU ($2.59 lista) | `ai_parse_document`; un documento superó los 5 min de espera del cliente (sí terminó en la plataforma) |
| 2026-10-06 | 2 | Partición por cláusula (mismo código) | Snowflake | | 8 s | – | Función Python no admite parámetros opcionales → envoltorio |
| 2026-10-06 | 2 | Partición por cláusula (mismo código) | Databricks | | 28 s | – | Función Python en Unity Catalog devolviendo JSON |
| 2026-10-06 | 2 | Buscador semántico | Snowflake | | 4.3 min | 0.12 créditos (~$0.36) vectorizar; servicio aún sin cargo reportado | Cortex Search: 1 sentencia SQL, se puede pausar. Examen: 12/12 (solo vigentes) |
| 2026-10-06 | 2 | Buscador semántico | Databricks | | 25 min endpoint + 56 min índice | ~$1.20 (endpoint $0.19 + sincronización $0.96 + modelo $0.05) | Vector Search: endpoint cobra mientras exista (se borra al terminar). Solo 1 modelo multilingüe. Examen: 11/12 (solo vigentes) |
| 2026-10-06 | 2 | Warehouse SQL de la fase | Snowflake | | – | 0.59 créditos (~$1.75) | |
| 2026-10-06 | 2 | Warehouse SQL de la fase | Databricks | | – | 2.5 DBU ($1.75 lista) | |
| 2026-10-06 | 2 | **Total Fase 2** | Snowflake | | – | **~4.6 créditos ≈ $13.7** (a ~$3/crédito) | El monitor de gasto solo cuenta el warehouse (0.59/20), **no la IA** |
| 2026-10-06 | 2 | **Total Fase 2** | Databricks | | – | **≈ $5.5** (precio de lista) | Leer PDF ~4× más barato que Snowflake, pero ~2× más lento |
| 2026-10-07 | 2 | Experimento: vectores precalculados con `ai_query` | Databricks | | vectores 18.6 s; índice 17.6 min (≈14 min de espera de aprovisionamiento) | mínimo | Mucho más rápido de calcular, pero calidad 9/12 vs 11/12 de la sincronización administrada |

## Notas por fase

### Fase 0
- Snowflake concentra la configuración inicial en un script de administrador; Databricks la reparte entre CLI (perfil) e interfaz (catálogo).
- El equipo local no tiene `git` ni `snow` CLI; Snowflake se usa con el conector de Python.
