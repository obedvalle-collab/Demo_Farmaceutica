-- =====================================================================================================
-- Fase 6 · Ciclo de prevenciones y alertas (misma lógica en Snowflake y Databricks).
-- Marcadores: {L} limpio, {N} negocio, {A} app. SQL portable.
-- =====================================================================================================

-- Avisos de disponibilidad detectados por el vigía en el buzón de la empresa
CREATE TABLE IF NOT EXISTS {A}.avisos (
    aviso_id STRING, correo_id INT, tramite_id STRING, folio STRING, asunto STRING, recibido_en TIMESTAMP,
    fecha_aviso DATE, fecha_limite_apertura DATE, estatus STRING, actualizado_en TIMESTAMP);

-- Acciones que la app pide al robot (por ahora: abrir el oficio en el portal)
CREATE TABLE IF NOT EXISTS {A}.acciones (
    accion_id STRING, tipo STRING, tramite_id STRING, aviso_id STRING, estatus STRING, solicitado_por STRING,
    solicitado_en TIMESTAMP, resultado STRING, actualizado_en TIMESTAMP);

-- Oficios abiertos y descargados
CREATE TABLE IF NOT EXISTS {A}.oficios (
    oficio_id STRING, aviso_id STRING, tramite_id STRING, folio STRING, numero_oficio STRING, archivo STRING,
    acuse_apertura STRING, fecha_apertura DATE, fecha_surte_efectos DATE, plazo_dias_habiles INT, fecha_limite DATE,
    texto STRING, procesado_en TIMESTAMP);

-- Observaciones separadas por la IA, ligadas a requisito CTD y a la cláusula de la NOM
CREATE TABLE IF NOT EXISTS {A}.observaciones_oficio (
    oficio_id STRING, tramite_id STRING, numero INT, texto STRING, norma STRING, clausula STRING, seccion_ctd STRING,
    requisito_id STRING, area_responsable STRING, texto_clausula STRING);

-- Tareas para atender cada observación
CREATE TABLE IF NOT EXISTS {A}.tareas_oficio (
    tarea_id STRING, oficio_id STRING, tramite_id STRING, numero INT, descripcion STRING, area STRING,
    responsable_id STRING, responsable STRING, fecha_compromiso DATE, estatus STRING, cerrada_en TIMESTAMP);

-- Borrador del escrito de respuesta redactado por la IA
CREATE TABLE IF NOT EXISTS {A}.borradores (
    oficio_id STRING, tramite_id STRING, texto STRING, modelo STRING, generado_en TIMESTAMP);

-- Alertas por correo al personal (cola de salida)
CREATE TABLE IF NOT EXISTS {A}.alertas (
    alerta_id STRING, tipo STRING, tramite_id STRING, referencia STRING, para STRING, asunto STRING, cuerpo STRING,
    creada_en TIMESTAMP, enviada_en TIMESTAMP, canal STRING, error STRING);

-- Responsable por área (primer gerente o especialista del área)
CREATE OR REPLACE VIEW {N}.responsables_area AS
SELECT area, MIN(usuario_id) AS usuario_id, MIN(titulo || ' ' || nombre) AS responsable
FROM {L}.usuarios
WHERE rol LIKE 'Gerente%' OR rol LIKE 'Responsable de%'
GROUP BY area;

-- Seguimiento de prevenciones en curso (en vivo), con semáforo en días hábiles contra la fecha de la demo
CREATE OR REPLACE VIEW {N}.prevenciones_en_curso AS
WITH base AS (
    SELECT a.aviso_id, a.tramite_id, a.folio, a.fecha_aviso, a.fecha_limite_apertura, a.estatus AS estatus_aviso,
           o.oficio_id, o.numero_oficio, o.fecha_apertura, o.fecha_surte_efectos, o.plazo_dias_habiles, o.fecha_limite,
           CASE WHEN o.oficio_id IS NULL THEN 'Abrir oficio' ELSE 'Responder prevención' END AS accion_pendiente,
           CASE WHEN o.oficio_id IS NULL THEN a.fecha_limite_apertura ELSE o.fecha_limite END AS fecha_limite_accion,
           par.fecha_demo, par.umbral_amarillo, par.umbral_rojo
    FROM {A}.avisos a
    LEFT JOIN {A}.oficios o ON o.aviso_id = a.aviso_id
    CROSS JOIN {N}.parametros par),
tar AS (
    SELECT oficio_id, COUNT(*) AS tareas, SUM(CASE WHEN estatus = 'Cerrada' THEN 1 ELSE 0 END) AS tareas_cerradas
    FROM {A}.tareas_oficio GROUP BY oficio_id)
SELECT b.aviso_id, b.tramite_id, t.producto, t.tipo_tramite, b.folio, b.numero_oficio, b.oficio_id, b.estatus_aviso,
       b.fecha_aviso, b.fecha_limite_apertura, b.fecha_apertura, b.fecha_surte_efectos, b.plazo_dias_habiles,
       b.fecha_limite, b.accion_pendiente, b.fecha_limite_accion,
       cl.indice_habil - ch.indice_habil AS dias_habiles_restantes,
       COALESCE(tar.tareas, 0) AS tareas, COALESCE(tar.tareas_cerradas, 0) AS tareas_cerradas,
       CASE WHEN cl.indice_habil - ch.indice_habil < 0 THEN 'Vencido'
            WHEN cl.indice_habil - ch.indice_habil <= b.umbral_rojo THEN 'Rojo'
            WHEN cl.indice_habil - ch.indice_habil <= b.umbral_amarillo THEN 'Amarillo'
            ELSE 'Verde' END AS semaforo
FROM base b
JOIN {L}.tramites t ON t.tramite_id = b.tramite_id
JOIN {N}.calendario_indice ch ON ch.fecha = b.fecha_demo
LEFT JOIN {N}.calendario_indice cl ON cl.fecha = b.fecha_limite_accion
LEFT JOIN tar ON tar.oficio_id = b.oficio_id
