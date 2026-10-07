# Decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-06 | Las dos plataformas avanzan en paralelo, fase por fase | Comparar la misma tarea con los mismos datos y ver diferencias sobre la marcha |
| 2026-10-06 | El envío va a un **portal COFEPRIS simulado**, no a DIGIPRiS real | La demo no debe tocar el portal real ni usar credenciales/e.firma reales |
| 2026-10-06 | El botón Enviar activa un **agente con computer use** que entra al portal simulado y sube el paquete; el envío final lo confirma una persona viendo la pantalla | Mostrar automatización real manteniendo el control humano en el paso irreversible |
| 2026-10-06 | Credenciales del portal simulado en `.env` local (solo de demo, nunca en el repositorio). En la nube se pasan a los gestores de secretos de cada plataforma | Seguridad; además es un punto de comparación entre plataformas |
| 2026-10-06 | Las alertas al personal salen por **correo** (más aviso en la app) | Preferencia de Obed |

| 2026-10-06 | El "vigía" detecta el **correo de aviso de disponibilidad** de DIGIPRiS (Gmail API, dominio en Google Workspace) y alerta de inmediato; abrir el oficio lo decide una persona | Abrir el oficio arranca el plazo legal (ver `INVESTIGACION_FASE0.md`) |
| 2026-10-06 | El plazo de respuesta a una prevención se **extrae de cada oficio**, no es una constante | La regulación no fija una cifra única; mínimo legal 5 días hábiles |
| 2026-10-06 | Vigencia de registro: 5 años; prórrogas de 10 años | Reformas LGS (15/01/2026) y RIS (24/04/2026) |
| 2026-10-06 | Computer use por la API directa de Anthropic; Playwright como respaldo. Navegador en Snowpark Container Services; en Databricks, contenedor externo (Apps no permite instalar navegador) | Ni Cortex ni Databricks confirman soporte de computer use |
| 2026-10-06 | Databricks: warehouse propio `farma_wh` (serverless 2X-Small, auto-stop 5 min); catálogo creado por SQL | El CLI no crea catálogos con Default Storage |
| 2026-10-06 | Snowflake: monitor de gasto `FARMA_MONITOR` de 20 créditos/mes | Evitar sorpresas de costo |

## Resuelto en Fase 0

Las preguntas sobre notificaciones de COFEPRIS, acceso a DIGIPRiS y dónde corre el agente quedaron respondidas en `docs/INVESTIGACION_FASE0.md`. Siguen sin confirmar: términos de uso de DIGIPRiS sobre automatización y el texto exacto del correo de aviso.
