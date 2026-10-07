-- =====================================================================================================
-- Fase 7: resultados de IA que se guardan para no repetir la consulta (misma lógica en ambas plataformas).
-- Marcadores: {L} limpio, {N} negocio, {A} app.
-- =====================================================================================================

-- Vista 6: veredicto de la IA sobre una corrección (versión anterior contra versión nueva)
CREATE TABLE IF NOT EXISTS {A}.comparaciones (
    tramite_id STRING, requisito_id STRING, archivo_anterior STRING, archivo_nuevo STRING, modelo STRING,
    veredicto STRING, resultado STRING, segundos DOUBLE, generado_en TIMESTAMP);

-- Vista 4: pre-auditoría (la IA como dictaminador) por trámite
CREATE TABLE IF NOT EXISTS {A}.preauditorias (
    preauditoria_id STRING, tramite_id STRING, modelo STRING, riesgo STRING, resultado STRING, segundos DOUBLE,
    generado_en TIMESTAMP, generado_por STRING);

-- Pares de versiones de un mismo requisito (la anterior y la siguiente)
CREATE OR REPLACE VIEW {N}.versiones_pares AS
SELECT n.tramite_id, n.requisito_id, d.seccion_ctd, d.nombre_requisito, d.area_responsable,
       a.archivo AS archivo_anterior, a.version AS version_anterior, a.cargado_en AS cargado_anterior,
       n.archivo AS archivo_nuevo, n.version AS version_nueva, n.cargado_en AS cargado_nuevo, n.cargado_por, n.origen
FROM {A}.cargas n
JOIN {A}.cargas a ON a.tramite_id = n.tramite_id AND a.requisito_id = n.requisito_id AND a.version = n.version - 1
JOIN {L}.documentos d ON d.tramite_id = n.tramite_id AND d.requisito_id = n.requisito_id;

-- Vista 10: bitácora única (histórico de la empresa + todo lo que se hizo en la app, incluidos robot e IA)
CREATE OR REPLACE VIEW {N}.bitacora_unificada AS
SELECT b.evento_id, CAST(b.fecha_hora AS TIMESTAMP) AS fecha_hora, b.usuario_id, u.nombre AS usuario, u.rol, b.accion, b.objeto,
       b.tramite_id, b.detalle, b.sha256, 'Histórico' AS origen
FROM {L}.bitacora b LEFT JOIN {L}.usuarios u ON u.usuario_id = b.usuario_id
UNION ALL
SELECT 'APP-C-' || c.tramite_id || '-' || c.requisito_id || '-v' || CAST(c.version AS STRING), c.cargado_en, NULL, c.cargado_por,
       CASE WHEN c.cargado_por = 'demo' THEN 'Carga inicial de la demo' ELSE 'Usuario de la app' END,
       'Carga de documento', c.archivo, c.tramite_id, c.origen || ' · versión ' || CAST(c.version AS STRING), NULL, 'App'
FROM {A}.cargas c
UNION ALL
SELECT 'APP-E1-' || e.envio_id, e.solicitado_en, NULL, e.solicitado_por, 'Usuario de la app', 'Solicitud de envío', e.envio_id,
       e.tramite_id, 'Botón Enviar · modo ' || COALESCE(e.modo, '—'), NULL, 'App'
FROM {A}.envios e
UNION ALL
SELECT 'APP-E2-' || e.envio_id, e.confirmado_en, NULL, e.confirmado_por, 'Usuario de la app', 'Confirmación humana del envío',
       e.envio_id, e.tramite_id, 'Confirmó la pantalla del portal antes de firmar', NULL, 'App'
FROM {A}.envios e WHERE e.confirmado_en IS NOT NULL
UNION ALL
SELECT 'APP-E3-' || e.envio_id, e.enviado_en, NULL, 'Robot de envío', 'Agente', 'Envío a COFEPRIS', e.folio, e.tramite_id,
       'Folio ' || e.folio, e.cadena_acuse, 'App'
FROM {A}.envios e WHERE e.folio IS NOT NULL
UNION ALL
SELECT 'APP-AV-' || a.aviso_id, a.recibido_en, NULL, 'Vigía del buzón', 'Agente', 'Aviso de prevención detectado', a.folio,
       a.tramite_id, a.asunto, NULL, 'App'
FROM {A}.avisos a
UNION ALL
SELECT 'APP-AC-' || x.accion_id, x.solicitado_en, NULL, x.solicitado_por, 'Usuario de la app', 'Solicitud: ' || x.tipo, x.aviso_id,
       x.tramite_id, x.estatus || COALESCE(' · ' || x.resultado, ''), NULL, 'App'
FROM {A}.acciones x
UNION ALL
SELECT 'APP-OF-' || o.oficio_id, o.procesado_en, NULL, 'IA de la plataforma', 'IA', 'Oficio analizado', o.numero_oficio, o.tramite_id,
       'Plazo ' || CAST(o.plazo_dias_habiles AS STRING) || ' días hábiles · límite ' || CAST(o.fecha_limite AS STRING), NULL, 'App'
FROM {A}.oficios o WHERE o.procesado_en IS NOT NULL
UNION ALL
SELECT 'APP-T-' || t.tarea_id, t.cerrada_en, NULL, t.responsable, 'Usuario de la app', 'Tarea cerrada', t.tarea_id, t.tramite_id,
       t.descripcion, NULL, 'App'
FROM {A}.tareas_oficio t WHERE t.cerrada_en IS NOT NULL
UNION ALL
SELECT 'APP-AL-' || l.alerta_id, l.enviada_en, NULL, 'Sistema de alertas', 'Agente', 'Alerta enviada por correo', l.para, l.tramite_id,
       l.asunto, NULL, 'App'
FROM {A}.alertas l WHERE l.enviada_en IS NOT NULL
UNION ALL
SELECT 'APP-PA-' || p.preauditoria_id, p.generado_en, NULL, p.generado_por, 'Usuario de la app', 'Pre-auditoría con IA', p.modelo,
       p.tramite_id, 'Riesgo ' || p.riesgo, NULL, 'App'
FROM {A}.preauditorias p
UNION ALL
SELECT 'APP-VC-' || v.tramite_id || '-' || v.requisito_id || '-' || CAST(v.generado_en AS STRING), v.generado_en, NULL,
       'IA de la plataforma', 'IA', 'Evaluación de corrección', v.archivo_nuevo, v.tramite_id, v.veredicto || ' · ' || v.modelo, NULL, 'App'
FROM {A}.comparaciones v;

-- Vista 10: controles de integridad de datos (ALCOA+) sobre la bitácora histórica.
-- Cada versión de un documento se identifica por su huella (sha256): la carga y su aprobación deben coincidir.
CREATE OR REPLACE VIEW {N}.alcoa_controles AS
WITH b AS (SELECT * FROM {L}.bitacora),
carga AS (SELECT objeto, sha256, MIN(fecha_hora) AS f, MIN(usuario_id) AS quien FROM b
          WHERE accion = 'Carga de documento' GROUP BY objeto, sha256),
apr AS (SELECT objeto, sha256, MIN(fecha_hora) AS f, MIN(usuario_id) AS quien FROM b
        WHERE accion = 'Aprobación de documento' GROUP BY objeto, sha256)
SELECT 'Atribuible' AS principio, 'Cada evento tiene usuario identificado' AS control,
       SUM(CASE WHEN usuario_id IS NULL OR usuario_id = '' THEN 1 ELSE 0 END) AS incidencias, COUNT(*) AS revisados FROM b
UNION ALL
SELECT 'Original', 'Cada carga y aprobación guarda la huella digital (SHA-256) del archivo',
       SUM(CASE WHEN sha256 IS NULL OR LENGTH(sha256) <> 64 THEN 1 ELSE 0 END), COUNT(*)
FROM b WHERE accion IN ('Carga de documento', 'Aprobación de documento')
UNION ALL
SELECT 'Exacto', 'Lo aprobado es exactamente un archivo que se cargó (misma huella)',
       SUM(CASE WHEN carga.objeto IS NULL THEN 1 ELSE 0 END), COUNT(*)
FROM apr LEFT JOIN carga ON carga.objeto = apr.objeto AND carga.sha256 = apr.sha256
UNION ALL
SELECT 'Contemporáneo', 'La aprobación se registró después de la carga',
       SUM(CASE WHEN apr.f < carga.f THEN 1 ELSE 0 END), COUNT(*)
FROM apr JOIN carga ON carga.objeto = apr.objeto AND carga.sha256 = apr.sha256
UNION ALL
SELECT 'Consistente', 'Segregación de funciones: quien aprueba no es quien cargó',
       SUM(CASE WHEN apr.quien = carga.quien THEN 1 ELSE 0 END), COUNT(*)
FROM apr JOIN carga ON carga.objeto = apr.objeto AND carga.sha256 = apr.sha256
UNION ALL
SELECT 'Completo', 'Versiones cargadas que ya tienen aprobación (el resto está en revisión)',
       SUM(CASE WHEN apr.objeto IS NULL THEN 1 ELSE 0 END), COUNT(*)
FROM carga LEFT JOIN apr ON apr.objeto = carga.objeto AND apr.sha256 = carga.sha256
UNION ALL
SELECT 'Perdurable', 'Ningún evento repetido ni sobrescrito (identificador único)',
       COUNT(*) - COUNT(DISTINCT evento_id), COUNT(*) FROM b;
