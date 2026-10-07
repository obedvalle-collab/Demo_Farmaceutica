# Investigación Fase 0

> Fecha: 2026-10-06. Fuentes: documentación oficial de cada proveedor. Lo marcado como "no confirmado" se valida al construir.

## A. Normas y plazos

[C] confirmado en fuente oficial · [S] fuente secundaria · [I] inferido / no confirmado.

### Normas (versión a usar en la demo)

| Norma | Estado | DOF vigente | Fuente |
|---|---|---|---|
| NOM-059-SSA1-2015 | Vigente + **modificación 19/03/2025** (Reliance para biotecnológicos importados) [C] | 05/02/2016; mod. 19/03/2025 | [norma](https://dof.gob.mx/nota_detalle.php?codigo=5424575&fecha=05/02/2016) · [modificación](https://dof.gob.mx/nota_detalle.php?codigo=5752351&fecha=19/03/2025) |
| NOM-164-SSA1-2015 | Vigente, sin PROY conocido [I] | 04/02/2016 | [DOF](https://dof.gob.mx/nota_detalle.php?codigo=5424377&fecha=04/02/2016) |
| NOM-072-SSA1-2012 | Vigente; **PROY-NOM-072-SSA1-2025** en consulta (aviso 05/01/2026) [C] | 21/11/2012 | [norma](https://dof.gob.mx/nota_detalle.php?codigo=5278341&fecha=21/11/2012) · [PROY](https://dof.gob.mx/nota_detalle.php?codigo=5777847&fecha=05/01/2026) |
| NOM-073-SSA1-2015 | Vigente, sin PROY conocido [I] | 07/06/2016 | [DOF](https://dof.gob.mx/nota_detalle.php?codigo=5440183&fecha=07/06/2016) |
| NOM-177-SSA1-2013 | Vigente; **PROY-NOM-177-SSA1-2025** en consulta (aviso 05/01/2026) [C] | 20/09/2013 | [norma](https://dof.gob.mx/nota_detalle.php?codigo=5314833&fecha=20/09/2013) · [PROY](https://dof.gob.mx/nota_detalle.php?codigo=5777848&fecha=05/01/2026) |
| NOM-257-SSA1-2014 | Vigente, sin PROY conocido [I] | 11/12/2014 | [DOF](https://dof.gob.mx/nota_detalle.php?codigo=5375517&fecha=11/12/2014) |
| NOM-220-SSA1-2016 | Vigente + modificación 30/09/2020; **PROY-NOM-220-SSA1-2024** (25/07/2024) sin versión definitiva [C/I] | 19/07/2017; mod. 30/09/2020 | [norma](https://dof.gob.mx/nota_detalle.php?codigo=5490830&fecha=19/07/2017) · [mod.](https://dof.gob.mx/nota_detalle.php?codigo=5601541&fecha=30/09/2020) · [PROY](https://dof.gob.mx/nota_detalle.php?codigo=5734460&fecha=25/07/2024) |
| NOM-012-SSA3-2012 | Vigente, sin PROY conocido [I] | 04/01/2013 | [DOF](https://dof.gob.mx/nota_detalle.php?codigo=5284148&fecha=04/01/2013) |
| Ley General de Salud | Última reforma 15/01/2026: art. 376, registro 5 años y **prórrogas de 10 años** [C título / S detalle] | – | [texto vigente](https://www.diputados.gob.mx/LeyesBiblio/pdf/LGS.pdf) · [reforma](https://dof.gob.mx/nota_detalle.php?codigo=5778298&fecha=15/01/2026) |
| Reglamento de Insumos para la Salud | **Reforma 24/04/2026** (arts. 166, 167, 167-bis, 177, 190 Bis…) [C] | – | [texto](https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LGS_MIS.pdf) · [reforma](https://dof.gob.mx/nota_detalle.php?codigo=5785957&fecha=24/04/2026) |
| ICH M4(R4) / ICH Q1A(R2) | Aplicables; ICH Q1 consolidada en Step 2 [S] | – | [M4](https://www.ema.europa.eu/en/documents/scientific-guideline/ich-guideline-m4-r4-common-technical-document-ctd-registration-pharmaceuticals-human-use_en.pdf) · [Q1A](https://database.ich.org/sites/default/files/Q1A(R2)%20Guideline.pdf) |

### Plazos (para la lógica de la app)

| Tema | Regla | Estado |
|---|---|---|
| Registro genérico | 180 días naturales (RIS 166-I) | [S] |
| Activo no registrado en México | 240 días naturales (RIS 166-II) | [S] |
| Molécula nueva | 180 días tras reunión técnica (RIS 166-III, reforma 2026) | [C] |
| Prevención | Una sola vez; suspende el plazo de resolución; si no se responde, la solicitud **se tiene por no presentada** (RIS 155-156) | [S] |
| Plazo para responder | **Lo fija COFEPRIS en cada oficio**; mínimo 5 días hábiles (LFPA 17-A, RIS 167-bis). No hay cifra única de "10 días" | [S/C] |
| Vigencia del registro | 5 años; prórrogas por 10 años (2026) | [C/S] |
| Solicitar prórroga | A más tardar 150 días naturales antes del vencimiento (RIS 190 Bis 7); manuales dicen "hábiles" | [C] / discrepancia |
| Resolver prórroga | 120 días naturales, afirmativa ficta | [S] |

### Homoclaves para los datos ficticios
COFEPRIS-04-004-A/C (molécula nueva) · 04-004-B/D (genérico) · 04-004-G/H (biocomparable) · 04-014 (cambio de sitio) · 04-015 (modificación sin cambio de proceso) · 04-016 (con cambio de proceso) · 04-023-A/B (prórroga).

**Implicaciones:** el plazo de respuesta se toma del oficio (la IA lo extrae), no de una constante; la vista de portafolio usa 5 años + prórrogas de 10; la biblioteca normativa muestra avisos de PROY-NOM para 072, 177 y 220.

## B. DIGIPRiS

Notación: [OF] fuente oficial · [OF-frag] oficial visto solo en fragmento · [SEC] consultora/prensa · [NC] no confirmado.

| Tema | Hallazgo |
|---|---|
| Trámites en DIGIPRiS | Prórrogas (desde 2022) [OF]; modificaciones menores/moderadas/mayores desde 23-sep-2024 [OF]; registro de medicamentos nuevos en CTD desde 30-sep-2024 [OF]; genéricos y biológicos también migrados [SEC] |
| Acceso | **e.firma vigente** obligatoria para entrar y firmar; la empresa da permisos a personas físicas que firman con su propia e.firma; el trámite inicia solo al firmar y enviar [OF / OF-frag]. Borradores se guardan 90 días [SEC] |
| Formato | CTD en 5 módulos; PDF ≤ 100 MB por archivo (si excede, partes p1, p2…); M1 puede ir escaneado salvo 1.4.1 (Word editable); M2–M5 PDF no escaneado [OF-frag]. [Guía CTD digital](https://www.gob.mx/cms/uploads/attachment/file/945358/23092024_Indicaciones_del_CTD_en_formato_digital_para_el_solicitante__002_.pdf) |
| **Notificación** | COFEPRIS deja el acto (prevención/resolución) **dentro de DIGIPRiS** y manda un **"aviso de disponibilidad"** al correo registrado (remitente notificaciones@cofepris.gob.mx). Hay **5 días hábiles** para abrirlo; al abrirlo se genera acuse y **surte efectos el día hábil siguiente**; si no se abre, se notifica por estrados electrónicos [OF-frag: términos de uso y [FAQ DIGIPRiS](https://www.gob.mx/cms/uploads/attachment/file/847094/Manual_DigiPris_PreguntasFrecuentes.PDF)] |
| Correo como notificación | Desde 27-feb-2026 COFEPRIS/ATDT tienen un formato de autorización de notificación por correo para todos los trámites [OF, [comunicado](https://www.gob.mx/cofepris/es/articulos/cofepris-mejora-servicios-y-plazos-de-atencion-mediante-notificaciones-por-correo-electronico?idiom=es)] |
| Desahogo | Se responde en la misma plataforma; el plazo corre desde que se abre la prevención. Duración específica para medicamentos [NC] → ver investigación de plazos |
| API | No se encontró API pública [NC: parece no existir]. Términos de uso sobre automatización: no se pudieron leer [NC] |
| Decreto 2026 | Prensa reporta máximo 180 días para resolver registros de medicamentos nuevos y prórrogas a 10 años [SEC; verificar en DOF] |

**Implicaciones para la demo**
- El "vigía" detecta el **correo de aviso** → la alerta al personal sale de inmediato.
- Abrir el oficio **arranca el plazo**. La app debe mostrar "tienes hasta [fecha] para abrirlo" y dejar que una persona decida cuándo abrirlo (o abrirlo el agente por instrucción explícita).
- El portal simulado debe imitar: login, carga por módulo CTD con límite de 100 MB, firma simulada, acuse con folio, aviso por correo y acuse de apertura.

## C. Herramientas técnicas (computer use, correo, buzón)

### Computer use
- Herramienta actual de Anthropic: `computer_toolset_20260801`, en GA en la API de Claude (Opus 5.5, Sonnet 5.5, etc.). Es **del lado del cliente**: Claude decide la acción y nuestro código la ejecuta en un navegador/escritorio virtual y le devuelve el screenshot. Referencia: [computer use tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool), [contenedor de referencia](https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo).
- Por Cortex o por Databricks Model Serving: **no confirmado** que acepten computer use → asumir que va por la **API directa de Anthropic**.
- Alternativa más simple y barata: **Playwright** (navegador headless) guiado por Claude.
- Dónde corre el navegador:
  - Snowflake: Snowpark Container Services (imagen Docker en compute pool + External Access Integration). Ojo: el pool cobra mientras está activo; poner `AUTO_SUSPEND_SECS` y suspender a mano.
  - Databricks Apps: no permite instalar paquetes del sistema → Chromium muy probablemente no corre ahí (**no confirmado**). Opción: contenedor externo.

### Correo saliente (alertas)
- Snowflake: `NOTIFICATION INTEGRATION` tipo EMAIL (la crea ACCOUNTADMIN) + `SYSTEM$SEND_EMAIL`. Solo a **usuarios de la cuenta con correo verificado**; acepta HTML; sin adjuntos.
- Databricks: notification destinations (las crea el admin) para Jobs/SQL Alerts; para correo libre, SMTP o Microsoft Graph desde código con secret scope.

### Buzón entrante (detectar avisos de COFEPRIS)
- Recomendado: **Microsoft Graph** (si el correo es M365) con permiso `Mail.Read` limitado a un buzón; alternativa Gmail API. IMAP no recomendado.
- Snowflake: network rule + secret + EAI, en procedimiento programado con TASK. Databricks: secret scope + Job programado.

### Pendientes de confirmar al construir
1. Computer use vía Cortex/Databricks.
2. Chromium dentro de Databricks Apps o del runtime de contenedor de Streamlit.
3. Costo por hora de SPCS y de Databricks Apps.
4. Adjuntos por correo.
