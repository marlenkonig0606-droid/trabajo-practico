from database.conexion import BaseDeDatos

class ReportesDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    @staticmethod
    def filtro_fechas(columna, desde, hasta):
        filtros, parametros = ["1 = 1"], []
        if desde:
            filtros.append(f"date({columna}) >= date(?)")
            parametros.append(desde)
        if hasta:
            filtros.append(f"date({columna}) <= date(?)")
            parametros.append(hasta)
        return " AND ".join(filtros), tuple(parametros)

    def resumen_ventas(self, where, parametros, sucursal_id):
        filtro_sucursal = " AND v.sucursal_id = ?" if sucursal_id is not None else ""
        parametros = tuple(parametros) + ((sucursal_id,) if sucursal_id is not None else ())
        return self.db.consultar_uno(f"""
            SELECT COUNT(*) AS cantidad,
                   COALESCE(ROUND(SUM(v.total), 2), 0) AS ingresos,
                   COALESCE(SUM(v.unidades), 0) AS unidades
            FROM (
                SELECT venta.id, venta.sucursal_id, venta.fecha, venta.total,
                       COALESCE(SUM(detalle_venta.cantidad), 0) AS unidades
                FROM venta
                LEFT JOIN detalle_venta ON detalle_venta.venta_id = venta.id
                GROUP BY venta.id
            ) v
            WHERE {where}{filtro_sucursal}""", parametros)

    def resumen_devoluciones(self, where, parametros, sucursal_id):
        filtro_sucursal = " AND v.sucursal_id = ?" if sucursal_id is not None else ""
        parametros = tuple(parametros) + ((sucursal_id,) if sucursal_id is not None else ())
        return self.db.consultar_uno(f"""
            SELECT COUNT(DISTINCT d.id) AS cantidad,
                   COALESCE(ROUND(SUM(d.total), 2), 0) AS importe
            FROM devolucion d
            JOIN venta v ON v.id = d.venta_id
            WHERE {where}{filtro_sucursal}""", parametros)

    def local_lider(self, where_devoluciones, params_devoluciones,
                    where_ventas, params_ventas):
        return self.db.consultar(f"""
            WITH ingresos_ventas AS (
                SELECT v.sucursal_id, SUM(v.total) AS importe,
                       COUNT(*) AS cantidad_ventas
                FROM venta v WHERE {where_ventas}
                GROUP BY v.sucursal_id
            ),
            egresos_devoluciones AS (
                SELECT v.sucursal_id, SUM(d.total) AS importe
                FROM devolucion d JOIN venta v ON v.id=d.venta_id
                WHERE {where_devoluciones}
                GROUP BY v.sucursal_id
            )
            SELECT s.id, s.nombre,
                   ROUND(COALESCE(iv.importe, 0)
                         - COALESCE(ed.importe, 0), 2) AS ingresos_netos,
                   COALESCE(iv.cantidad_ventas, 0) AS cantidad_ventas
            FROM sucursal s
            LEFT JOIN ingresos_ventas iv ON iv.sucursal_id=s.id
            LEFT JOIN egresos_devoluciones ed ON ed.sucursal_id=s.id
            WHERE s.tipo='LOCAL'
              AND (iv.sucursal_id IS NOT NULL OR ed.sucursal_id IS NOT NULL)
            ORDER BY ingresos_netos DESC, cantidad_ventas DESC, s.nombre
            LIMIT 1""", tuple(params_ventas) + tuple(params_devoluciones))

    def rechazados(self, filtros, parametros):
        return self.db.consultar(f"""
            SELECT b.id AS bulto_id, b.precinto, r.numero AS remito, s.nombre AS destino,
                   b.fecha_recepcion,
                   (SELECT h.observacion FROM historial_bulto h
                    WHERE h.bulto_id = b.id AND h.estado = 'RECHAZADO') AS motivo,
                   SUM(db.cantidad) AS unidades,
                   CASE WHEN COUNT(db.costo_unitario)=COUNT(*)
                        THEN ROUND(SUM(db.cantidad * db.costo_unitario), 2)
                        ELSE NULL END AS valor_historico,
                   COUNT(db.costo_unitario) != COUNT(*) AS costo_faltante
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.destino_id
            JOIN detalle_bulto db ON db.bulto_id = b.id
            WHERE {' AND '.join(filtros)}
            GROUP BY b.id
            ORDER BY b.fecha_recepcion DESC""", tuple(parametros))

    def tiempo_promedio_transito(self, sucursal_id=None):
        return self.db.consultar("""
            SELECT s.nombre AS local, COUNT(*) AS bultos,
                   ROUND(AVG((julianday(b.fecha_recepcion) - julianday(b.fecha_despacho)) * 24), 2)
                       AS horas_promedio
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.destino_id
            WHERE b.estado='VERIFICADO'
              AND b.fecha_despacho IS NOT NULL AND b.fecha_recepcion IS NOT NULL
              AND (? IS NULL OR s.id=?)
            GROUP BY s.id ORDER BY horas_promedio DESC""",
            (sucursal_id, sucursal_id))

    def estados_transito(self, sucursal_id=None):
        return self.db.consultar(
            """SELECT s.id AS sucursal_id, s.nombre AS local,
                      SUM(CASE WHEN b.estado IN ('EN_TRANSITO', 'RECIBIDO')
                               THEN 1 ELSE 0 END) AS pendientes_verificacion,
                      SUM(CASE WHEN b.estado='RECHAZADO' THEN 1 ELSE 0 END) AS rechazados,
                      SUM(CASE WHEN b.estado='PERDIDO' THEN 1 ELSE 0 END) AS perdidos
               FROM sucursal s
               LEFT JOIN orden_reposicion o ON o.destino_id=s.id
               LEFT JOIN remito r ON r.orden_id=o.id
               LEFT JOIN bulto b ON b.remito_id=r.id
               WHERE s.tipo='LOCAL' AND (? IS NULL OR s.id=?)
               GROUP BY s.id ORDER BY s.nombre""",
            (sucursal_id, sucursal_id))

    def alertas_verificacion(self, sucursal_id=None):
        return self.db.consultar(
            """SELECT b.id AS bulto_id, r.numero AS remito, s.nombre AS local,
                      b.estado, b.fecha_despacho, b.fecha_recepcion,
                      ROUND((julianday('now', 'localtime')
                             - julianday(b.fecha_despacho))*24, 1) AS horas_sin_verificar,
                      CASE WHEN julianday('now', 'localtime')
                                    - julianday(b.fecha_despacho) >= 2
                           THEN 'ESCALADO_48_HORAS'
                           ELSE 'ALERTA_24_HORAS' END AS nivel
               FROM bulto b
               JOIN remito r ON r.id=b.remito_id
               JOIN orden_reposicion o ON o.id=r.orden_id
               JOIN sucursal s ON s.id=o.destino_id
               WHERE b.estado IN ('EN_TRANSITO', 'RECIBIDO')
                 AND b.fecha_despacho IS NOT NULL
                 AND b.fecha_despacho <= datetime('now', 'localtime', '-24 hours')
                 AND (? IS NULL OR s.id=?)
               ORDER BY b.fecha_despacho""",
            (sucursal_id, sucursal_id))

    def existencias(self, sucursal_id):
        return self.db.consultar("""
            SELECT s.nombre AS sucursal, p.codigo, p.nombre AS producto,
                   COALESCE(st.disponible, 0) AS disponible,
                   COALESCE(st.reservado, 0) AS reservado,
                   COALESCE(st.disponible - st.reservado, 0) AS libre,
                   COALESCE(logistica.en_transito, 0) AS en_transito,
                   COALESCE(logistica.recibido_sin_verificar, 0) AS recibido_sin_verificar,
                   COALESCE(logistica.rechazado, 0) AS rechazado,
                   COALESCE(libro.movimientos, 0) AS saldo_segun_movimientos,
                   COALESCE(st.disponible, 0)-COALESCE(libro.movimientos, 0)
                       AS diferencia_movimientos,
                   COALESCE(mv.stock_minimo, 0) AS stock_minimo,
                   CASE WHEN COALESCE(st.disponible, 0)!=COALESCE(libro.movimientos, 0)
                        THEN 'CONCILIAR'
                        WHEN COALESCE(st.disponible-st.reservado, 0)<COALESCE(mv.stock_minimo, 0)
                        THEN 'BAJO MÍNIMO' ELSE 'OK' END AS estado
            FROM sucursal s
            CROSS JOIN producto p
            LEFT JOIN stock st ON st.sucursal_id = s.id AND st.producto_id = p.id
            -- mínimo de ESA sucursal: el propio del local o el propio del CD
            LEFT JOIN minimo_vigente mv ON mv.sucursal_id = s.id AND mv.producto_id = p.id
            LEFT JOIN (
                SELECT m.sucursal_id, m.producto_id, SUM(m.cantidad) AS movimientos
                FROM movimiento_stock m
                GROUP BY m.sucursal_id, m.producto_id
            ) libro ON libro.sucursal_id=s.id AND libro.producto_id=p.id
            LEFT JOIN (
                SELECT o.destino_id AS sucursal_id, db.producto_id,
                       SUM(CASE WHEN b.estado='EN_TRANSITO' THEN db.cantidad ELSE 0 END)
                           AS en_transito,
                       SUM(CASE WHEN b.estado='RECIBIDO' THEN db.cantidad ELSE 0 END)
                           AS recibido_sin_verificar,
                       SUM(CASE WHEN b.estado='RECHAZADO' THEN db.cantidad ELSE 0 END)
                           AS rechazado
                FROM orden_reposicion o
                JOIN remito r ON r.orden_id=o.id
                JOIN bulto b ON b.remito_id=r.id
                JOIN detalle_bulto db ON db.bulto_id=b.id
                GROUP BY o.destino_id, db.producto_id
            ) logistica ON logistica.sucursal_id=s.id
                        AND logistica.producto_id=p.id
            WHERE (? IS NULL OR s.id = ?)
            ORDER BY estado = 'OK', s.nombre, p.nombre""",
            (sucursal_id, sucursal_id))

    def movimientos(self, sucursal_id, tipos):
        if not tipos:
            return []
        ramas = {
            "VENTA": """
                SELECT 'VENTA' AS tipo, v.id AS operacion_id, v.id AS venta_id,
                       NULL AS devolucion_id, date(v.fecha) AS fecha, s.nombre AS sucursal,
                       'Venta #' || v.id AS referencia,
                       SUM(dv.cantidad) AS unidades,
                       ROUND(SUM(dv.cantidad * dv.precio_unitario), 2) AS valor
                FROM venta v
                JOIN sucursal s ON s.id = v.sucursal_id
                JOIN detalle_venta dv ON dv.venta_id = v.id
                WHERE (? IS NULL OR v.sucursal_id = ?)
                GROUP BY v.id
            """,
            "DEVOLUCION": """
                SELECT 'DEVOLUCION' AS tipo, d.id AS operacion_id, d.venta_id,
                       d.id AS devolucion_id, date(d.fecha) AS fecha, s.nombre AS sucursal,
                       'Devolución #' || d.id AS referencia,
                       SUM(dd.cantidad) AS unidades,
                       -ROUND(SUM(dd.cantidad * dd.precio_unitario), 2) AS valor
                FROM devolucion d
                JOIN venta v ON v.id = d.venta_id
                JOIN sucursal s ON s.id = v.sucursal_id
                JOIN detalle_devolucion dd ON dd.devolucion_id = d.id
                WHERE (? IS NULL OR v.sucursal_id = ?)
                GROUP BY d.id
            """,
            "RECEPCION": """
                SELECT 'RECEPCION' AS tipo, m.referencia AS operacion_id,
                       NULL AS venta_id, NULL AS devolucion_id, date(MAX(m.fecha)) AS fecha,
                       s.nombre AS sucursal, m.referencia AS referencia,
                       SUM(m.cantidad) AS unidades,
                       CASE WHEN COUNT(m.costo_unitario)=COUNT(*)
                            THEN ROUND(SUM(m.cantidad * m.costo_unitario), 2)
                            ELSE NULL END AS valor
                FROM movimiento_stock m
                JOIN sucursal s ON s.id = m.sucursal_id
                WHERE m.motivo='RECEPCION' AND (? IS NULL OR m.sucursal_id = ?)
                GROUP BY s.id, m.referencia
            """,
        }
        consulta = " UNION ALL ".join(ramas[tipo] for tipo in tipos)
        parametros = tuple(
            valor for _ in tipos for valor in (sucursal_id, sucursal_id))
        return self.db.consultar(
            f"SELECT * FROM ({consulta}) ORDER BY fecha DESC, sucursal, tipo",
            parametros)

    def ventas(self, where, parametros):
        return self.db.consultar(f"""
            SELECT date(v.fecha) AS dia, s.nombre AS local, pg.medio_pago,
                   COUNT(*) AS ventas,
                   ROUND(SUM(v.total), 2) AS ingresos,
                   ROUND(AVG(v.total), 2) AS ticket_promedio
            FROM venta v
            JOIN sucursal s ON s.id = v.sucursal_id
            JOIN pago pg ON pg.venta_id = v.id
            WHERE {where}
            GROUP BY dia, s.id, pg.medio_pago
            ORDER BY dia DESC, ingresos DESC""", parametros)

    def mas_vendidos(self, where_vendido, params_vendido,
                     where_devuelto, params_devuelto):
        return self.db.consultar(f"""
            WITH vendido AS (
                SELECT dv.producto_id,
                       SUM(dv.cantidad) AS unidades,
                       SUM(dv.cantidad * dv.precio_unitario) AS ingresos,
                       SUM(dv.cantidad * dv.costo_unitario) AS costo,
                       SUM(CASE WHEN dv.costo_unitario IS NULL
                                THEN dv.cantidad ELSE 0 END) AS unidades_sin_costo
                FROM detalle_venta dv
                JOIN venta v ON v.id = dv.venta_id
                WHERE {where_vendido}
                GROUP BY dv.producto_id
            ),
            devuelto AS (
                SELECT dd.producto_id,
                       SUM(dd.cantidad) AS unidades,
                       SUM(dd.cantidad * dd.precio_unitario) AS importe,
                       SUM(dd.cantidad * dd.costo_unitario) AS costo,
                       SUM(CASE WHEN dd.costo_unitario IS NULL
                                THEN dd.cantidad ELSE 0 END) AS unidades_sin_costo
                FROM detalle_devolucion dd
                JOIN devolucion d ON d.id = dd.devolucion_id
                JOIN venta v ON v.id = d.venta_id
                WHERE {where_devuelto}
                GROUP BY dd.producto_id
            )
            SELECT p.codigo, p.nombre AS producto,
                   ve.unidades - COALESCE(de.unidades, 0) AS unidades,
                   ROUND(ve.ingresos - COALESCE(de.importe, 0), 2) AS ingresos,
                   CASE WHEN ve.unidades_sin_costo=0
                              AND COALESCE(de.unidades_sin_costo, 0)=0
                        THEN ROUND(ve.costo - COALESCE(de.costo, 0), 2)
                        ELSE NULL END AS costo,
                   CASE WHEN ve.unidades_sin_costo=0
                              AND COALESCE(de.unidades_sin_costo, 0)=0
                        THEN ROUND(ve.ingresos - COALESCE(de.importe, 0)
                             - ve.costo + COALESCE(de.costo, 0), 2)
                        ELSE NULL END AS margen,
                   CASE WHEN ve.unidades_sin_costo=0
                              AND COALESCE(de.unidades_sin_costo, 0)=0
                        THEN ROUND(100.0 * (ve.ingresos - COALESCE(de.importe, 0)
                             - ve.costo + COALESCE(de.costo, 0))
                             / NULLIF(ve.ingresos - COALESCE(de.importe, 0), 0), 1)
                        ELSE NULL END AS margen_pct,
                   CASE WHEN ve.unidades_sin_costo>0
                              OR COALESCE(de.unidades_sin_costo, 0)>0
                        THEN 1 ELSE 0 END AS costo_faltante
            FROM vendido ve
            JOIN producto p ON p.id = ve.producto_id
            LEFT JOIN devuelto de ON de.producto_id = ve.producto_id
            ORDER BY unidades DESC, margen DESC""",
            tuple(params_vendido) + tuple(params_devuelto))

    def ordenes(self):
        return self.db.consultar(
            "SELECT estado, fecha FROM orden_reposicion"
        )
    #busco el remito para cada bulto(y de ahi su orden y orden del local tmb) /
    # para agruparlo por local, contandolo y sumando a cada bulto rechazadp
    def abastecimiento(self):
        return self.db.consultar("""
            SELECT s.nombre AS local,
                   COUNT(*) AS bultos,
                   SUM(CASE WHEN b.estado = 'RECHAZADO' THEN 1 ELSE 0 END) AS rechazados
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.destino_id
            GROUP BY s.id""")

    #queremos que el reporrte de ventas por medio de pago quede algo asi
    #medio_pago        ventas          ingresos
    #EFECTIVO          12              10000
    #TARJETA_CREDITO   34              90000

    def ventas_por_medio_pago(self, sucursal_id, where="1 = 1", parametros_fecha=()):
        """where/parametros_fecha: filtro opcional de período (ver filtro_fechas)."""
        filtro = f"WHERE {where}"
        parametros = tuple(parametros_fecha)
        if sucursal_id is not None:                 # es un local: solo sus ventas
            filtro += " AND v.sucursal_id = ?"
            parametros += (sucursal_id,) #LLEVA COMA PORQUE NECESITAMOS UNA TUPLA DE PARAMETROS, sin la coma es un parentesis comun y quedarian numeros sueltos
        return self.db.consultar(f"""
            SELECT pg.medio_pago,
                   COUNT(*) AS ventas,
                   ROUND(SUM(v.total), 2) AS ingresos
            FROM venta v
            JOIN pago pg ON pg.venta_id = v.id
            {filtro}
            GROUP BY pg.medio_pago
            ORDER BY ingresos DESC""", parametros)
 #el filtro hace que pythonn rellene lo que tiene guardado en esa variable



#lo que quiero hacer maso menos es esto
#producto   devoluciones      unidades        importe
#agua 1.5l       3               5             4000
#yerba 1kg       2               4             9000
    def devoluciones_por_producto(self, sucursal_id, where="1 = 1", parametros_fecha=()):
        """where/parametros_fecha: filtro opcional de período sobre d.fecha."""
        filtro = f"WHERE {where}"
        parametros = tuple(parametros_fecha)
        if sucursal_id is not None:
            filtro += " AND v.sucursal_id = ?"
            parametros += (sucursal_id,)
        return self.db.consultar(f"""
            SELECT p.id AS producto_id, p.nombre AS producto,
                   COUNT(DISTINCT d.id) AS devoluciones,
                   SUM(dd.cantidad) AS unidades,
                   ROUND(SUM(dd.cantidad * dd.precio_unitario), 2) AS importe
            FROM detalle_devolucion dd
            JOIN devolucion d ON d.id = dd.devolucion_id
            JOIN venta v ON v.id = d.venta_id
            JOIN producto p ON p.id = dd.producto_id
            {filtro}
            GROUP BY p.id
            ORDER BY unidades DESC""", parametros)

    # ================================================================
    #  REPORTE GERENCIAL DE UN LOCAL
    #  Todas las consultas reciben la sucursal y un filtro de período
    #  (where + parámetros armados con filtro_fechas).
    # ================================================================

    def tickets(self, sucursal_id, where, parametros):
        """Una fila por venta: es la base de los indicadores, la estadística y
        la evolución mensual (se agrega en Python para no repetir consultas)."""
        return self.db.consultar(f"""
            SELECT v.id, v.fecha, strftime('%Y-%m', v.fecha) AS mes,
                   ROUND(v.total, 2) AS total,
                   COALESCE((SELECT SUM(dv.cantidad) FROM detalle_venta dv
                             WHERE dv.venta_id = v.id), 0) AS unidades,
                   (SELECT pg.medio_pago FROM pago pg WHERE pg.venta_id = v.id)
                       AS medio_pago
            FROM venta v
            WHERE {where} AND v.sucursal_id = ?
            ORDER BY v.fecha, v.id""", tuple(parametros) + (sucursal_id,))

    def unidades_por_producto_y_mes(self, sucursal_id, where, parametros):
        return self.db.consultar(f"""
            SELECT p.id AS producto_id, p.nombre AS producto,
                   strftime('%Y-%m', v.fecha) AS mes,
                   SUM(dv.cantidad) AS unidades
            FROM detalle_venta dv
            JOIN venta v ON v.id = dv.venta_id
            JOIN producto p ON p.id = dv.producto_id
            WHERE {where} AND v.sucursal_id = ?
            GROUP BY p.id, mes
            ORDER BY mes, p.nombre""", tuple(parametros) + (sucursal_id,))

    def movimientos_de_stock(self, sucursal_id, hasta=None):
        """Historial completo de entradas/salidas por producto (para reconstruir
        cuándo hubo stock). Se toma desde el inicio: el saldo depende de todo
        lo anterior al período."""
        return self.db.consultar("""
            SELECT m.producto_id, p.nombre AS producto, m.fecha, m.cantidad
            FROM movimiento_stock m
            JOIN producto p ON p.id = m.producto_id
            WHERE m.sucursal_id = ? AND (? IS NULL OR date(m.fecha) <= date(?))
            ORDER BY m.producto_id, m.fecha, m.id""",
            (sucursal_id, hasta, hasta))

    def alertas_pendientes(self, sucursal_id):
        return self.db.consultar("""
            SELECT p.nombre AS producto, a.fecha AS desde,
                   COALESCE(st.disponible - st.reservado, 0) AS libre,
                   COALESCE(mv.stock_minimo, 0) AS minimo,
                   MAX(COALESCE(mv.stock_minimo, 0) - COALESCE(st.disponible - st.reservado, 0), 0)
                       AS faltante
            FROM alerta_stock a
            JOIN producto p ON p.id = a.producto_id
            LEFT JOIN minimo_vigente mv ON mv.sucursal_id = a.sucursal_id
                                       AND mv.producto_id = a.producto_id
            LEFT JOIN stock st ON st.sucursal_id = a.sucursal_id
                              AND st.producto_id = a.producto_id
            WHERE a.sucursal_id = ? AND a.resuelta = 0
            ORDER BY faltante DESC, p.nombre""", (sucursal_id,))

    def ordenes_del_local(self, sucursal_id, where, parametros):
        return self.db.consultar(f"""
            SELECT o.id, o.estado, o.resolucion, o.fecha, s.nombre AS cd
            FROM orden_reposicion o
            JOIN sucursal s ON s.id = o.origen_id
            WHERE {where} AND o.destino_id = ?""",
            tuple(parametros) + (sucursal_id,))

    def bultos_del_local(self, sucursal_id):
        """Todos los bultos enviados (o por enviar) al local, con su CD de origen,
        la fecha del pedido y las fechas reales de despacho y recepción."""
        return self.db.consultar("""
            SELECT b.id, b.estado, o.id AS orden_id, o.fecha AS fecha_pedido,
                   s.nombre AS cd, b.fecha_despacho, b.fecha_recepcion,
                   COALESCE((SELECT SUM(db.cantidad) FROM detalle_bulto db
                             WHERE db.bulto_id = b.id), 0) AS unidades
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.origen_id
            WHERE o.destino_id = ?""", (sucursal_id,))

    def productos_rechazados(self, sucursal_id, where, parametros):
        """where filtra por b.fecha_recepcion (el día en que se rechazó)."""
        return self.db.consultar(f"""
            SELECT p.nombre AS producto, COUNT(DISTINCT b.id) AS bultos,
                   SUM(db.cantidad) AS unidades
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN detalle_bulto db ON db.bulto_id = b.id
            JOIN producto p ON p.id = db.producto_id
            WHERE b.estado = 'RECHAZADO' AND {where} AND o.destino_id = ?
            GROUP BY p.id
            ORDER BY unidades DESC""", tuple(parametros) + (sucursal_id,))

    def anios_con_datos(self, sucursal_id):
        return [fila["anio"] for fila in self.db.consultar("""
            SELECT DISTINCT CAST(strftime('%Y', fecha) AS INTEGER) AS anio FROM (
                SELECT fecha FROM venta WHERE sucursal_id = ?
                UNION ALL
                SELECT fecha FROM orden_reposicion WHERE destino_id = ?)
            ORDER BY anio DESC""", (sucursal_id, sucursal_id))]

    # ================================================================
    #  Reporte del centro de distribución (toda la red de locales)
    # ================================================================
    def locales_activos(self):
        return self.db.consultar(
            "SELECT id, nombre FROM sucursal WHERE tipo='LOCAL' AND activo=1 ORDER BY nombre")

    def es_local_activo(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT 1 AS ok FROM sucursal WHERE id=? AND tipo='LOCAL' AND activo=1",
            (sucursal_id,)) is not None

    def anios_con_datos_red(self):
        return [fila["anio"] for fila in self.db.consultar("""
            SELECT DISTINCT CAST(strftime('%Y', fecha) AS INTEGER) AS anio FROM (
                SELECT fecha FROM venta UNION ALL SELECT fecha FROM orden_reposicion)
            ORDER BY anio DESC""")]

    def ventas_por_local_producto_mes(self, where, parametros):
        """Ventas de todos los locales agrupadas por local, producto y mes.
        El costo es el guardado en cada venta (precio histórico); si una venta
        vieja no lo tiene, se usa el costo actual del producto."""
        return self.db.consultar(f"""
            SELECT v.sucursal_id, s.nombre AS local, p.id AS producto_id,
                   p.nombre AS producto, strftime('%Y-%m', v.fecha) AS mes,
                   COUNT(DISTINCT v.id) AS ventas,
                   SUM(dv.cantidad) AS unidades,
                   SUM(dv.cantidad * dv.precio_unitario) AS ingresos,
                   SUM(dv.cantidad * COALESCE(dv.costo_unitario, p.precio_costo)) AS costo
            FROM detalle_venta dv
            JOIN venta v ON v.id = dv.venta_id
            JOIN sucursal s ON s.id = v.sucursal_id
            JOIN producto p ON p.id = dv.producto_id
            WHERE {where}
            GROUP BY v.sucursal_id, p.id, mes""", tuple(parametros))

    def ventas_por_local_y_mes(self, where, parametros):
        """Cantidad de tickets por local y mes (un ticket puede tener varios productos)."""
        return self.db.consultar(f"""
            SELECT v.sucursal_id, strftime('%Y-%m', v.fecha) AS mes, COUNT(*) AS ventas
            FROM venta v WHERE {where}
            GROUP BY v.sucursal_id, mes""", tuple(parametros))

    def devoluciones_por_local_producto_mes(self, where, parametros):
        """where filtra por d.fecha (la plata sale el día de la devolución)."""
        return self.db.consultar(f"""
            SELECT v.sucursal_id, p.id AS producto_id, strftime('%Y-%m', d.fecha) AS mes,
                   SUM(dd.cantidad) AS unidades,
                   SUM(dd.cantidad * dd.precio_unitario) AS importe,
                   SUM(dd.cantidad * COALESCE(dd.costo_unitario, p.precio_costo)) AS costo
            FROM detalle_devolucion dd
            JOIN devolucion d ON d.id = dd.devolucion_id
            JOIN venta v ON v.id = d.venta_id
            JOIN producto p ON p.id = dd.producto_id
            WHERE {where}
            GROUP BY v.sucursal_id, p.id, mes""", tuple(parametros))

    def bultos_perdidos(self, where, parametros):
        """Mercadería perdida en tránsito, valuada al costo del despacho.
        where filtra por h.fecha (cuándo se declaró perdido)."""
        return self.db.consultar(f"""
            SELECT strftime('%Y-%m', h.fecha) AS mes, b.id AS bulto_id,
                   SUM(db.cantidad * COALESCE(db.costo_unitario, p.precio_costo)) AS valor
            FROM bulto b
            JOIN historial_bulto h ON h.bulto_id = b.id AND h.estado = 'PERDIDO'
            JOIN detalle_bulto db ON db.bulto_id = b.id
            JOIN producto p ON p.id = db.producto_id
            WHERE b.estado = 'PERDIDO' AND {where}
            GROUP BY b.id""", tuple(parametros))

    def ordenes_para_cumplimiento(self, where, parametros, cd_id=None):
        """Cada orden con las unidades pedidas y las que el local recibió y
        verificó. where filtra por o.fecha (cuándo se hizo el pedido)."""
        filtro_cd = " AND o.origen_id = ?" if cd_id is not None else ""
        return self.db.consultar(f"""
            SELECT o.id, o.estado, o.resolucion, o.fecha, o.destino_id,
                   s.nombre AS local, cd.nombre AS cd,
                   (SELECT SUM(dor.cantidad) FROM detalle_orden dor
                    WHERE dor.orden_id = o.id) AS pedidas,
                   (SELECT COALESCE(SUM(db.cantidad), 0)
                    FROM remito r JOIN bulto b ON b.remito_id = r.id
                    JOIN detalle_bulto db ON db.bulto_id = b.id
                    WHERE r.orden_id = o.id AND b.estado = 'VERIFICADO') AS recibidas
            FROM orden_reposicion o
            JOIN sucursal s ON s.id = o.destino_id
            JOIN sucursal cd ON cd.id = o.origen_id
            WHERE {where}{filtro_cd}
            ORDER BY o.fecha""",
            tuple(parametros) + ((cd_id,) if cd_id is not None else ()))

    def movimientos_de_cds(self, where, parametros):
        """Entradas y salidas de mercadería de cada CD, por mes, tipo y proveedor.
        where filtra por m.fecha."""
        return self.db.consultar(f"""
            SELECT s.id AS cd_id, s.nombre AS cd, strftime('%Y-%m', m.fecha) AS mes,
                   m.motivo, COALESCE(pr.nombre, 'Sin proveedor') AS proveedor,
                   SUM(m.cantidad) AS unidades,
                   SUM(m.cantidad * COALESCE(m.costo_unitario, p.precio_costo)) AS valor,
                   COUNT(DISTINCT COALESCE(m.referencia, m.id)) AS documentos
            FROM movimiento_stock m
            JOIN sucursal s ON s.id = m.sucursal_id AND s.tipo = 'CD'
            JOIN producto p ON p.id = m.producto_id
            LEFT JOIN proveedor pr ON pr.id = p.proveedor_id
            WHERE {where}
            GROUP BY s.id, mes, m.motivo, pr.id""", tuple(parametros))

    def stock_de_cds(self):
        return self.db.consultar("""
            SELECT s.id AS cd_id, s.nombre AS cd,
                   COALESCE(SUM(st.disponible), 0) AS unidades,
                   COALESCE(SUM(st.disponible * p.precio_costo), 0) AS valor
            FROM sucursal s
            LEFT JOIN stock st ON st.sucursal_id = s.id
            LEFT JOIN producto p ON p.id = st.producto_id
            WHERE s.tipo = 'CD' AND s.activo = 1
            GROUP BY s.id ORDER BY s.nombre""")

    def ultimos_ingresos_a_cds(self, where, parametros, limite=10):
        return self.db.consultar(f"""
            SELECT m.fecha, s.nombre AS cd, p.nombre AS producto,
                   COALESCE(pr.nombre, 'Sin proveedor') AS proveedor, m.cantidad,
                   ROUND(m.cantidad * COALESCE(m.costo_unitario, p.precio_costo), 2) AS valor,
                   m.referencia
            FROM movimiento_stock m
            JOIN sucursal s ON s.id = m.sucursal_id AND s.tipo = 'CD'
            JOIN producto p ON p.id = m.producto_id
            LEFT JOIN proveedor pr ON pr.id = p.proveedor_id
            WHERE m.motivo = 'INGRESO_PROVEEDOR' AND {where}
            ORDER BY m.fecha DESC, m.id DESC LIMIT ?""", tuple(parametros) + (limite,))
