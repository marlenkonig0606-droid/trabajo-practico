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
                   p.stock_minimo,
                   CASE WHEN COALESCE(st.disponible, 0)!=COALESCE(libro.movimientos, 0)
                        THEN 'CONCILIAR'
                        WHEN COALESCE(st.disponible-st.reservado, 0)<p.stock_minimo
                        THEN 'BAJO MÍNIMO' ELSE 'OK' END AS estado
            FROM sucursal s
            CROSS JOIN producto p
            LEFT JOIN stock st ON st.sucursal_id = s.id AND st.producto_id = p.id
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

    def ventas_por_medio_pago(self, sucursal_id):
        filtro = ""
        parametros = ()
        if sucursal_id is not None:                 # es un local: solo sus ventas
            filtro = "WHERE v.sucursal_id = ?"
            parametros = (sucursal_id,) #LLEVA COMA PORQUE NECESITAMOS UNA TUPLA DE PARAMETROS, sin la coma es un parentesis comun y quedarian numeros sueltos
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
    def devoluciones_por_producto(self, sucursal_id):
           filtro = ""
           parametros = ()
           if sucursal_id is not None:
               filtro = "WHERE v.sucursal_id = ?"
               parametros = (sucursal_id,)
           return self.db.consultar(f"""
               SELECT p.nombre AS producto,
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