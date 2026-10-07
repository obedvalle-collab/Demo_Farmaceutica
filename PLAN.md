# Obed Farmacéutica — Plan del proyecto

> Estado: **Fase 6 terminada** (2026-10-07). Envío con un botón (Vista 2) y ciclo de prevenciones con alertas por correo (Vista 5) en ambas plataformas (ver `docs/resultados/`). Pendiente al final: prueba con computer use. Siguiente: Fase 7 (vistas restantes).

## 1. Objetivo

Construir una demo de **gestor de expedientes regulatorios** para una **farmacéutica ficticia** que registra medicamentos **genéricos y biosimilares** ante COFEPRIS. Se construye en **Snowflake y en Databricks** con las mismas cuentas que la demo de fraude, pero **totalmente separado** de ella. El fin es documentar la experiencia de construir en cada plataforma: horas, tropiezos, latencias y costos, sus fortalezas y a qué perfil de cliente ofrecer cada una. **No** se trata de decidir cuál es "mejor".

Referencia de inspiración, que **NO se replica**: la app DossierIA para PISA (`PISA_PRUEBA.DOSSIER.DOSSIER_AI_AGENTE_APP`, `DOSSIER_DB`, `REGTECH.COFEPRIS` en Snowflake). En ella solo el chat es real; las otras 4 pestañas tienen datos fijos en el código. Lo útil de ese proyecto es su flujo: NOM-059 partida por cláusula → checklist → análisis de brechas con IA → buscadores → agente.

## 2. El problema que se ataca

1. El expediente (formato CTD, módulos 1 a 5) se sube a **DIGIPRiS**, la plataforma digital de COFEPRIS.
2. Si falta algo, COFEPRIS emite una **prevención**: un oficio con observaciones y un plazo corto para responder. Hay que confirmar el plazo por trámite; la referencia encontrada es 10 días hábiles improrrogables. Si no se responde a tiempo, se desecha.
3. Se corrige, se reenvía y puede volver a observarse. Ese ciclo es lo que hace que un registro tarde meses.
4. En genéricos, ser el primero en registrar tiene un gran valor comercial.

La app debe **reducir las prevenciones antes de enviar** y **acelerar la respuesta cuando llegan**.

### 2.1 Envío con un botón y alertas (agregado el 2026-10-06)

- **Envío:** cuando el expediente está listo, el usuario pulsa **Enviar**. Un agente con *computer use* entra al **portal COFEPRIS simulado** con credenciales de demo (`.env`), sube el paquete CTD y se detiene antes del envío final mostrando la pantalla al usuario; este confirma y se obtiene folio y acuse. No se toca DIGIPRiS real.
- **Detección de prevenciones:** un "vigía" revisa el canal por el que COFEPRIS avisa (correo y/o portal; se confirma en Fase 0), descarga el oficio y lo pasa a la IA.
- **Alertas:** por correo al personal responsable (más aviso en la app), con observación, NOM y cláusula, y fecha límite en días hábiles; recordatorios antes del vencimiento.

Detalle de fases en `docs/FASES.md`; decisiones en `docs/DECISIONES.md`.

## 3. Vistas de la app (se construyen las 10; después se decide qué quitar o agregar)

El núcleo son las vistas 2, 3, 5 y 7.

| # | Vista | Qué hace |
|---|---|---|
| 1 | Portafolio (tablero ejecutivo) | Trámites por producto y etapa, días en COFEPRIS, semáforo de prevenciones por vencer, registros próximos a renovarse (vigencia de 5 años) |
| 2 | **Expediente CTD** | Árbol M1–M5; cada requisito es un espacio con su documento, versión y estatus (faltante, borrador, en revisión, aprobado, enviado, observado); cobertura en % y candado de "listo para envío" |
| 3 | **Bandeja de carga inteligente** | Sube un PDF → la IA lo clasifica, lo asigna a su espacio CTD y extrae metadatos (lote, fechas, firmas, vigencia) → lo valida contra la NOM (etiqueta contra NOM-072, estabilidad contra NOM-073, certificado BPF vigente) |
| 4 | Pre-auditoría ("simulador COFEPRIS") | La IA actúa como dictaminador y predice las prevenciones probables antes del envío, citando la cláusula |
| 5 | **Ciclo de prevenciones** ⭐ | Sube el oficio → la IA separa las observaciones → las liga a documentos y cláusulas → crea tareas con responsable y cuenta regresiva en días hábiles → redacta el borrador del escrito de respuesta → línea de tiempo del trámite |
| 6 | Control de versiones y comparación | Qué cambió entre la versión enviada y la corregida, y si la corrección atiende la observación |
| 7 | **Biblioteca normativa** | NOM reales por cláusula, buscador semántico, aviso de PROY-NOM y actualizaciones |
| 8 | Asistente regulatorio | Chat sobre expediente, normas y estatus con citas obligatorias; no inventa |
| 9 | Analítica de desempeño | Prevenciones más frecuentes por NOM y sección, tiempo de ciclo, aprobación al primer intento, cuellos de botella por área |
| 10 | Gobierno y bitácora | Quién subió, aprobó y envió qué; integridad de datos ALCOA+; permisos por rol |

## 4. Normas reales (DOF, públicas)

**Antes de descargar, confirmar la versión vigente de cada una.**

Todas comparten la misma estructura: Prefacio · 1 Objetivo y campo de aplicación · 2 Referencias · 3 Definiciones · 4 Símbolos · 5+ requisitos numerados por cláusula · Apéndices · Bibliografía · Concordancia · Vigilancia · Vigencia.

| Norma | Tema | Uso en el expediente |
|---|---|---|
| NOM-059-SSA1-2015 | Buenas prácticas de fabricación (BPF) de medicamentos | Certificado de BPF, validaciones, módulo 3 |
| NOM-164-SSA1-2015 | BPF de fármacos (el principio activo) | Proveedor del principio activo, módulo 3 |
| NOM-072-SSA1-2012 | Etiquetado de medicamentos | Proyecto de etiqueta, módulo 1 |
| NOM-073-SSA1-2015 | Estabilidad de fármacos y medicamentos | Estudios de estabilidad, módulo 3 |
| NOM-177-SSA1-2013 | Intercambiabilidad (bioequivalencia) | Genéricos, módulo 5 |
| NOM-257-SSA1-2014 | Medicamentos biotecnológicos | Biosimilares |
| NOM-220-SSA1-2016 | Farmacovigilancia (hay un PROY-NOM de actualización) | Plan de manejo de riesgos, módulo 1 |
| NOM-012-SSA3-2012 | Investigación en seres humanos | Estudios clínicos, módulo 5 |
| Complementarias | Ley General de Salud y Reglamento de Insumos para la Salud (artículos de registro), ICH M4 (CTD), ICH Q1A (estabilidad) | Marco legal y estructura CTD |

## 5. Datos ficticios (las normas son reales; la farmacéutica es inventada)

| Tabla / archivo | Contenido | Volumen |
|---|---|---|
| productos | Portafolio mixto: genéricos (metformina, atorvastatina, losartán), 1–2 biosimilares (adalimumab o trastuzumab), 1 molécula nueva | ~12 |
| tramites | Registro nuevo, modificación y prórroga, con homoclave, fechas, etapa y estatus | ~150 históricos (3 años) + ~10 activos |
| requisitos_ctd | Plantilla CTD más requisitos COFEPRIS por tipo de producto, ligados a NOM y artículo | ~100–150 |
| documentos / versiones | Metadatos e historial de versiones | ~1,500 |
| PDF ficticios | Para los trámites activos: etiquetas, estabilidad, certificados BPF, bioequivalencia, cartas. **Con defectos sembrados a propósito** para que la IA los detecte | ~40–60 |
| prevenciones / observaciones | Oficios ficticios que citan NOM y cláusula | ~400 observaciones históricas + 3–4 oficios activos en PDF |
| respuestas / tareas | Escritos de respuesta, responsables, plazos y cumplimiento | Ligadas a las prevenciones |
| calendario_habil | Días hábiles e inhábiles de México | Para los contadores de plazo |
| usuarios / roles | Asuntos regulatorios, calidad, CMC, clínico, dirección | Para la vista de gobierno |

## 6. Arquitectura (igual en ambas plataformas) — lakehouse

```
PDF (expediente, oficios) + NOM reales
        │  carga a stage (Snowflake) / volume (Databricks)
        ▼
Capa cruda → leer PDF con IA → partir por cláusula o sección
        ▼
Capa limpia: documentos, cláusulas, observaciones, metadatos extraídos (JSON → tablas)
        ▼
Capa de negocio: cobertura CTD, plazos, KPIs, resultados de pre-auditoría
        ▼
IA: 2 buscadores (normas / expediente) · análisis en lenguaje natural · agente con citas
        ▼
App (Streamlit en Snowflake / Databricks Apps) + bitácora y permisos
```

- La mayor parte del volumen es no estructurado (PDF); la app lee la capa estructurada.
- Equivalencias esperadas: AI_PARSE_DOCUMENT ↔ ai_parse_document; Cortex Search ↔ Vector Search; Cortex Analyst ↔ Genie; Cortex Agent ↔ agente en código (el workspace de Databricks no tiene Claude, se usa un modelo abierto); Streamlit in Snowflake ↔ Databricks Apps.

## 7. Aislamiento (nombres propuestos; se crean al aprobar el plan)

| Dónde | Nombre |
|---|---|
| Carpeta local | `Desktop\Obed_Farmaceutica` |
| Snowflake: base de datos / rol / warehouse | `OBED_FARMACEUTICA` / `FARMA_BUILDER` / `FARMA_WH` |
| Databricks: catálogo / perfil CLI | `obed_farmaceutica` / `obed_farma` |
| Registro comparativo | `docs/REGISTRO_COMPARATIVO.md` (horas y tropiezos desde el día 1) |

## 8. Pendientes inmediatos

1. ~~Aprobar el plan de fases~~ → en paralelo, fase por fase (`docs/FASES.md`).
2. ~~Investigar notificaciones y acceso a DIGIPRiS~~ → `docs/INVESTIGACION_FASE0.md`.
3. ~~Confirmar NOM vigentes y descargarlas~~ → `normas/README.md`.
4. ~~Confirmar plazos legales~~ → `docs/INVESTIGACION_FASE0.md` (el plazo de prevención lo fija cada oficio).
5. ~~Conexiones~~ → Snowflake `obed_farma` (llave RSA) y Databricks perfil `obed_farma`.
6. ~~Repositorio~~ → https://github.com/obedvalle-collab/Demo_Farmaceutica
