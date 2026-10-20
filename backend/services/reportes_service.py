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

    # TODO: ventas e ingresos por período, local y medio de pago
    # TODO: productos más vendidos + margen estimado (precio_venta - precio_costo)
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
