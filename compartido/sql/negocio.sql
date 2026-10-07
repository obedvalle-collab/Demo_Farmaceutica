-- =====================================================================================================
-- Capa de NEGOCIO (misma lógica en Snowflake y Databricks). Marcadores: {L} = esquema limpio, {N} = negocio.
-- SQL estándar portable: CASE, DATEDIFF(day, a, b), YEAR, funciones de ventana. Sin funciones propietarias.
-- =====================================================================================================

-- Parámetros de la demo: "hoy" fijo y umbrales del semáforo (días hábiles restantes)
CREATE OR REPLACE TABLE {N}.parametros AS
SELECT CAST('2026-10-06' AS DATE) AS fecha_demo, 5 AS umbral_amarillo, 2 AS umbral_rojo;

-- Índice acumulado de días hábiles: días hábiles en (a, b] = indice(b) - indice(a)
CREATE OR REPLACE VIEW {N}.calendario_indice AS
SELECT fecha, es_habil, motivo_inhabil,
       SUM(CASE WHEN es_habil THEN 1 ELSE 0 END) OVER (ORDER BY fecha ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS indice_habil
FROM {L}.calendario_habil;

-- Cobertura del expediente CTD y candado de "listo para envío"
CREATE OR REPLACE VIEW {N}.cobertura_ctd AS
SELECT t.tramite_id, t.producto, t.tipo_tramite, t.etapa, t.estatus AS estatus_tramite, t.es_activo,
       COUNT(*) AS requisitos,
       SUM(CASE WHEN d.estatus IN ('Aprobado', 'Enviado') THEN 1 ELSE 0 END) AS completos,
       SUM(CASE WHEN d.estatus = 'En revisión' THEN 1 ELSE 0 END) AS en_revision,
       SUM(CASE WHEN d.estatus = 'Borrador' THEN 1 ELSE 0 END) AS borradores,
       SUM(CASE WHEN d.estatus = 'Observado' THEN 1 ELSE 0 END) AS observados,
       SUM(CASE WHEN d.estatus = 'Faltante' THEN 1 ELSE 0 END) AS faltantes,
       ROUND(100.0 * SUM(CASE WHEN d.estatus IN ('Aprobado', 'Enviado') THEN 1 ELSE 0 END) / COUNT(*), 1) AS cobertura_pct,
       CASE WHEN t.fecha_ingreso IS NOT NULL THEN 'Ya enviado'
            WHEN SUM(CASE WHEN d.estatus <> 'Aprobado' THEN 1 ELSE 0 END) = 0 THEN 'Listo para envío'
            ELSE 'Bloqueado' END AS candado_envio
FROM {L}.tramites t
JOIN {L}.documentos d ON d.tramite_id = t.tramite_id
GROUP BY t.tramite_id, t.producto, t.tipo_tramite, t.etapa, t.estatus, t.es_activo, t.fecha_ingreso;

CREATE OR REPLACE VIEW {N}.cobertura_ctd_modulo AS
SELECT tramite_id, modulo, COUNT(*) AS requisitos,
       SUM(CASE WHEN estatus IN ('Aprobado', 'Enviado') THEN 1 ELSE 0 END) AS completos,
       SUM(CASE WHEN estatus = 'Faltante' THEN 1 ELSE 0 END) AS faltantes,
       ROUND(100.0 * SUM(CASE WHEN estatus IN ('Aprobado', 'Enviado') THEN 1 ELSE 0 END) / COUNT(*), 1) AS cobertura_pct
FROM {L}.documentos
GROUP BY tramite_id, modulo;

-- Plazos de prevenciones con semáforo en días hábiles
CREATE OR REPLACE VIEW {N}.plazos_prevenciones AS
WITH base AS (
    SELECT pr.prevencion_id, pr.tramite_id, t.producto, t.tipo_tramite, pr.numero_oficio, pr.tipo, pr.estatus,
           pr.num_observaciones, pr.fecha_emision, pr.fecha_apertura, pr.fecha_limite_apertura,
           pr.fecha_limite_respuesta, pr.fecha_respuesta, pr.plazo_dias_habiles,
           par.fecha_demo, par.umbral_amarillo, par.umbral_rojo,
           CASE WHEN pr.estatus = 'Sin abrir' THEN 'Abrir oficio'
                WHEN pr.estatus = 'Abierta' THEN 'Responder prevención'
                ELSE 'Ninguna' END AS accion_pendiente,
           CASE WHEN pr.estatus = 'Sin abrir' THEN pr.fecha_limite_apertura
                WHEN pr.estatus = 'Abierta' THEN pr.fecha_limite_respuesta END AS fecha_limite_accion
    FROM {L}.prevenciones pr
    JOIN {L}.tramites t ON t.tramite_id = pr.tramite_id
    CROSS JOIN {N}.parametros par),
obs AS (
    SELECT prevencion_id,
           SUM(CASE WHEN estatus IN ('Pendiente', 'En atención', 'Sin conocer') THEN 1 ELSE 0 END) AS observaciones_abiertas
    FROM {L}.observaciones GROUP BY prevencion_id),
tar AS (
    SELECT o.prevencion_id, COUNT(*) AS tareas,
           SUM(CASE WHEN ta.estatus = 'Cerrada' THEN 1 ELSE 0 END) AS tareas_cerradas
    FROM {L}.tareas ta JOIN {L}.observaciones o ON o.observacion_id = ta.observacion_id
    GROUP BY o.prevencion_id),
dias AS (
    SELECT b.*, CASE WHEN b.fecha_limite_accion IS NOT NULL THEN cl.indice_habil - ch.indice_habil END AS dias_habiles_restantes
    FROM base b
    JOIN {N}.calendario_indice ch ON ch.fecha = b.fecha_demo
    LEFT JOIN {N}.calendario_indice cl ON cl.fecha = b.fecha_limite_accion)
SELECT d.prevencion_id, d.tramite_id, d.producto, d.tipo_tramite, d.numero_oficio, d.tipo, d.estatus,
       d.num_observaciones, COALESCE(o.observaciones_abiertas, 0) AS observaciones_abiertas,
       COALESCE(ta.tareas, 0) AS tareas, COALESCE(ta.tareas_cerradas, 0) AS tareas_cerradas,
       d.fecha_emision, d.fecha_apertura, d.fecha_limite_apertura, d.fecha_limite_respuesta, d.fecha_respuesta,
       d.plazo_dias_habiles, d.accion_pendiente, d.fecha_limite_accion, d.dias_habiles_restantes,
       CASE WHEN d.accion_pendiente = 'Ninguna' THEN 'Cerrada'
            WHEN d.dias_habiles_restantes < 0 THEN 'Vencido'
            WHEN d.dias_habiles_restantes <= d.umbral_rojo THEN 'Rojo'
            WHEN d.dias_habiles_restantes <= d.umbral_amarillo THEN 'Amarillo'
            ELSE 'Verde' END AS semaforo
FROM dias d
LEFT JOIN obs o ON o.prevencion_id = d.prevencion_id
LEFT JOIN tar ta ON ta.prevencion_id = d.prevencion_id;

-- Vigencia de registros sanitarios y prórrogas (5 años de registro; pedir prórroga 150 días naturales antes)
CREATE OR REPLACE VIEW {N}.registros_vigencia AS
WITH base AS (
    SELECT pr.producto_id, pr.denominacion_generica || ' ' || pr.concentracion AS producto, pr.registro_sanitario,
           pr.fecha_registro, pr.fecha_vencimiento_registro, pr.fecha_limite_solicitar_prorroga,
           DATEDIFF(day, par.fecha_demo, pr.fecha_vencimiento_registro) AS dias_para_vencimiento,
           DATEDIFF(day, par.fecha_demo, pr.fecha_limite_solicitar_prorroga) AS dias_para_limite_prorroga,
           pt.tramite_id AS prorroga_en_tramite
    FROM {L}.productos pr
    CROSS JOIN {N}.parametros par
    LEFT JOIN (SELECT producto_id, MAX(tramite_id) AS tramite_id FROM {L}.tramites
               WHERE es_activo AND familia = 'Prórroga' GROUP BY producto_id) pt ON pt.producto_id = pr.producto_id
    WHERE pr.registro_sanitario IS NOT NULL)
SELECT b.*,
       CASE WHEN b.prorroga_en_tramite IS NOT NULL THEN 'Prórroga en trámite'
            WHEN b.dias_para_limite_prorroga < 0 THEN 'Fuera de plazo para solicitar prórroga'
            WHEN b.dias_para_limite_prorroga <= 90 THEN 'Preparar prórroga'
            ELSE 'Vigente' END AS estatus_vigencia,
       CASE WHEN b.prorroga_en_tramite IS NOT NULL THEN 'En trámite'
            WHEN b.dias_para_limite_prorroga < 0 THEN 'Rojo'
            WHEN b.dias_para_limite_prorroga <= 90 THEN 'Amarillo'
            ELSE 'Verde' END AS semaforo
FROM base b;

-- Portafolio de trámites activos (tablero ejecutivo)
CREATE OR REPLACE VIEW {N}.portafolio AS
SELECT t.tramite_id, t.producto_id, t.producto, t.homoclave, t.tipo_tramite, t.familia, t.descripcion, t.etapa,
       t.estatus, t.fecha_inicio_integracion, t.fecha_ingreso, t.fecha_objetivo_envio,
       CASE WHEN t.fecha_ingreso IS NOT NULL THEN DATEDIFF(day, t.fecha_ingreso, par.fecha_demo) END AS dias_en_cofepris,
       tt.plazo_resolucion_dias, tt.tipo_plazo,
       c.cobertura_pct, c.faltantes, c.candado_envio,
       pp.accion_pendiente, pp.fecha_limite_accion, pp.dias_habiles_restantes,
       COALESCE(pp.semaforo, 'Sin prevención') AS semaforo_prevencion
FROM {L}.tramites t
JOIN {L}.tipos_tramite tt ON tt.homoclave = t.homoclave
CROSS JOIN {N}.parametros par
LEFT JOIN {N}.cobertura_ctd c ON c.tramite_id = t.tramite_id
LEFT JOIN (SELECT * FROM {N}.plazos_prevenciones WHERE semaforo <> 'Cerrada') pp ON pp.tramite_id = t.tramite_id
WHERE t.es_activo;

-- Indicadores: observaciones más frecuentes por norma y cláusula
CREATE OR REPLACE VIEW {N}.kpi_observaciones_norma AS
SELECT COALESCE(norma, 'Administrativa') AS norma, COALESCE(clausula, '—') AS clausula, seccion_ctd, area_responsable,
       COUNT(*) AS observaciones, COUNT(DISTINCT tramite_id) AS tramites_afectados,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_del_total
FROM {L}.observaciones
GROUP BY COALESCE(norma, 'Administrativa'), COALESCE(clausula, '—'), seccion_ctd, area_responsable;

-- Indicadores: desempeño por año de ingreso y familia de trámite (trámites concluidos)
CREATE OR REPLACE VIEW {N}.kpi_desempeno AS
SELECT YEAR(fecha_ingreso) AS anio, familia,
       COUNT(*) AS concluidos,
       SUM(CASE WHEN resultado = 'Aprobado' THEN 1 ELSE 0 END) AS aprobados,
       SUM(CASE WHEN resultado = 'Aprobado' AND NOT tuvo_prevencion THEN 1 ELSE 0 END) AS aprobados_primer_intento,
       ROUND(100.0 * SUM(CASE WHEN resultado = 'Aprobado' AND NOT tuvo_prevencion THEN 1 ELSE 0 END) / COUNT(*), 1) AS pct_primer_intento,
       SUM(CASE WHEN tuvo_prevencion THEN 1 ELSE 0 END) AS con_prevencion,
       SUM(CASE WHEN resultado IN ('Negado', 'Desechado') THEN 1 ELSE 0 END) AS negados_o_desechados,
       ROUND(AVG(DATEDIFF(day, fecha_ingreso, fecha_resolucion)), 1) AS ciclo_promedio_dias
FROM {L}.tramites
WHERE NOT es_activo
GROUP BY YEAR(fecha_ingreso), familia;

-- Indicadores: atención de tareas por área (cuellos de botella)
CREATE OR REPLACE VIEW {N}.kpi_areas AS
SELECT ta.area, COUNT(*) AS tareas,
       SUM(CASE WHEN ta.estatus = 'Cerrada' THEN 1 ELSE 0 END) AS cerradas,
       SUM(CASE WHEN ta.estatus = 'Vencida' THEN 1 ELSE 0 END) AS vencidas,
       SUM(CASE WHEN ta.estatus IN ('Pendiente', 'En curso') THEN 1 ELSE 0 END) AS abiertas,
       ROUND(AVG(CASE WHEN ta.fecha_cierre IS NOT NULL THEN cc.indice_habil - ca.indice_habil END), 1) AS dias_habiles_promedio_atencion,
       ROUND(100.0 * SUM(CASE WHEN ta.fecha_cierre IS NOT NULL AND ta.fecha_cierre <= ta.fecha_compromiso THEN 1 ELSE 0 END)
             / NULLIF(SUM(CASE WHEN ta.fecha_cierre IS NOT NULL THEN 1 ELSE 0 END), 0), 1) AS pct_cerradas_a_tiempo
FROM {L}.tareas ta
LEFT JOIN {N}.calendario_indice ca ON ca.fecha = ta.fecha_asignacion
LEFT JOIN {N}.calendario_indice cc ON cc.fecha = ta.fecha_cierre
GROUP BY ta.area
