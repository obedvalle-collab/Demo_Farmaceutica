"""Consultas de las vistas de lectura (Fase 7): Portafolio (Vista 1) y Analítica (Vista 9).

Mismo SQL en ambas plataformas; cada una solo aporta q(sql, params) y los nombres de esquema L / N / A
(ver ciclo_prevencion.py).
"""


class Consultas:
    L = N = A = ""

    # ------------------------------------------------------------------------------- Vista 1 · Portafolio
    def portafolio(self):
        """Trámites activos. Lo que pasó en la app manda sobre los datos históricos:
        un envío con folio (Fase 5) y una prevención viva (Fase 6)."""
        return self.q(f"""
            SELECT p.tramite_id, p.producto, p.familia, p.tipo_tramite, p.descripcion,
                   CASE WHEN v.tramite_id IS NOT NULL THEN 'Prevención – ' || LOWER(v.accion_pendiente)
                        WHEN e.folio IS NOT NULL THEN 'Enviado a COFEPRIS · folio ' || e.folio ELSE p.etapa END AS etapa,
                   CASE WHEN e.folio IS NOT NULL THEN 'En evaluación' ELSE p.estatus END AS estatus,
                   COALESCE(p.fecha_ingreso, CAST(e.enviado_en AS DATE)) AS fecha_ingreso, p.fecha_objetivo_envio,
                   COALESCE(p.dias_en_cofepris, CASE WHEN e.enviado_en IS NULL THEN NULL
                                                     WHEN CAST(e.enviado_en AS DATE) < par.fecha_demo
                                                     THEN DATEDIFF(day, CAST(e.enviado_en AS DATE), par.fecha_demo) ELSE 0 END) AS dias_en_cofepris, p.plazo_resolucion_dias, p.tipo_plazo,
                   p.cobertura_pct, p.faltantes, p.candado_envio,
                   COALESCE(v.accion_pendiente, p.accion_pendiente) AS accion_pendiente,
                   COALESCE(v.fecha_limite_accion, p.fecha_limite_accion) AS fecha_limite_accion,
                   COALESCE(v.dias_habiles_restantes, p.dias_habiles_restantes) AS dias_habiles_restantes,
                   COALESCE(v.semaforo, p.semaforo_prevencion) AS semaforo_prevencion
            FROM {self.N}.portafolio p
            CROSS JOIN {self.N}.parametros par
            LEFT JOIN (SELECT tramite_id, MAX(folio) AS folio, MAX(enviado_en) AS enviado_en FROM {self.A}.envios
                       WHERE folio IS NOT NULL GROUP BY tramite_id) e ON e.tramite_id = p.tramite_id
            LEFT JOIN (SELECT * FROM (SELECT x.*, ROW_NUMBER() OVER (PARTITION BY tramite_id ORDER BY fecha_aviso DESC) AS rn
                                      FROM {self.N}.prevenciones_en_curso x) z WHERE rn = 1) v ON v.tramite_id = p.tramite_id
            ORDER BY CASE COALESCE(v.semaforo, p.semaforo_prevencion)
                       WHEN 'Vencido' THEN 0 WHEN 'Rojo' THEN 1 WHEN 'Amarillo' THEN 2 WHEN 'Verde' THEN 3 ELSE 4 END,
                     p.tramite_id""")

    def registros_vigencia(self):
        return self.q(f"""SELECT producto, registro_sanitario, fecha_vencimiento_registro, fecha_limite_solicitar_prorroga,
                                 dias_para_limite_prorroga, prorroga_en_tramite, estatus_vigencia, semaforo
                          FROM {self.N}.registros_vigencia ORDER BY dias_para_limite_prorroga""")

    # ------------------------------------------------------------------------------- Vista 9 · Analítica
    def obs_por_norma(self):
        return self.q(f"""SELECT norma, SUM(observaciones) AS observaciones, SUM(tramites_afectados) AS tramites
                          FROM {self.N}.kpi_observaciones_norma GROUP BY norma ORDER BY 2 DESC""")

    def obs_top_clausulas(self, n=12):
        return self.q(f"""SELECT norma, clausula, seccion_ctd, area_responsable, observaciones, tramites_afectados, pct_del_total
                          FROM {self.N}.kpi_observaciones_norma WHERE norma <> 'Administrativa'
                          ORDER BY observaciones DESC, norma, clausula LIMIT {int(n)}""")

    def obs_por_seccion(self):
        return self.q(f"""SELECT SUBSTR(seccion_ctd, 1, 1) AS modulo, seccion_ctd, SUM(observaciones) AS observaciones
                          FROM {self.N}.kpi_observaciones_norma WHERE seccion_ctd IS NOT NULL
                          GROUP BY SUBSTR(seccion_ctd, 1, 1), seccion_ctd ORDER BY 3 DESC""")

    def desempeno(self):
        return self.q(f"SELECT * FROM {self.N}.kpi_desempeno ORDER BY anio, familia")

    def areas(self):
        return self.q(f"SELECT * FROM {self.N}.kpi_areas ORDER BY abiertas DESC, vencidas DESC")

    # ------------------------------------------------------------------------------- Vista 7 · Biblioteca normativa
    def _crudo(self):
        return self.L.rsplit(".", 1)[0] + ".crudo"

    def catalogo_normas(self):
        return self.q(f"""SELECT c.clave AS norma, c.titulo, c.tipo, c.estatus, c.fecha_dof, c.norma_relacionada, c.fuente,
                                 COUNT(n.clausula_id) AS clausulas
                          FROM {self._crudo()}.normas_catalogo c
                          LEFT JOIN {self.L}.normas_clausulas n ON n.norma = c.clave
                          GROUP BY c.clave, c.titulo, c.tipo, c.estatus, c.fecha_dof, c.norma_relacionada, c.fuente
                          ORDER BY COALESCE(c.norma_relacionada, c.clave), c.tipo""")

    def clausula(self, clausula_id):
        """Texto completo de la cláusula, sus subnumerales directos y, si existe, el mismo numeral en el proyecto
        de norma o en la modificación publicada (aviso de actualización)."""
        c = self.q(f"""SELECT clausula_id, norma, titulo_norma, tipo, estatus, numeral, titulo, contexto, texto, modificada_por
                       FROM {self.L}.normas_clausulas WHERE clausula_id = :c""", {"c": clausula_id})
        if not c:
            return None
        c = c[0]
        c["hijas"] = self.q(f"""SELECT numeral, titulo, texto FROM {self.L}.normas_clausulas
                                WHERE norma = :n AND numeral_padre = :u ORDER BY orden""", {"n": c["norma"], "u": c["numeral"]})
        c["relacionadas"] = self.q(f"""
            SELECT n.norma, n.tipo, n.estatus, n.numeral, n.titulo, n.texto, k.fecha_dof
            FROM {self.L}.normas_clausulas n
            JOIN {self._crudo()}.normas_catalogo k ON k.clave = n.norma
            WHERE n.numeral = :u AND (k.norma_relacionada = :n OR k.clave = (SELECT MAX(norma_relacionada)
                                       FROM {self._crudo()}.normas_catalogo WHERE clave = :n))""",
                                   {"n": c["norma"], "u": c["numeral"]})
        return c

    # ------------------------------------------------------------------------------- Vista 10 · Gobierno y bitácora
    def bitacora(self, tramite=None, origen=None, limite=300):
        filtros, p = [], {}
        if tramite:
            filtros.append("tramite_id = :t"); p["t"] = tramite
        if origen:
            filtros.append("origen = :o"); p["o"] = origen
        where = ("WHERE " + " AND ".join(filtros)) if filtros else ""
        return self.q(f"""SELECT fecha_hora, origen, COALESCE(usuario, usuario_id) AS usuario, rol, accion, tramite_id, objeto,
                                 detalle, sha256
                          FROM {self.N}.bitacora_unificada {where} ORDER BY fecha_hora DESC LIMIT {int(limite)}""", p)

    def bitacora_resumen(self):
        return self.q(f"""SELECT origen, accion, COUNT(*) AS eventos, MAX(fecha_hora) AS ultimo
                          FROM {self.N}.bitacora_unificada GROUP BY origen, accion ORDER BY origen, eventos DESC""")

    def alcoa(self):
        return self.q(f"SELECT * FROM {self.N}.alcoa_controles")

    def usuarios(self):
        return self.q(f"SELECT usuario_id, titulo, nombre, rol, area, activo FROM {self.L}.usuarios ORDER BY area, rol")
