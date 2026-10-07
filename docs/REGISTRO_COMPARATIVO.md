# Registro comparativo Snowflake vs Databricks

Una fila por tarea y plataforma. Las horas son de trabajo efectivo; el costo, en créditos/DBU y su equivalente en USD cuando se conozca.

| Fecha | Fase | Tarea | Plataforma | Horas | Latencia observada | Costo | Tropiezos / notas |
|---|---|---|---|---|---|---|---|
| 2026-10-06 | 0 | Planificación y estructura del proyecto | Ambas | | – | – | Sin recursos creados aún |
| 2026-10-06 | 0 | Investigación (NOM, plazos, DIGIPRiS, herramientas) | Ambas | | – | – | 3 investigaciones en paralelo; varios PDF oficiales de COFEPRIS no se pudieron leer como texto |
| 2026-10-06 | 0 | Perfil CLI `obed_farma` (OAuth en navegador) | Databricks | | < 1 min | 0 | Sin fricción |
| 2026-10-06 | 0 | Crear catálogo `obed_farmaceutica` | Databricks | | 3.8 s (SQL, incluye arranque serverless) | mínimo | `databricks catalogs create` falla con *Default Storage*; **solución:** `CREATE CATALOG` por SQL en un warehouse serverless propio (`farma_wh`, 2X-Small, auto-stop 5 min) |
| 2026-10-06 | 0 | Rol, warehouse, base, monitor de gasto, integración de correo, llave RSA | Snowflake | | – | – | Requiere ACCOUNTADMIN → script `snowflake/sql/00_setup_accountadmin.sql` ejecutado por el usuario. La llave va en `RSA_PUBLIC_KEY_2` porque el espacio 1 está ocupado |

## Notas por fase

### Fase 0
- Snowflake concentra la configuración inicial en un script de administrador; Databricks la reparte entre CLI (perfil) e interfaz (catálogo).
- El equipo local no tiene `git` ni `snow` CLI; Snowflake se usa con el conector de Python.
