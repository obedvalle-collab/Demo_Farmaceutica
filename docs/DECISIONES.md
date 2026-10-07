# Decisiones

| Fecha | Decisión | Motivo |
|---|---|---|
| 2026-10-06 | Las dos plataformas avanzan en paralelo, fase por fase | Comparar la misma tarea con los mismos datos y ver diferencias sobre la marcha |
| 2026-10-06 | El envío va a un **portal COFEPRIS simulado**, no a DIGIPRiS real | La demo no debe tocar el portal real ni usar credenciales/e.firma reales |
| 2026-10-06 | El botón Enviar activa un **agente con computer use** que entra al portal simulado y sube el paquete; el envío final lo confirma una persona viendo la pantalla | Mostrar automatización real manteniendo el control humano en el paso irreversible |
| 2026-10-06 | Credenciales del portal simulado en `.env` local (solo de demo, nunca en el repositorio). En la nube se pasan a los gestores de secretos de cada plataforma | Seguridad; además es un punto de comparación entre plataformas |
| 2026-10-06 | Las alertas al personal salen por **correo** (más aviso en la app) | Preferencia de Obed |

## Pendientes de investigar (Fase 0)

- ¿Cómo notifica COFEPRIS una prevención? (bandeja de DIGIPRiS, correo al responsable registrado, ambos). De esto depende cómo el "vigía" la detecta.
- ¿DIGIPRiS tiene API? ¿Cómo se autentica (usuario/contraseña, e.firma)?
- ¿Dónde corre el agente de computer use en cada plataforma (Snowpark Container Services / Databricks Apps) o fuera de ellas?
