"""
La consigna pide AL MENOS 4 reportes no triviales.
Hay 2 hechos (ambos de logística). Te quedan los de ventas/stock (ver README, paso 6).
"""
from database.conexion import BaseDeDatos


class ReportesService:
    def __init__(self):
        self.db = BaseDeDatos()

    def bultos_rechazados(self, desde=None, hasta=None):
        filtros, params = ["b.estado = 'RECHAZADO'"], []
        if desde:
            filtros.append("date(b.fecha_recepcion) >= date(?)"); params.append(desde)
        if hasta:
            filtros.append("date(b.fecha_recepcion) <= date(?)"); params.append(hasta)

        return self.db.consultar(f"""
            SELECT b.id AS bulto_id, b.precinto, r.numero AS remito, s.nombre AS destino,
                   b.fecha_recepcion,
                   (SELECT h.observacion FROM historial_bulto h
                    WHERE h.bulto_id = b.id AND h.estado = 'RECHAZADO') AS motivo,
                   SUM(db.cantidad) AS unidades,
                   ROUND(SUM(db.cantidad * p.precio_costo), 2) AS merma_valorizada
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.destino_id
            JOIN detalle_bulto db ON db.bulto_id = b.id
            JOIN producto p ON p.id = db.producto_id
            WHERE {' AND '.join(filtros)}
            GROUP BY b.id
            ORDER BY b.fecha_recepcion DESC""", tuple(params))

    # ✅ HECHO: tiempo promedio de tránsito CD -> cada local (en horas)
    def tiempo_promedio_transito(self):
        return self.db.consultar("""
            SELECT s.nombre AS local, COUNT(*) AS bultos,
                   ROUND(AVG((julianday(b.fecha_recepcion) - julianday(b.fecha_despacho)) * 24), 2)
                       AS horas_promedio
            FROM bulto b
            JOIN remito r ON r.id = b.remito_id
            JOIN orden_reposicion o ON o.id = r.orden_id
            JOIN sucursal s ON s.id = o.destino_id
            WHERE b.fecha_despacho IS NOT NULL AND b.fecha_recepcion IS NOT NULL
            GROUP BY s.id ORDER BY horas_promedio DESC""")

    # Reporte: existencias actuales y productos en stock mínimo
    def existencias(self):
        # CROSS JOIN = todas las combinaciones sucursal x producto.
        # LEFT JOIN stock = trae el stock si existe; si no hay fila, las columnas quedan NULL
        # y COALESCE las convierte en 0 (así aparecen los productos que el local NO tiene).
        return self.db.consultar("""
            SELECT s.nombre AS sucursal, p.codigo, p.nombre AS producto,
                   COALESCE(st.disponible, 0) AS disponible,
                   COALESCE(st.reservado, 0) AS reservado,
                   COALESCE(st.disponible - st.reservado, 0) AS libre,
                   p.stock_minimo,
                   CASE WHEN COALESCE(st.disponible - st.reservado, 0) < p.stock_minimo
                        THEN 'BAJO MÍNIMO' ELSE 'OK' END AS estado
            FROM sucursal s
            CROSS JOIN producto p
            LEFT JOIN stock st ON st.sucursal_id = s.id AND st.producto_id = p.id
            ORDER BY estado = 'OK', s.nombre, p.nombre""")

    # Reporte: movimientos y valorización del inventario
    def movimientos(self):
        return self.db.consultar("""
            SELECT s.nombre AS sucursal, m.motivo,
                   COUNT(*) AS movimientos,
                   SUM(CASE WHEN m.cantidad > 0 THEN m.cantidad ELSE 0 END) AS entradas,
                   SUM(CASE WHEN m.cantidad < 0 THEN -m.cantidad ELSE 0 END) AS salidas,
                   ROUND(SUM(m.cantidad * p.precio_costo), 2) AS valor_neto
            FROM movimiento_stock m
            JOIN sucursal s ON s.id = m.sucursal_id
            JOIN producto p ON p.id = m.producto_id
            GROUP BY s.id, m.motivo
            ORDER BY s.nombre, m.motivo""")

    # Filtro de fechas reutilizable: arma "date(columna) >= ? AND date(columna) <= ?"
    @staticmethod
    def _filtro_fechas(columna, desde, hasta):
        filtros, params = ["1 = 1"], []      # 1 = 1: así el WHERE nunca queda vacío
        if desde:
            filtros.append(f"date({columna}) >= date(?)"); params.append(desde)
        if hasta:
            filtros.append(f"date({columna}) <= date(?)"); params.append(hasta)
        return " AND ".join(filtros), tuple(params)

    # Reporte: ventas e ingresos por período, local y medio de pago
    def ventas(self, desde=None, hasta=None):
        where, params = self._filtro_fechas("v.fecha", desde, hasta)
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
            ORDER BY dia DESC, ingresos DESC""", params)

    # Reporte: productos más vendidos y margen de ganancia / pérdida
    def mas_vendidos(self, desde=None, hasta=None):
        """Se descuentan las devoluciones. Ingresos al precio del momento de la venta,
        costo al precio de costo actual del producto."""
        where, params = self._filtro_fechas("v.fecha", desde, hasta)
        return self.db.consultar(f"""
            WITH vendido AS (
                SELECT dv.producto_id,
                       SUM(dv.cantidad) AS unidades,
                       SUM(dv.cantidad * dv.precio_unitario) AS ingresos
                FROM detalle_venta dv
                JOIN venta v ON v.id = dv.venta_id
                WHERE {where}
                GROUP BY dv.producto_id
            ),
            devuelto AS (
                SELECT dd.producto_id,
                       SUM(dd.cantidad) AS unidades,
                       SUM(dd.cantidad * dd.precio_unitario) AS importe
                FROM detalle_devolucion dd
                JOIN devolucion d ON d.id = dd.devolucion_id
                JOIN venta v ON v.id = d.venta_id
                WHERE {where}
                GROUP BY dd.producto_id
            )
            SELECT p.codigo, p.nombre AS producto,
                   ve.unidades - COALESCE(de.unidades, 0) AS unidades,
                   ROUND(ve.ingresos - COALESCE(de.importe, 0), 2) AS ingresos,
                   ROUND((ve.unidades - COALESCE(de.unidades, 0)) * p.precio_costo, 2) AS costo,
                   ROUND(ve.ingresos - COALESCE(de.importe, 0)
                         - (ve.unidades - COALESCE(de.unidades, 0)) * p.precio_costo, 2) AS margen,
                   ROUND(100.0 * (ve.ingresos - COALESCE(de.importe, 0)
                         - (ve.unidades - COALESCE(de.unidades, 0)) * p.precio_costo)
                         / NULLIF(ve.ingresos - COALESCE(de.importe, 0), 0), 1) AS margen_pct
            FROM vendido ve
            JOIN producto p ON p.id = ve.producto_id
            LEFT JOIN devuelto de ON de.producto_id = ve.producto_id
            ORDER BY unidades DESC, margen DESC""", params * 2)
