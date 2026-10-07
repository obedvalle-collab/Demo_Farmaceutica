# Obed Farmacéutica

Lee `PLAN.md` antes de cualquier tarea: tiene el objetivo, las vistas, las NOM, los datos ficticios y la arquitectura acordados.

## Reglas del proyecto

- Todo en español. El usuario (Obed, Data IQ) prefiere avanzar por pasos: explicar qué hace algo antes de ejecutarlo y mostrar el plan completo antes de construir. Las explicaciones deben ser claras y no demasiado técnicas.
- **Separación total de la demo de fraude** (`Desktop\Demo_Fraude-main`, base `LOAD_DETECTION`, catálogo `load_detection`, conexión `demo_fraude`): no leer, modificar ni reutilizar sus objetos.
- No tocar los objetos de DossierIA/PISA (`PISA_PRUEBA`, `DOSSIER_DB`, `REGTECH`). Son solo referencia.
- Las NOM son reales (DOF); todo lo de la farmacéutica es ficticio. No usar documentos reales de clientes.
- Registrar horas, tropiezos, latencias y costos por fase en `docs/REGISTRO_COMPARATIVO.md` desde el inicio.
- Recursos que cobran por tiempo encendido (warehouses, compute pools, endpoints de Vector Search, Databricks Apps) se apagan al terminar cada sesión.
- Lo que requiera ACCOUNTADMIN lo ejecuta el usuario en Snowsight: darle SQL listo para copiar, sin placeholders, y explicar qué hace.
- En PowerShell, no usar Remove-Item en comandos; los scripts temporales van en %TEMP%\claude.
- El CLI de Databricks está en WinGet\Packages\Databricks.DatabricksCLI_...; hay que agregarlo al PATH en cada proceso.
