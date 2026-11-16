from database.conexion import BaseDeDatos


class StockDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def transaccion(self):
        return self.db.transaccion()

    def disponible(self, sucursal_id, producto_id):
        return self.db.consultar_uno(
            "SELECT disponible FROM stock WHERE sucursal_id=? AND producto_id=?",
            (sucursal_id, producto_id))

    def reservado(self, sucursal_id, producto_id):
        return self.db.consultar_uno(
            "SELECT reservado FROM stock WHERE sucursal_id=? AND producto_id=?",
            (sucursal_id, producto_id))

    def reservar(self, sucursal_id, producto_id, cantidad):
        return self.db.ejecutar_contando(
            """UPDATE stock SET reservado = reservado + ?
               WHERE sucursal_id=? AND producto_id=? AND disponible - reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))

    def consumir_reserva(self, sucursal_id, producto_id, cantidad):
        return self.db.ejecutar_contando(
            """UPDATE stock SET disponible = disponible - ?, reservado = reservado - ?
               WHERE sucursal_id=? AND producto_id=? AND reservado >= ?""",
            (cantidad, cantidad, sucursal_id, producto_id, cantidad))

    def liberar_reserva(self, sucursal_id, producto_id, cantidad):
        return self.db.ejecutar_contando(
            """UPDATE stock SET reservado = reservado - ?
               WHERE sucursal_id=? AND producto_id=? AND reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))

    def sumar(self, sucursal_id, producto_id, cantidad):
        return self.db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)
               ON CONFLICT(sucursal_id, producto_id)
               DO UPDATE SET disponible = disponible + excluded.disponible""",
            (sucursal_id, producto_id, cantidad))

    def obtener_producto(self, producto_id):
        return self.db.consultar_uno(
            "SELECT id, precio_costo FROM producto WHERE id=?", (producto_id,))

    def obtener_existencia(self, sucursal_id, producto_id):
        return self.db.consultar_uno(
            """SELECT disponible, reservado FROM stock
               WHERE sucursal_id=? AND producto_id=?""",
            (sucursal_id, producto_id))

    def fijar_disponible(self, sucursal_id, producto_id, disponible):
        return self.db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)
               ON CONFLICT(sucursal_id, producto_id)
               DO UPDATE SET disponible=excluded.disponible""",
            (sucursal_id, producto_id, disponible))

    def restar(self, sucursal_id, producto_id, cantidad):
        return self.db.ejecutar_contando(
            """UPDATE stock SET disponible = disponible - ?
               WHERE sucursal_id=? AND producto_id=? AND disponible - reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))

    def registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo,
                             referencia, costo_unitario=None):
        return self.db.ejecutar(
            """INSERT INTO movimiento_stock
               (sucursal_id, producto_id, cantidad, motivo, referencia, costo_unitario)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (sucursal_id, producto_id, cantidad, motivo, referencia, costo_unitario))

    def cantidad_registrada_en_movimientos(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            """SELECT COALESCE(SUM(cantidad), 0) AS cantidad
               FROM movimiento_stock WHERE sucursal_id=? AND producto_id=?""",
            (sucursal_id, producto_id),
        )
        return fila["cantidad"]

    def listar(self, sucursal_id):
        """stock_minimo = mínimo vigente de ESA sucursal (propio del local, o suma de
        los locales para un CD). stock_minimo_defecto = valor inicial del producto."""
        return self.db.consultar(
            """SELECT p.id AS producto_id, p.codigo, p.nombre, p.precio_venta,
                      COALESCE(mv.stock_minimo, 0) AS stock_minimo,
                      p.stock_minimo AS stock_minimo_defecto, p.activo,
                      p.proveedor_id, pr.nombre AS proveedor,
                      COALESCE(ps.habilitado, 0) AS habilitado,
                      COALESCE(s.disponible, 0) AS disponible,
                      COALESCE(s.reservado, 0) AS reservado,
                      COALESCE(s.disponible, 0) - COALESCE(s.reservado, 0) AS libre
               FROM producto p
               LEFT JOIN producto_sucursal ps
                 ON ps.producto_id=p.id AND ps.sucursal_id=?
               LEFT JOIN stock s ON s.producto_id = p.id AND s.sucursal_id = ?
               LEFT JOIN minimo_vigente mv ON mv.producto_id = p.id AND mv.sucursal_id = ?
               LEFT JOIN proveedor pr ON pr.id = p.proveedor_id
               ORDER BY p.nombre""", (sucursal_id, sucursal_id, sucursal_id))

    def pares_para_alertas(self, sucursal_id=None, producto_id=None):
        """Combinaciones sucursal/producto sobre las que se recalculan las alertas."""
        return self.db.consultar(
            """SELECT s.id AS sucursal_id, p.id AS producto_id
               FROM sucursal s CROSS JOIN producto p
               WHERE (? IS NULL OR s.id = ?) AND (? IS NULL OR p.id = ?)""",
            (sucursal_id, sucursal_id, producto_id, producto_id))

    def cds(self):
        return [f["id"] for f in self.db.consultar(
            "SELECT id FROM sucursal WHERE tipo = 'CD'")]
