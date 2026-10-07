"""Catálogos fijos: productos, tipos de trámite, requisitos CTD y plantillas de observaciones.

Las cláusulas citadas se verificaron contra el texto de las normas en normas/.
"""

# --------------------------------------------------------------------------------------------
# Productos (ficticios). Fracción IV del art. 226 LGS = requieren receta médica.
# --------------------------------------------------------------------------------------------
PRODUCTOS = [
    # id, DCI / denominación genérica, distintiva, forma farmacéutica, concentración, tipo, área, crónico,
    # registro sanitario (None si no tiene), fecha de registro, presentación
    dict(producto_id="P01", denominacion_generica="Metformina", denominacion_distintiva="Altaformin",
         forma_farmaceutica="Tableta", concentracion="850 mg", tipo_producto="Genérico",
         area_terapeutica="Endocrinología", cronico=True, registro_sanitario="214M2017 SSA",
         fecha_registro="2017-03-14", presentacion="Caja con 30 tabletas"),
    dict(producto_id="P02", denominacion_generica="Atorvastatina", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="20 mg", tipo_producto="Genérico",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario="087M2019 SSA",
         fecha_registro="2019-06-21", presentacion="Caja con 30 tabletas"),
    dict(producto_id="P03", denominacion_generica="Losartán potásico", denominacion_distintiva="Losaltam",
         forma_farmaceutica="Tableta", concentracion="50 mg", tipo_producto="Genérico",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario="352M2021 SSA",
         fecha_registro="2021-11-26", presentacion="Caja con 30 tabletas"),
    dict(producto_id="P04", denominacion_generica="Omeprazol", denominacion_distintiva=None,
         forma_farmaceutica="Cápsula de liberación retardada", concentracion="20 mg",
         tipo_producto="Genérico", area_terapeutica="Gastroenterología", cronico=False,
         registro_sanitario="129M2018 SSA", fecha_registro="2018-01-30", presentacion="Caja con 14 cápsulas"),
    dict(producto_id="P05", denominacion_generica="Amlodipino", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="5 mg", tipo_producto="Genérico",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario="403M2020 SSA",
         fecha_registro="2020-09-08", presentacion="Caja con 30 tabletas"),
    dict(producto_id="P06", denominacion_generica="Clopidogrel", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="75 mg", tipo_producto="Genérico",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario="061M2022 SSA",
         fecha_registro="2022-04-19", presentacion="Caja con 28 tabletas"),
    dict(producto_id="P07", denominacion_generica="Sertralina", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="50 mg", tipo_producto="Genérico",
         area_terapeutica="Psiquiatría", cronico=True, registro_sanitario="298M2023 SSA",
         fecha_registro="2023-12-05", presentacion="Caja con 14 tabletas"),
    dict(producto_id="P08", denominacion_generica="Rosuvastatina", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="10 mg", tipo_producto="Genérico",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario=None,
         fecha_registro=None, presentacion="Caja con 30 tabletas"),
    dict(producto_id="P09", denominacion_generica="Sitagliptina", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="100 mg", tipo_producto="Genérico",
         area_terapeutica="Endocrinología", cronico=True, registro_sanitario=None,
         fecha_registro=None, presentacion="Caja con 28 tabletas"),
    dict(producto_id="P10", denominacion_generica="Adalimumab", denominacion_distintiva="Adalitam",
         forma_farmaceutica="Solución inyectable", concentracion="40 mg/0.4 mL",
         tipo_producto="Biocomparable", area_terapeutica="Reumatología", cronico=True,
         registro_sanitario=None, fecha_registro=None,
         presentacion="Caja con 2 jeringas prellenadas con 0.4 mL"),
    dict(producto_id="P11", denominacion_generica="Trastuzumab", denominacion_distintiva="Trastalam",
         forma_farmaceutica="Solución inyectable", concentracion="440 mg",
         tipo_producto="Biocomparable", area_terapeutica="Oncología", cronico=False,
         registro_sanitario="045M2024 SSA", fecha_registro="2024-08-13",
         presentacion="Caja con frasco ámpula con liofilizado y frasco ámpula con 20 mL de diluyente"),
    dict(producto_id="P12", denominacion_generica="Tefazurán (ALT-417, ficticio)", denominacion_distintiva=None,
         forma_farmaceutica="Tableta", concentracion="40 mg", tipo_producto="Molécula nueva",
         area_terapeutica="Cardiología", cronico=True, registro_sanitario=None,
         fecha_registro=None, presentacion="Caja con 30 tabletas"),
]

FABRICANTES_FARMACO = {
    # proveedores ficticios del principio activo
    "P01": ("Química Fina del Bajío, S.A. de C.V.", "México"),
    "P02": ("Shreya Organics Pvt. Ltd.", "India"),
    "P03": ("Zhejiang Hengli Pharmaceutical Co., Ltd.", "China"),
    "P04": ("Química Fina del Bajío, S.A. de C.V.", "México"),
    "P05": ("Shreya Organics Pvt. Ltd.", "India"),
    "P06": ("Iberquímica Farma, S.L.", "España"),
    "P07": ("Iberquímica Farma, S.L.", "España"),
    "P08": ("Zhejiang Hengli Pharmaceutical Co., Ltd.", "China"),
    "P09": ("Kavya Lifesciences Pvt. Ltd.", "India"),
    "P10": ("BioNorte Biologics GmbH", "Alemania"),
    "P11": ("BioNorte Biologics GmbH", "Alemania"),
    "P12": ("Laboratorios Altamira, S.A. de C.V. (planta de síntesis)", "México"),
}

# --------------------------------------------------------------------------------------------
# Tipos de trámite (homoclaves reales del catálogo COFEPRIS)
# --------------------------------------------------------------------------------------------
TIPOS_TRAMITE = {
    "REG_GEN": dict(homoclave="COFEPRIS-04-004-B", nombre="Registro sanitario de medicamento alopático genérico (fabricación nacional)",
                    familia="Registro nuevo", plazo_resolucion_dias=180, tipo_plazo="naturales", fundamento="RIS art. 166-I"),
    "REG_BIO": dict(homoclave="COFEPRIS-04-004-G", nombre="Registro sanitario de medicamento biotecnológico biocomparable (fabricación nacional)",
                    familia="Registro nuevo", plazo_resolucion_dias=180, tipo_plazo="naturales", fundamento="RIS arts. 166, 177"),
    "REG_NUEVA": dict(homoclave="COFEPRIS-04-004-A", nombre="Registro sanitario de medicamento alopático molécula nueva (fabricación nacional)",
                      familia="Registro nuevo", plazo_resolucion_dias=180, tipo_plazo="naturales", fundamento="RIS art. 166-III"),
    "MOD_SIN": dict(homoclave="COFEPRIS-04-015-A", nombre="Modificación a las condiciones del registro sanitario sin cambio de proceso",
                    familia="Modificación", plazo_resolucion_dias=30, tipo_plazo="hábiles", fundamento="Acuerdo DOF 13/02/2017"),
    "MOD_CON": dict(homoclave="COFEPRIS-04-016-A", nombre="Modificación a las condiciones del registro sanitario con cambio de proceso",
                    familia="Modificación", plazo_resolucion_dias=45, tipo_plazo="hábiles", fundamento="Acuerdo DOF 13/02/2017"),
    "MOD_SITIO": dict(homoclave="COFEPRIS-04-014-A", nombre="Modificación por cambio de sitio de fabricación",
                      familia="Modificación", plazo_resolucion_dias=45, tipo_plazo="hábiles", fundamento="Acuerdo DOF 13/02/2017"),
    "PRORROGA": dict(homoclave="COFEPRIS-04-023-A", nombre="Prórroga del registro sanitario de medicamento alopático o biotecnológico",
                     familia="Prórroga", plazo_resolucion_dias=120, tipo_plazo="naturales", fundamento="RIS art. 190 Bis 6"),
}

DESCRIPCIONES_MODIFICACION = {
    "MOD_SIN": ["Actualización de textos de etiqueta", "Cambio de proveedor del fármaco",
                "Inclusión de presentación comercial", "Actualización de la IPP por seguridad",
                "Cambio de material de envase secundario", "Cambio de especificaciones del producto terminado",
                "Cambio de denominación distintiva"],
    "MOD_CON": ["Cambio en el proceso de granulación", "Cambio de tamaño de lote",
                "Cambio de equipo de compresión de diferente principio de operación"],
    "MOD_SITIO": ["Cambio de sitio de acondicionamiento secundario", "Inclusión de sitio alterno de fabricación"],
}

# --------------------------------------------------------------------------------------------
# Requisitos CTD. aplica: G=genérico, B=biocomparable, N=molécula nueva, P=prórroga, M=modificación
# --------------------------------------------------------------------------------------------
_R = [
    # id, módulo, sección, nombre, norma, cláusula, fundamento, aplica, área, formato
    ("R001", "M1", "1.1", "Formato de solicitud firmado", None, None, "RIS art. 167; LFPA art. 15", "GBNPM", "Asuntos Regulatorios", "PDF"),
    ("R002", "M1", "1.2", "Comprobante de pago de derechos", None, None, "Ley Federal de Derechos art. 195-A", "GBNPM", "Asuntos Regulatorios", "PDF"),
    ("R003", "M1", "1.3.1", "Licencia sanitaria del establecimiento fabricante", None, None, "LGS art. 198", "GBN", "Asuntos Regulatorios", "PDF"),
    ("R004", "M1", "1.3.2", "Instrumento que acredita la representación legal", None, None, "LFPA art. 19", "GBNP", "Asuntos Regulatorios", "PDF"),
    ("R005", "M1", "1.4.1", "Proyecto de etiqueta del envase primario", "NOM-072-SSA1-2012", "5.24", "RIS art. 167 fr. III", "GBNPM", "Asuntos Regulatorios", "PDF"),
    ("R006", "M1", "1.4.1", "Proyecto de etiqueta del envase secundario", "NOM-072-SSA1-2012", "5.21; 6.1", "RIS art. 167 fr. III", "GBNPM", "Asuntos Regulatorios", "PDF"),
    ("R007", "M1", "1.4.2", "Información para prescribir amplia (IPPA)", None, None, "RIS art. 167 fr. II", "GBN", "Asuntos Regulatorios", "Word editable"),
    ("R008", "M1", "1.4.2", "Información para prescribir reducida (IPPR)", None, None, "RIS art. 167 fr. II", "GBN", "Asuntos Regulatorios", "Word editable"),
    ("R009", "M1", "1.5.1", "Documento IMPI de titularidad de patentes o licencia de explotación", None, None, "RIS art. 167 fr. I Bis (reforma DOF 24/04/2026)", "GN", "Asuntos Regulatorios", "PDF"),
    ("R010", "M1", "1.6", "Plan de manejo de riesgos (PMR)", "NOM-220-SSA1-2016", "8.4.1; 8.4.3", "NOM-220-SSA1-2016", "GBNP", "Farmacovigilancia", "PDF"),
    ("R011", "M1", "1.7.1", "Certificado de BPF del medicamento", "NOM-059-SSA1-2015", None, "RIS art. 167 fr. VI", "GBNP", "Calidad", "PDF"),
    ("R012", "M1", "1.7.2", "Certificado de BPF del fármaco", "NOM-164-SSA1-2015", None, "RIS art. 167 fr. VI", "GNP", "Calidad", "PDF"),
    ("R013", "M1", "1.8", "Registro sanitario vigente y modificaciones autorizadas", None, None, "RIS art. 190 Bis 7", "P", "Asuntos Regulatorios", "PDF"),
    ("R014", "M1", "1.9", "Informe periódico de seguridad", "NOM-220-SSA1-2016", "8.2", "NOM-220-SSA1-2016", "BP", "Farmacovigilancia", "PDF"),
    ("R015", "M1", "1.10", "Justificación técnica de la modificación", None, None, "Acuerdo DOF 13/02/2017", "M", "Asuntos Regulatorios", "PDF"),
    ("R020", "M2", "2.3", "Resumen global de calidad", None, None, "ICH M4(R4)", "GBN", "CMC", "PDF"),
    ("R021", "M2", "2.4", "Resumen no clínico", None, None, "ICH M4(R4)", "BN", "Clínico", "PDF"),
    ("R022", "M2", "2.5", "Resumen clínico", None, None, "ICH M4(R4)", "BN", "Clínico", "PDF"),
    ("R030", "M3", "3.2.S.1", "Información general del fármaco", None, None, "ICH M4(R4); RIS art. 167 fr. I a", "GBN", "CMC", "PDF"),
    ("R031", "M3", "3.2.S.2", "Fabricación del fármaco", "NOM-164-SSA1-2015", "10", "RIS art. 167 fr. VI", "GBN", "CMC", "PDF"),
    ("R032", "M3", "3.2.S.4", "Certificado de análisis del fármaco", "NOM-164-SSA1-2015", "11", "RIS art. 167 fr. I a", "GBNM", "Calidad", "PDF"),
    ("R033", "M3", "3.2.S.7", "Estabilidad del fármaco", "NOM-073-SSA1-2015", "6", "RIS art. 167 fr. I b", "GN", "CMC", "PDF"),
    ("R034", "M3", "3.2.P.1", "Descripción y composición del medicamento", None, None, "ICH M4(R4)", "GBN", "CMC", "PDF"),
    ("R035", "M3", "3.2.P.3.5", "Validación del proceso de fabricación", "NOM-059-SSA1-2015", "9.9.2.2.3", "NOM-059-SSA1-2015", "GBNM", "Calidad", "PDF"),
    ("R036", "M3", "3.2.P.3.6", "Validación de limpieza", "NOM-059-SSA1-2015", "9.11", "NOM-059-SSA1-2015", "GB", "Calidad", "PDF"),
    ("R037", "M3", "3.2.P.5", "Certificado de análisis del lote del medicamento", "NOM-059-SSA1-2015", "5.5.1; 12", "NOM-059-SSA1-2015", "GBNP", "Calidad", "PDF"),
    ("R038", "M3", "3.2.P.5.3", "Validación de métodos analíticos", "NOM-059-SSA1-2015", "9.12", "NOM-059-SSA1-2015", "GBNM", "Calidad", "PDF"),
    ("R039", "M3", "3.2.P.7", "Sistema contenedor-cierre", "NOM-073-SSA1-2015", "8.2", "NOM-073-SSA1-2015", "GBNM", "CMC", "PDF"),
    ("R040", "M3", "3.2.P.8", "Estudio de estabilidad del medicamento", "NOM-073-SSA1-2015", "8.1; 8.4; 8.5.1; 10.19", "RIS art. 167 fr. I b", "GBNM", "CMC", "PDF"),
    ("R041", "M3", "3.2.R.1", "Programa de aseguramiento de calidad del producto biotecnológico", "NOM-257-SSA1-2014", "6.1", "NOM-257-SSA1-2014", "B", "Calidad", "PDF"),
    ("R042", "M3", "3.2.R.2", "Caracterización fisicoquímica y biológica comparativa", "NOM-257-SSA1-2014", "10.1", "RIS art. 177", "B", "CMC", "PDF"),
    ("R050", "M4", "4.2", "Estudios no clínicos (farmacología y toxicología)", None, None, "ICH M4(R4)", "BN", "Clínico", "PDF"),
    ("R060", "M5", "5.3.1.2", "Informe del estudio de bioequivalencia", "NOM-177-SSA1-2013", "8.5.2; 9.6.4", "RIS art. 167 fr. V", "G", "Clínico", "PDF"),
    ("R061", "M5", "5.3.1.3", "Perfiles de disolución comparativos", "NOM-177-SSA1-2013", "7.5.5", "RIS art. 167 fr. V", "GM", "CMC", "PDF"),
    ("R062", "M5", "5.3.1.4", "Autorización vigente del Tercero Autorizado", "NOM-177-SSA1-2013", "4.97; 8.11.8", "NOM-177-SSA1-2013", "G", "Clínico", "PDF"),
    ("R063", "M5", "5.3.5.1", "Estudio clínico de biocomparabilidad", "NOM-257-SSA1-2014", "10.1", "RIS art. 177", "B", "Clínico", "PDF"),
    ("R064", "M5", "5.3.5.2", "Estudios clínicos de eficacia y seguridad (fase III)", "NOM-012-SSA3-2012", "6.2", "RIS art. 167 fr. I c", "N", "Clínico", "PDF"),
    ("R065", "M5", "5.3.5.3", "Autorización del protocolo y dictamen del comité de ética", "NOM-012-SSA3-2012", "5.3; 6.1", "Reglamento LGS en materia de Investigación", "BN", "Clínico", "PDF"),
    ("R066", "M5", "5.4", "Opinión del Comité de Moléculas Nuevas / SEPB", "NOM-257-SSA1-2014", "5.1.2; 5.1.3", "RIS art. 166-III", "BN", "Asuntos Regulatorios", "PDF"),
]
REQUISITOS = [dict(zip(["requisito_id", "modulo", "seccion_ctd", "nombre", "norma", "clausula",
                        "fundamento", "aplica", "area_responsable", "formato_requerido"], r)) for r in _R]

APLICA_POR_TRAMITE = {"REG_GEN": "G", "REG_BIO": "B", "REG_NUEVA": "N", "PRORROGA": "P",
                      "MOD_SIN": "M", "MOD_CON": "M", "MOD_SITIO": "M"}

# --------------------------------------------------------------------------------------------
# Plantillas de observaciones de prevención (redacción tipo oficio). peso = frecuencia relativa.
# --------------------------------------------------------------------------------------------
OBSERVACIONES = [
    # requisito, norma, cláusula, texto, severidad, peso, aplica (familias de trámite)
    ("R006", "NOM-072-SSA1-2012", "6.1.4", "El proyecto de etiqueta del envase secundario no incluye la leyenda \"Su venta requiere receta médica\" aplicable a medicamentos de la fracción IV del artículo 226 de la Ley General de Salud.", "Menor", 9, "GBNPM"),
    ("R006", "NOM-072-SSA1-2012", "6.1.6.2", "El proyecto de etiqueta no incluye la leyenda para el reporte de sospechas de reacción adversa.", "Menor", 7, "GBNPM"),
    ("R006", "NOM-072-SSA1-2012", "5.19", "Al tratarse de un tratamiento prolongado de enfermedad crónico-degenerativa, la etiqueta debe incluir la leyenda \"prohibida la venta fraccionada del producto\".", "Menor", 6, "GPM"),
    ("R006", "NOM-072-SSA1-2012", "5.17.2.5", "El domicilio del fabricante declarado en la etiqueta no coincide con el autorizado en el registro sanitario.", "Mayor", 4, "GBPM"),
    ("R006", "NOM-072-SSA1-2012", "5.31.7", "La etiqueta del medicamento biotecnológico biocomparable no presenta las siglas M.B.B. en la superficie principal de exhibición del envase secundario.", "Mayor", 3, "B"),
    ("R005", "NOM-072-SSA1-2012", "5.24.8", "El proyecto de etiqueta del envase primario no indica el espacio para el número de lote.", "Menor", 4, "GBNPM"),
    ("R005", "NOM-072-SSA1-2012", "5.15.1", "La expresión de la fecha de caducidad no se ajusta al formato establecido (mes con al menos tres letras y año con dos dígitos).", "Menor", 4, "GBNPM"),
    ("R006", "NOM-072-SSA1-2012", "5.9", "No se expresa la dosis conforme a lo establecido: \"Dosis: la que el médico señale\".", "Menor", 3, "GBNPM"),
    ("R040", "NOM-073-SSA1-2015", "8.1", "El estudio de estabilidad se realizó en dos lotes; deberá presentar el estudio en al menos tres lotes de producción o piloto.", "Mayor", 6, "GM"),
    ("R040", "NOM-073-SSA1-2015", "8.4", "Los datos de estabilidad a largo plazo presentados no alcanzan el mínimo de 3 meses al momento de la solicitud.", "Mayor", 6, "GM"),
    ("R040", "NOM-073-SSA1-2015", "8.5.1.1", "Se observa cambio significativo en la valoración durante la estabilidad acelerada; deberá presentar el estudio a condición intermedia.", "Mayor", 4, "GM"),
    ("R040", "NOM-073-SSA1-2015", "10.19", "El informe de estabilidad no se encuentra avalado por el responsable sanitario del establecimiento.", "Menor", 5, "GBNM"),
    ("R040", "NOM-073-SSA1-2015", "7.5.6", "No se presenta la evaluación del impacto de excursiones de temperatura fuera de las condiciones de almacenamiento.", "Mayor", 3, "BN"),
    ("R040", "NOM-073-SSA1-2015", "10.17", "No se demuestra que el análisis de las muestras se realizó dentro de los 30 días siguientes a su retiro de las cámaras de estabilidad.", "Menor", 2, "GBNM"),
    ("R060", "NOM-177-SSA1-2013", "9.6.4", "El intervalo de confianza al 90% del cociente de medias geométricas de Cmáx excede el límite de 80-125%; la conclusión de bioequivalencia no está sustentada.", "Crítica", 3, "G"),
    ("R060", "NOM-177-SSA1-2013", "8.5.2", "El número de sujetos de investigación evaluables no se especifica previamente en el protocolo y en el informe.", "Mayor", 2, "G"),
    ("R060", "NOM-177-SSA1-2013", "8.5.6", "Se identifica reemplazo de sujetos de investigación durante el estudio, lo cual no está permitido.", "Crítica", 1, "G"),
    ("R061", "NOM-177-SSA1-2013", "7.5.5", "El factor de similitud f2 calculado es menor a 50 en al menos un medio de disolución; los perfiles no pueden considerarse similares.", "Mayor", 4, "GM"),
    ("R062", "NOM-177-SSA1-2013", "8.11.8", "No se presenta evidencia de la autorización vigente del Tercero Autorizado que realizó la fase clínica.", "Menor", 2, "G"),
    ("R035", "NOM-059-SSA1-2015", "9.9.2.2.3", "La calificación del desempeño del proceso no se realizó con al menos tres lotes consecutivos de tamaño comercial.", "Mayor", 4, "GBM"),
    ("R037", "NOM-059-SSA1-2015", "5.5.1", "El certificado de análisis reporta un resultado fuera de especificación dictaminado como conforme, sin reporte de desviación.", "Crítica", 3, "GBNP"),
    ("R038", "NOM-059-SSA1-2015", "9.12", "No se presenta el informe de validación del método analítico para la prueba de valoración.", "Mayor", 3, "GBNM"),
    ("R011", "NOM-059-SSA1-2015", None, "El certificado de buenas prácticas de fabricación del medicamento no se encuentra vigente.", "Mayor", 3, "GBNP"),
    ("R012", "NOM-164-SSA1-2015", None, "El certificado de buenas prácticas de fabricación del fármaco presentado excede la vigencia de treinta meses (RIS art. 167 fr. VI).", "Mayor", 4, "GNP"),
    ("R010", "NOM-220-SSA1-2016", "8.4.3.1.4", "El plan de manejo de riesgos no incluye el plan de minimización de riesgos.", "Menor", 4, "GBNP"),
    ("R010", "NOM-220-SSA1-2016", "8.4.1.2", "Para la solicitud de prórroga deberá presentar el plan de manejo de riesgos del medicamento.", "Mayor", 3, "P"),
    ("R041", "NOM-257-SSA1-2014", "6.1.3", "El programa de aseguramiento de calidad no incluye el programa de auditorías internas del producto y del proceso.", "Mayor", 2, "B"),
    ("R002", None, None, "El comprobante de pago de derechos es ilegible; deberá presentarlo en forma legible.", "Menor", 3, "GBNPM"),
    ("R004", None, None, "El instrumento que acredita la personalidad del representante legal no se encuentra firmado por el otorgante.", "Menor", 3, "GBNP"),
    ("R009", None, None, "No se presenta el documento emitido por el IMPI que acredite la titularidad de patentes vigentes o la licencia de explotación correspondiente (RIS art. 167 fr. I Bis).", "Mayor", 2, "GN"),
    ("R007", None, None, "La información para prescribir amplia no es congruente con la del medicamento de referencia en las secciones de contraindicaciones.", "Menor", 4, "GBN"),
    ("R015", None, None, "La justificación técnica no describe el impacto del cambio en la calidad del producto.", "Menor", 4, "M"),
    ("R032", "NOM-164-SSA1-2015", "11", "El certificado de análisis del fármaco no corresponde al fabricante declarado en el expediente.", "Mayor", 3, "GBNM"),
    ("R039", "NOM-073-SSA1-2015", "8.2", "El sistema contenedor-cierre del estudio de estabilidad difiere del propuesto para comercialización.", "Mayor", 2, "GBNM"),
]

AREAS = ["Asuntos Regulatorios", "Calidad", "CMC", "Clínico", "Farmacovigilancia"]

ROLES = [
    # rol, área, cantidad
    ("Director(a) de Asuntos Regulatorios", "Dirección", 1),
    ("Gerente de Asuntos Regulatorios", "Asuntos Regulatorios", 1),
    ("Especialista de Asuntos Regulatorios", "Asuntos Regulatorios", 3),
    ("Gerente de Aseguramiento de Calidad", "Calidad", 1),
    ("Analista de Calidad", "Calidad", 2),
    ("Especialista CMC", "CMC", 2),
    ("Gerente Médico", "Clínico", 1),
    ("Especialista Clínico", "Clínico", 1),
    ("Responsable de Farmacovigilancia", "Farmacovigilancia", 1),
    ("Responsable Sanitario", "Calidad", 1),
    ("Representante Legal", "Dirección", 1),
]
