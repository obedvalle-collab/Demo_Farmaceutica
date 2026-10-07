# Datos ficticios – Laboratorios Altamira

Paquete de datos de la demo, generado **una sola vez** y cargado igual en Snowflake y Databricks.
La empresa, las personas, los folios, los oficios y los certificados son **inventados**. Las NOM, cláusulas,
artículos y homoclaves que se citan son **reales** y se verificaron contra los textos de `normas/`.

## Cómo regenerarlo

```
pip install -r datos/generador/requirements.txt
python datos/generador/main.py
```

La semilla es fija: cada corrida produce exactamente lo mismo. Fecha de referencia de la demo: **06/10/2026**.

## Qué contiene `salida/`

| Ruta | Contenido |
|---|---|
| `tablas/*.csv` | 14 tablas: empresa, productos, tipos de trámite, requisitos CTD, trámites, documentos, versiones, prevenciones, observaciones, tareas, respuestas, usuarios, calendario hábil y bitácora |
| `pdf/<trámite>/` | 54 PDF de los trámites activos (expedientes, oficios de prevención y un escrito de respuesta) |
| `pdf/INDICE.csv` | Lista de todos los PDF con su trámite, sección CTD y número de defectos |
| `defectos_sembrados.csv` | **Hoja de respuestas**: 20 errores puestos a propósito, con norma, cláusula y cómo detectarlos |
| `RESUMEN.md` | Conteos de la última generación |

## Los trámites activos (el corazón de la demo)

| Trámite | Producto | Situación al 06/10/2026 | Para qué sirve en la demo |
|---|---|---|---|
| TR-2026-032 | Sitagliptina 100 mg (genérico) | Expediente en integración, 26 PDF, 11 errores sin detectar | Carga inteligente, pre-auditoría, candado de envío, botón Enviar |
| TR-2026-025 | Adalimumab (biocomparable) | Prevención abierta, 5 observaciones, vence 20/10/2026 | Ciclo de prevenciones, tareas, borrador de respuesta |
| TR-2026-017 | Rosuvastatina 10 mg (genérico) | Prevención abierta, 3 observaciones, vence 15/10/2026 (urgente) | Semáforo de plazos, alertas |
| TR-2026-022 | Losartán 50 mg (prórroga) | Aviso de COFEPRIS **sin abrir**; hay hasta el 12/10/2026 para abrirlo | Vigía de correo, alerta y decisión de abrir |
| TR-2026-029 | Clopidogrel 75 mg (modificación) | Prevención ya respondida, en evaluación | Línea de tiempo y ejemplo de respuesta |
| 5 más | Varios | En evaluación o en integración (solo en tablas) | Portafolio |

## Decisiones de diseño

- Los documentos "de autoridad" (oficios, certificados, registro) llevan la marca de agua **"SIMULADO – NO ES UN DOCUMENTO OFICIAL"**,
  no usan escudos ni logotipos oficiales y los nombres de funcionarios son ficticios.
- Siete PDF van **escaneados** (imagen sin texto, con giro y ruido) para probar la lectura con IA de documentos escaneados; uno es ilegible a propósito.
- Los días inhábiles siguen la Ley Federal del Trabajo más los habituales de la Administración Pública Federal; los periodos vacacionales son aproximados.
