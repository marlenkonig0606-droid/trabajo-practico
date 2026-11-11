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
            "SELECT id FROM producto WHERE id=?", (producto_id,))

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

    def registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo, referencia):
        return self.db.ejecutar(
            """INSERT INTO movimiento_stock (sucursal_id, producto_id, cantidad, motivo, referencia)
               VALUES (?, ?, ?, ?, ?)""",
            (sucursal_id, producto_id, cantidad, motivo, referencia))

    def listar(self, sucursal_id):
        return self.db.consultar(
            """SELECT p.id AS producto_id, p.codigo, p.nombre, p.precio_venta,
                      p.stock_minimo,
                      COALESCE(s.disponible, 0) AS disponible,
                      COALESCE(s.reservado, 0) AS reservado,
                      COALESCE(s.disponible, 0) - COALESCE(s.reservado, 0) AS libre
               FROM producto p
               LEFT JOIN stock s ON s.producto_id = p.id AND s.sucursal_id = ?
               ORDER BY p.nombre""", (sucursal_id,))
