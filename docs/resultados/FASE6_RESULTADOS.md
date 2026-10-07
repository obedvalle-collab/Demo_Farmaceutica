# Fase 6 – Ciclo de prevenciones y alertas: resultados (2026-10-07)

Prueba de punta a punta con el trámite de demostración **TR-2026-032 (Sitagliptina 100 mg)**, ya enviado en la Fase 5.
El dictaminador simulado del portal emite una prevención con 3 observaciones del catálogo y plazo de 10 días hábiles.
Todo lo demás ocurre sin intervención, salvo el clic de "Abrir oficio" (decisión humana, porque abrirlo hace correr el plazo).

## Flujo

1. **Aviso**: el portal deja un correo de aviso en el buzón simulado (`/api/buzon`). El vigía (`agente_envio/robot.py`)
   lo detecta, identifica el folio `DGP-…`, lo liga al trámite y registra el aviso con límite de apertura de 5 días hábiles.
   Se envía la primera alerta por correo al responsable.
2. **Apertura**: desde la Vista 5 el usuario pide "Abrir oficio en el portal"; el robot entra, abre la notificación,
   descarga el oficio PDF y el acuse de notificación.
3. **Análisis con IA** (`compartido/ciclo_prevencion.py`, mismo código en ambas):
   lectura del PDF → separación de observaciones con esquema JSON (`compartido/oficio.py`) → plazo y fecha límite en días
   hábiles (surte efectos el día hábil siguiente) → cada observación ligada a requisito CTD y al texto de la cláusula de la
   NOM (de la capa limpia de normas) → tareas por área con compromiso 3 días hábiles antes del límite → borrador de respuesta.
4. **Alertas**: correo "oficio analizado" con observaciones y fecha límite; recordatorios cuando faltan ≤ 3 días hábiles.

## Resultados

| | Snowflake | Databricks |
|---|---|---|
| Folio / oficio | DGP-2026-72741 · CAS/DERS/7001/2026 | DGP-2026-36706 · CAS/DERS/7002/2026 |
| Aviso detectado por el vigía | 8 s | ≈ 8 s |
| Observaciones separadas | 3/3 con norma, cláusula y sección CTD | 3/3 con norma, cláusula y sección CTD |
| Tareas creadas | 3 (una por observación, con responsable) | 3 |
| Borrador de respuesta | 4,701 caracteres (Claude Sonnet 4.5) | 2,804 caracteres (gpt-oss-120b) |
| Correos de alerta | 3 enviados con `SYSTEM$SEND_EMAIL` (integración de correo) | enviados con una alerta SQL ejecutada por un job |
| Tiempo total del ciclo | **135 s** | 183 s |

Borradores: `fase6_borrador_snowflake.md` y `fase6_borrador_databricks.md`.

## Diferencias de plataforma

- **Correo**: Snowflake lo resuelve con una sola llamada SQL (`SYSTEM$SEND_EMAIL`) a direcciones verificadas.
  Databricks no tiene función de correo en SQL: se usa una alerta SQL basada en consulta, disparada por un job; el job
  (`sql_task`) no admite las alertas v2, hubo que crear la alerta con la API anterior. La app necesita permiso
  `CAN_MANAGE_RUN` sobre el job.
- **Texto libre de la IA**: `AI_COMPLETE` de Snowflake devuelve el texto entrecomillado como JSON → se decodifica.
- **Calidad del borrador**: el de Claude es más completo y formal; ambos dejan marcadores `[PENDIENTE: …]` en lugar de
  afirmar correcciones (en la primera versión el modelo inventaba que ya se había corregido; se endureció la instrucción).

## Vista 5 en la app

Navegación lateral nueva (Expediente CTD / Ciclo de prevenciones). La Vista 5 muestra: selector de prevención,
semáforo de días hábiles restantes (verde > 5, amarillo ≤ 5, rojo ≤ 2), línea de tiempo (aviso, límite para abrir,
oficio abierto, surte efectos, límite para responder), pestañas de Observaciones (con texto de la cláusula),
Tareas (cerrar) y Borrador (editar, guardar, descargar .md), lista de alertas enviadas y botón de recordatorios.
Verificada local (Snowflake) y publicada en ambas plataformas.

## Pendiente

- Costo de la fase (consumo de IA y correo) — medir con `ACCOUNT_USAGE` / tablas de sistema de Databricks.
- Apertura del oficio con computer use (hoy en modo guion): al final, cuando la API de Anthropic tenga créditos.
