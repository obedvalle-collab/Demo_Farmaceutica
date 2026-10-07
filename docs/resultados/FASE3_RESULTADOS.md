# Fase 3 – Capas de datos: resultados (2026-10-07)

Mismos CSV (14 tablas), misma conversión de tipos (`compartido/esquema_tablas.py`), mismos 98 controles de calidad
(`compartido/capas.py`) y **el mismo archivo SQL de negocio** (`compartido/sql/negocio.sql`) en ambas plataformas.

## Tiempos

| Paso | Snowflake | Databricks |
|---|---|---|
| Capa cruda (14 tablas desde CSV) | 44 s (PUT + COPY INTO) | 89 s (volume + `read_files`) |
| Subir 54 PDF de expedientes | 34 s (stage) | 25 s (volume) |
| Capa limpia + 98 controles de calidad | 31 s | 67 s |
| Capa de negocio (9 objetos) | 7.6 s | 12.9 s |
| Consultar las 8 vistas | 10 s (0.3–3.5 s c/u; caché de resultados) | 16 s (1.1–5.1 s c/u) |

## Calidad y consistencia

- **98/98 controles en OK** en ambas: llaves únicas y no nulas, 10 llaves foráneas, conversiones de tipo sin pérdida y filas completas.
- **Las 8 vistas de negocio salieron idénticas renglón por renglón** entre plataformas (ver `fase3/snowflake` y `fase3/databricks`).
- El SQL de negocio es 100% portable (CASE, `DATEDIFF(day, a, b)`, `YEAR`, funciones de ventana): no hizo falta ninguna adaptación.
  Solo la conversión de tipos difiere: `TRY_TO_DATE`/`TRY_TO_BOOLEAN` en Snowflake vs `try_cast` en Databricks.

## Vistas de negocio

| Vista | Para qué pantalla | Filas |
|---|---|---|
| `cobertura_ctd`, `cobertura_ctd_modulo` | Expediente CTD (candado de envío) | 160 / 423 |
| `plazos_prevenciones` | Ciclo de prevenciones (semáforo en días hábiles) | 87 |
| `registros_vigencia` | Portafolio (vencimientos y prórrogas) | 8 |
| `portafolio` | Tablero ejecutivo | 10 |
| `kpi_observaciones_norma`, `kpi_desempeno`, `kpi_areas` | Analítica de desempeño | 32 / 9 / 5 |

Parámetros en `negocio.parametros`: fecha de la demo **06/10/2026** y umbrales del semáforo (amarillo ≤ 5, rojo ≤ 2 días hábiles).

## Semáforos según la fecha de la demo

| | 06/10/2026 | 13/10/2026 |
|---|---|---|
| Losartán – abrir oficio (límite 12/10) | Amarillo (4 días) | **Vencido** (se notifica por estrados) |
| Rosuvastatina – responder (límite 15/10) | Verde (7 días) | **Rojo** (2 días) |
| Adalimumab – responder (límite 20/10) | Verde (10 días) | Amarillo (5 días) |
| Metformina – pedir prórroga (límite 15/10) | Amarillo (9 días) | Amarillo (2 días) |

## Hallazgos

- La capa de negocio detectó un error del generador de datos: Metformina y Omeprazol aparecían con registro vencido
  porque su primera prórroga (2022–2023) quedó fuera de la historia generada. Se corrigió en `gen_tablas.py`.
- Snowflake respondió consultas repetidas desde su caché de resultados sin encender el warehouse.
- Los PDF ahora se generan idénticos byte a byte en cada corrida (fecha fija y ruido con semilla).
