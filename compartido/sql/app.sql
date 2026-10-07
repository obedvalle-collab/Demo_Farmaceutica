-- =====================================================================================================
-- Estado operativo de la app (lo que cambia con el uso): documentos cargados, cola de envíos y candado.
-- Misma lógica en Snowflake y Databricks. Marcadores: {L} limpio, {N} negocio, {A} app.
-- =====================================================================================================

-- Documentos cargados al expediente (versión 1 de la demo + lo que se suba desde la bandeja)
CREATE TABLE IF NOT EXISTS {A}.cargas (
    tramite_id STRING, requisito_id STRING, archivo STRING, version INT, cargado_en TIMESTAMP,
    cargado_por STRING, origen STRING);

-- Cola de envíos al portal: la app la llena con el botón Enviar; el robot la atiende
CREATE TABLE IF NOT EXISTS {A}.envios (
    envio_id STRING, tramite_id STRING, estatus STRING, solicitado_por STRING, solicitado_en TIMESTAMP,
    captura STRING, resumen_agente STRING, confirmado_por STRING, confirmado_en TIMESTAMP, folio STRING,
    cadena_acuse STRING, enviado_en TIMESTAMP, modo STRING, pasos INT, segundos DOUBLE, costo_usd DOUBLE,
    error STRING, actualizado_en TIMESTAMP);

-- Documento vigente por requisito y su estado efectivo (hallazgos de la IA sobre la última versión)
CREATE OR REPLACE VIEW {N}.expediente_estado AS
WITH vig AS (
    SELECT c.*, ROW_NUMBER() OVER (PARTITION BY tramite_id, requisito_id ORDER BY version DESC, cargado_en DESC) AS rn
    FROM {A}.cargas c),
hall AS (
    SELECT archivo, COUNT(*) AS hallazgos FROM {N}.hallazgos_ia WHERE archivo <> '' GROUP BY archivo)
SELECT d.tramite_id, d.requisito_id, d.modulo, d.seccion_ctd, d.nombre_requisito, d.area_responsable,
       v.archivo, v.version, v.cargado_en, v.origen,
       COALESCE(h.hallazgos, 0) AS hallazgos_abiertos,
       CASE WHEN v.archivo IS NULL AND d.estatus = 'Faltante' THEN 'Faltante'
            WHEN v.archivo IS NULL THEN d.estatus
            WHEN COALESCE(h.hallazgos, 0) > 0 THEN 'Con hallazgos'
            ELSE 'Validado' END AS estatus_efectivo
FROM {L}.documentos d
LEFT JOIN vig v ON v.tramite_id = d.tramite_id AND v.requisito_id = d.requisito_id AND v.rn = 1
LEFT JOIN hall h ON h.archivo = v.archivo;

-- Candado de "listo para envío" con el estado efectivo del expediente
CREATE OR REPLACE VIEW {N}.candado_envio AS
SELECT e.tramite_id, t.producto, t.homoclave, t.tipo_tramite, t.fecha_ingreso,
       COUNT(*) AS requisitos,
       SUM(CASE WHEN e.estatus_efectivo IN ('Validado', 'Aprobado', 'Enviado') THEN 1 ELSE 0 END) AS completos,
       SUM(CASE WHEN e.estatus_efectivo = 'Con hallazgos' THEN 1 ELSE 0 END) AS con_hallazgos,
       SUM(CASE WHEN e.estatus_efectivo = 'Faltante' THEN 1 ELSE 0 END) AS faltantes,
       SUM(e.hallazgos_abiertos) AS hallazgos_abiertos,
       ROUND(100.0 * SUM(CASE WHEN e.estatus_efectivo IN ('Validado', 'Aprobado', 'Enviado') THEN 1 ELSE 0 END) / COUNT(*), 1) AS cobertura_pct,
       CASE WHEN t.fecha_ingreso IS NOT NULL THEN 'Ya enviado'
            WHEN MAX(env.envio_id) IS NOT NULL THEN 'Envío en curso o enviado'
            WHEN SUM(CASE WHEN e.estatus_efectivo IN ('Validado', 'Aprobado') THEN 0 ELSE 1 END) = 0 THEN 'Listo para envío'
            ELSE 'Bloqueado' END AS candado
FROM {N}.expediente_estado e
JOIN {L}.tramites t ON t.tramite_id = e.tramite_id
LEFT JOIN (SELECT tramite_id, MAX(envio_id) AS envio_id FROM {A}.envios WHERE estatus <> 'Cancelado' GROUP BY tramite_id) env
       ON env.tramite_id = e.tramite_id
GROUP BY e.tramite_id, t.producto, t.homoclave, t.tipo_tramite, t.fecha_ingreso
