-- =====================================================================
-- Obed Farmacéutica · Fase 0 · Configuración inicial (ejecutar como ACCOUNTADMIN en Snowsight)
-- No toca nada de la demo de fraude: todo lleva nombre FARMA / OBED_FARMACEUTICA.
-- =====================================================================
USE ROLE ACCOUNTADMIN;

-- 1) Rol propio del proyecto ("gafete" con permisos solo sobre este proyecto)
CREATE ROLE IF NOT EXISTS FARMA_BUILDER COMMENT = 'Obed Farmacéutica: rol de construcción';
GRANT ROLE FARMA_BUILDER TO ROLE SYSADMIN;   -- jerarquía recomendada
GRANT ROLE FARMA_BUILDER TO USER OBEDVALLE;

-- 2) Warehouse: el más pequeño, se apaga solo al minuto sin uso y nace apagado
CREATE WAREHOUSE IF NOT EXISTS FARMA_WH
  WAREHOUSE_SIZE = 'XSMALL'
  AUTO_SUSPEND = 60
  AUTO_RESUME = TRUE
  INITIALLY_SUSPENDED = TRUE
  COMMENT = 'Obed Farmacéutica';
GRANT USAGE, OPERATE, MONITOR ON WAREHOUSE FARMA_WH TO ROLE FARMA_BUILDER;

-- 3) Tope de gasto del warehouse: avisa al 75 % y lo suspende al llegar a 20 créditos al mes
CREATE RESOURCE MONITOR IF NOT EXISTS FARMA_MONITOR
  WITH CREDIT_QUOTA = 20
  FREQUENCY = MONTHLY
  START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 75 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND;
ALTER WAREHOUSE FARMA_WH SET RESOURCE_MONITOR = FARMA_MONITOR;

-- 4) Base de datos del proyecto, propiedad del rol FARMA_BUILDER
CREATE DATABASE IF NOT EXISTS OBED_FARMACEUTICA COMMENT = 'Obed Farmacéutica: demo de expedientes regulatorios';
GRANT OWNERSHIP ON DATABASE OBED_FARMACEUTICA TO ROLE FARMA_BUILDER COPY CURRENT GRANTS;
GRANT OWNERSHIP ON SCHEMA OBED_FARMACEUTICA.PUBLIC TO ROLE FARMA_BUILDER COPY CURRENT GRANTS;

-- A partir de aquí la hoja trabaja en el contexto del proyecto (no en el de la demo de fraude)
USE WAREHOUSE FARMA_WH;
USE SCHEMA OBED_FARMACEUTICA.PUBLIC;

-- 5) Permiso para usar las funciones de IA de Cortex (leer PDF, buscador, LLM)
GRANT DATABASE ROLE SNOWFLAKE.CORTEX_USER TO ROLE FARMA_BUILDER;

-- 6) Correo para las alertas (Fase 6). Solo puede enviar a correos verificados de la cuenta.
CREATE NOTIFICATION INTEGRATION IF NOT EXISTS FARMA_EMAIL
  TYPE = EMAIL
  ENABLED = TRUE
  ALLOWED_RECIPIENTS = ('obed.valle@dataiq.com.mx')
  COMMENT = 'Obed Farmacéutica: alertas de prevenciones';
GRANT USAGE ON INTEGRATION FARMA_EMAIL TO ROLE FARMA_BUILDER;

-- 7) Llave nueva para conectarse desde la computadora. Va en el SEGUNDO espacio:
--    el primero (RSA_PUBLIC_KEY) ya está ocupado y no se toca.
ALTER USER OBEDVALLE SET RSA_PUBLIC_KEY_2 = 'MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAz5mprL2tPzyh3i4+qtTst8Aov53SFOY/60pK1/I3TFBAVD1qjRfO5JB84o62//LBk5q3S0ffOPY7POA6fTUyvoWA7eVLszPQulH6nefB3hZkF61f5l6+xQd8yNtrmq7Q6aUfVco9nfT93mbtTrnRnSlb0tQnVZEr8/POpEDXeqO4NCEJmZjD4SO+hswZ9UNnhnuvYk9YZ/69kE99Tyyd3E86w6Q1Dl6lqSP2WM4SJ9sjyxMoDGKLekgilQ1C/zNnJONYkx68MX22O3Z1JkP99yDVofnygorG2YF1yKKkxPVdg10VZPeO+EzTFU13vpCrJSQL4P+fpvXP5ubi+6ZeAwIDAQAB';

-- 8) Verificación: debe mostrar SHA256:ZEgWWaIHVT2f6WIy3IjPNAEAnpCm29uyCJUQoCSSknQ= en RSA_PUBLIC_KEY_2_FP
--    y, en la última consulta, el identificador de la cuenta para la conexión local.
DESC USER OBEDVALLE;
SELECT CURRENT_ORGANIZATION_NAME() || '-' || CURRENT_ACCOUNT_NAME() AS identificador_cuenta;
