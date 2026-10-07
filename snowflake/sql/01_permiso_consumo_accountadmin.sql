-- =====================================================================
-- Obed Farmacéutica · Fase 2 · Permiso para LEER el consumo (ejecutar como ACCOUNTADMIN en Snowsight)
-- Solo da permiso de lectura a las vistas de uso de la cuenta (créditos, IA, búsqueda).
-- No permite crear, modificar ni borrar nada.
-- =====================================================================
USE ROLE ACCOUNTADMIN;
GRANT DATABASE ROLE SNOWFLAKE.USAGE_VIEWER TO ROLE FARMA_BUILDER;
