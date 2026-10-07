-- =====================================================================================================
-- Reglas de revisión de la bandeja de carga (misma lógica en Snowflake y Databricks).
-- Entrada: {L}.documentos_extraidos (datos que extrajo la IA de cada PDF). Salida: {N}.hallazgos_ia.
-- La IA solo extrae datos; estas reglas deciden y citan la norma. Marcadores: {L} limpio, {N} negocio.
-- =====================================================================================================
CREATE OR REPLACE VIEW {N}.hallazgos_ia AS
WITH req AS (
    SELECT nombre, MIN(requisito_id) AS requisito_id, MIN(seccion_ctd) AS seccion_ctd
    FROM {L}.requisitos_ctd GROUP BY nombre),
d AS (
    SELECT x.*, r.requisito_id, r.seccion_ctd, p.tipo_producto, p.cronico, p.fabricante_farmaco AS fabricante_declarado,
           t.familia, par.fecha_demo, e.domicilio_planta
    FROM {L}.documentos_extraidos x
    LEFT JOIN req r ON r.nombre = x.tipo_documento
    LEFT JOIN {L}.tramites t ON t.tramite_id = x.tramite_id
    LEFT JOIN {L}.productos p ON p.producto_id = t.producto_id
    CROSS JOIN {N}.parametros par
    CROSS JOIN {L}.empresa e),
reglas AS (
    -- Etiquetado (NOM-072)
    SELECT d.*, 'ETQ-RECETA' AS regla, 'Falta la leyenda "Su venta requiere receta médica"' AS hallazgo,
           'NOM-072-SSA1-2012' AS norma, '6.1.4' AS clausula, '' AS fundamento, 'Menor' AS severidad
    FROM d WHERE tipo_documento = 'Proyecto de etiqueta del envase secundario' AND COALESCE(leyenda_receta_medica, FALSE) = FALSE
    UNION ALL
    SELECT d.*, 'ETQ-FARMACOVIGILANCIA', 'Falta la leyenda para reportar sospechas de reacción adversa',
           'NOM-072-SSA1-2012', '6.1.6.2', '', 'Menor'
    FROM d WHERE tipo_documento = 'Proyecto de etiqueta del envase secundario' AND COALESCE(leyenda_farmacovigilancia, FALSE) = FALSE
    UNION ALL
    SELECT d.*, 'ETQ-VENTA-FRACCIONADA', 'Producto para enfermedad crónica sin la leyenda "prohibida la venta fraccionada"',
           'NOM-072-SSA1-2012', '5.19', '', 'Menor'
    FROM d WHERE tipo_documento = 'Proyecto de etiqueta del envase secundario' AND cronico AND COALESCE(leyenda_venta_fraccionada, FALSE) = FALSE
    UNION ALL
    SELECT d.*, 'ETQ-MBB', 'Biocomparable sin las siglas M.B.B. en el envase secundario',
           'NOM-072-SSA1-2012', '5.31.7', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Proyecto de etiqueta del envase secundario' AND tipo_producto = 'Biocomparable' AND COALESCE(siglas_mbb, FALSE) = FALSE
    UNION ALL
    SELECT d.*, 'ETQ-DOMICILIO', 'El domicilio del fabricante en la etiqueta no coincide con el autorizado (código postal ' || codigo_postal_fabricante || ')',
           'NOM-072-SSA1-2012', '5.17.2.5', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Proyecto de etiqueta del envase secundario' AND codigo_postal_fabricante IS NOT NULL
             AND domicilio_planta NOT LIKE '%' || codigo_postal_fabricante || '%'
    UNION ALL
    -- Certificados de buenas prácticas: vigencia de 30 meses (RIS art. 167 fr. VI)
    SELECT d.*, 'BPF-VIGENCIA', 'Certificado de BPF emitido el ' || CAST(fecha_emision AS STRING) || ': excede la vigencia de 30 meses',
           CASE WHEN tipo_documento LIKE '%fármaco%' THEN 'NOM-164-SSA1-2015' ELSE 'NOM-059-SSA1-2015' END, '',
           'RIS art. 167 fr. VI', 'Mayor'
    FROM d WHERE tipo_documento LIKE 'Certificado de BPF%' AND DATEADD(month, 30, fecha_emision) < fecha_demo
    UNION ALL
    -- Estabilidad (NOM-073)
    SELECT d.*, 'EST-LOTES', 'El estudio de estabilidad incluye ' || CAST(numero_lotes_estudio AS STRING) || ' lotes; se requieren al menos 3',
           'NOM-073-SSA1-2015', '8.1', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Estudio de estabilidad del medicamento' AND numero_lotes_estudio < 3
    UNION ALL
    SELECT d.*, 'EST-LARGO-PLAZO', 'Estabilidad a largo plazo con ' || CAST(meses_largo_plazo AS STRING) || ' meses; mínimo 3 al solicitar el registro',
           'NOM-073-SSA1-2015', '8.4', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Estudio de estabilidad del medicamento' AND familia = 'Registro nuevo' AND meses_largo_plazo < 3
    UNION ALL
    SELECT d.*, 'EST-EXCURSIONES', 'No evalúa excursiones de temperatura de un producto refrigerado',
           'NOM-073-SSA1-2015', '7.5.6', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Estudio de estabilidad del medicamento' AND tipo_producto = 'Biocomparable'
             AND COALESCE(evalua_excursiones_temperatura, FALSE) = FALSE
    UNION ALL
    SELECT d.*, 'EST-FIRMA', 'Informe de estabilidad sin aval (firma) de: ' || firmas_vacias,
           'NOM-073-SSA1-2015', '10.19', '', 'Menor'
    FROM d WHERE tipo_documento = 'Estudio de estabilidad del medicamento' AND n_firmas_vacias > 0
    UNION ALL
    -- Intercambiabilidad (NOM-177)
    SELECT d.*, 'BE-IC90', 'IC 90% de Cmáx ' || CAST(ic90_cmax_inferior AS STRING) || '–' || CAST(ic90_cmax_superior AS STRING) || '% fuera de 80–125% y aun así concluye bioequivalencia',
           'NOM-177-SSA1-2013', '9.6.4', '', 'Crítica'
    FROM d WHERE tipo_documento = 'Informe del estudio de bioequivalencia' AND conclusion_favorable
             AND (ic90_cmax_inferior < 80 OR ic90_cmax_superior > 125)
    UNION ALL
    SELECT d.*, 'PD-F2', 'f2 mínimo de ' || CAST(f2_minimo AS STRING) || ' (< 50) y concluye perfiles similares',
           'NOM-177-SSA1-2013', '7.5.5', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Perfiles de disolución comparativos' AND conclusion_favorable AND f2_minimo < 50
    UNION ALL
    -- Calidad (NOM-059 / NOM-164)
    SELECT d.*, 'COA-FUERA-ESPEC', 'Resultado fuera de especificación dictaminado como conforme: ' || pruebas_fuera_especificacion,
           'NOM-059-SSA1-2015', '5.5.1', '', 'Crítica'
    FROM d WHERE tipo_documento = 'Certificado de análisis del lote del medicamento' AND n_fuera_especificacion > 0 AND conclusion_favorable
    UNION ALL
    SELECT d.*, 'COA-FABRICANTE', 'El certificado de análisis del fármaco lo emite ' || COALESCE(fabricante_farmaco, emisor) || ', distinto del fabricante declarado (' || fabricante_declarado || ')',
           'NOM-164-SSA1-2015', '11', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Certificado de análisis del fármaco'
             AND UPPER(fabricante_declarado) NOT LIKE UPPER(SUBSTR(COALESCE(fabricante_farmaco, emisor), 1, 10)) || '%'
    UNION ALL
    -- Farmacovigilancia (NOM-220) y biotecnológicos (NOM-257)
    SELECT d.*, 'PMR-MINIMIZACION', 'El plan de manejo de riesgos no incluye el plan de minimización de riesgos',
           'NOM-220-SSA1-2016', '8.4.3.1.4', '', 'Menor'
    FROM d WHERE tipo_documento = 'Plan de manejo de riesgos (PMR)' AND LOWER(secciones) NOT LIKE '%minimizaci%'
    UNION ALL
    SELECT d.*, 'PAC-AUDITORIAS', 'El programa de aseguramiento de calidad no incluye el programa de auditorías internas',
           'NOM-257-SSA1-2014', '6.1.3', '', 'Mayor'
    FROM d WHERE tipo_documento = 'Programa de aseguramiento de calidad del producto biotecnológico' AND LOWER(secciones) NOT LIKE '%auditor%'
    UNION ALL
    -- Documentos administrativos
    SELECT d.*, 'ADM-FIRMA', 'Documento sin firma de: ' || firmas_vacias, '', '', 'LFPA art. 19', 'Menor'
    FROM d WHERE tipo_documento = 'Instrumento que acredita la representación legal' AND n_firmas_vacias > 0
    UNION ALL
    SELECT d.*, 'ADM-ILEGIBLE', 'Documento ilegible', '', '',
           CASE WHEN tipo_documento = 'Comprobante de pago de derechos' THEN 'Ley Federal de Derechos art. 195-A' ELSE 'RIS art. 153' END, 'Menor'
    FROM d WHERE es_legible = FALSE OR caracteres_texto < 400)
SELECT tramite_id, archivo, tipo_documento, requisito_id, seccion_ctd, regla, hallazgo, norma, clausula, fundamento,
       severidad, 'Revisión de documento (IA + regla)' AS origen
FROM reglas
UNION ALL
-- Requisitos sin documento en el expediente (dato de la cobertura CTD, no de la IA)
SELECT doc.tramite_id, '', doc.nombre_requisito, doc.requisito_id, doc.seccion_ctd, 'CTD-FALTANTE',
       'No se ha cargado: ' || doc.nombre_requisito, COALESCE(r.norma, ''), COALESCE(r.clausula, ''), r.fundamento,
       'Mayor', 'Cobertura del expediente'
FROM {L}.documentos doc
JOIN (SELECT requisito_id, MIN(norma) AS norma, MIN(clausula) AS clausula, MIN(fundamento) AS fundamento
      FROM {L}.requisitos_ctd GROUP BY requisito_id) r ON r.requisito_id = doc.requisito_id
WHERE doc.estatus = 'Faltante' AND doc.tramite_id IN (SELECT DISTINCT tramite_id FROM {L}.documentos_extraidos)
