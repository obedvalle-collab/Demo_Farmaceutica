# Fases del proyecto

> Acordado el 2026-10-06. Las dos plataformas avanzan **en paralelo, fase por fase**: cada fase se hace en Snowflake y en seguida en Databricks, con los mismos datos.

## Cómo trabajamos en cada fase

1. **Explicar**: qué se hará y para qué, en lenguaje claro.
2. **Aprobar**: Obed da el visto bueno antes de construir.
3. **Construir**: primero en Snowflake, luego en Databricks.
4. **Probar**: revisamos juntos el resultado visible de la fase.
5. **Registrar**: horas, tropiezos, latencias y costos en `docs/REGISTRO_COMPARATIVO.md`.
6. **Apagar**: warehouses, compute pools, endpoints y apps que cobran por tiempo.

Las decisiones importantes se anotan en `docs/DECISIONES.md`.

## Carpetas

| Carpeta | Contenido |
|---|---|
| `docs/` | Fases, decisiones y registro comparativo |
| `normas/` | PDF de las NOM descargados del DOF |
| `datos/generador/` | Scripts que generan los datos ficticios |
| `datos/salida/` | Tablas (CSV) y PDF ficticios generados |
| `portal_simulado/` | Portal COFEPRIS simulado (login, carga, folio, acuse, panel del dictaminador) |
| `agente_envio/` | Agente con computer use que entra al portal, sube el paquete y vigila notificaciones |
| `snowflake/` | SQL por fase (`sql/`) y la app Streamlit (`app/`) |
| `databricks/` | Notebooks por fase (`notebooks/`) y la app (`app/`) |

## Fases

### Fase 0 — Preparación
- Conexión propia en Snowflake (`OBED_FARMACEUTICA`, `FARMA_BUILDER`, `FARMA_WH`) y perfil/catálogo en Databricks (`obed_farma`, `obed_farmaceutica`).
- Confirmar en el DOF la versión vigente de cada NOM y descargarlas.
- Confirmar plazos legales por trámite (resolución y desahogo de prevención).
- Investigar cómo opera DIGIPRiS: acceso (usuario, e.firma), si tiene API y **cómo notifica las prevenciones** (portal, correo, ambos).
- Definir dónde corre el agente de computer use y la cuenta/API que usará.
- **Listo cuando:** ambas plataformas responden con la conexión nueva y las preguntas de investigación tienen respuesta escrita en `DECISIONES.md`.

### Fase 1 — Datos ficticios (una sola vez, independiente de la plataforma)
- Tablas: productos, trámites, requisitos CTD, documentos/versiones, prevenciones/observaciones, respuestas/tareas, calendario hábil, usuarios/roles.
- PDF ficticios con defectos sembrados a propósito y oficios de prevención activos.
- **Listo cuando:** `datos/salida/` tiene el paquete completo y una lista de los defectos sembrados (para medir si la IA los detecta).

### Fase 2 — Normas · Vista 7
- Cargar NOM, leerlas con IA, partirlas por cláusula, buscador semántico.
- **Listo cuando:** se puede buscar "estabilidad acelerada" y aparecen las cláusulas correctas de la NOM-073 en ambas plataformas.

### Fase 3 — Capas de datos
- Capa cruda → limpia → negocio (cobertura CTD, plazos en días hábiles, KPIs).
- **Listo cuando:** las tablas de negocio cuadran con los datos ficticios.

### Fase 4 — IA documental · Vista 3
- Subir PDF → clasificar → asignar espacio CTD → extraer metadatos → validar contra la NOM.
- **Listo cuando:** la IA detecta la mayoría de los defectos sembrados (se mide el porcentaje).

### Fase 5 — Expediente y envío con un botón · Vista 2
- Árbol CTD, estatus por requisito, candado de "listo para envío".
- Portal COFEPRIS simulado.
- Botón **Enviar** → el agente con computer use entra al portal con las credenciales de demo, sube el paquete y **se detiene antes del envío final**, mostrando al usuario la pantalla para que confirme. Tras confirmar: folio y acuse.
- **Listo cuando:** un expediente completo se envía de punta a punta con una sola confirmación humana.

### Fase 6 — Prevenciones y alertas · Vista 5 ⭐
- Detección: el "vigía" revisa por dónde avisa COFEPRIS (correo y/o portal; según lo que se confirme en Fase 0) y descarga el oficio.
- La IA separa observaciones, las liga a documento y cláusula, crea tareas con cuenta regresiva y redacta la respuesta.
- Alertas al personal **por correo** (y aviso dentro de la app), más recordatorios de plazo.
- **Listo cuando:** el dictaminador simulado emite una prevención y, sin intervención, el responsable recibe el correo con observación, cláusula y fecha límite.

### Fase 7 — Vistas restantes · Vistas 1, 4, 6, 8, 9, 10
- Portafolio, pre-auditoría, versiones, asistente, analítica, gobierno y bitácora.

### Fase 8 — Cierre comparativo
- Consolidar horas, costos, latencias y tropiezos; fortalezas de cada plataforma y a qué perfil de cliente ofrecerla.
