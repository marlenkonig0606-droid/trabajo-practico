from database.conexion import BaseDeDatos


class ObservadoresDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def transaccion(self):
        return self.db.transaccion()

    def stock_minimo(self, producto_id):
        return self.db.consultar_uno(
            "SELECT stock_minimo FROM producto WHERE id=?", (producto_id,))

    def alerta_pendiente(self, sucursal_id, producto_id):
        return self.db.consultar_uno(
            """SELECT id FROM alerta_stock
               WHERE sucursal_id=? AND producto_id=? AND resuelta=0""",
            (sucursal_id, producto_id))

    def actualizar_alerta(self, alerta_id, libre):
        self.db.ejecutar("UPDATE alerta_stock SET libre=? WHERE id=?", (libre, alerta_id))

    def crear_alerta(self, sucursal_id, producto_id, libre, minimo):
        self.db.ejecutar(
            """INSERT INTO alerta_stock (sucursal_id, producto_id, libre, minimo)
               VALUES (?, ?, ?, ?)""",
            (sucursal_id, producto_id, libre, minimo))

    def resolver_alerta(self, alerta_id):
        self.db.ejecutar(
            """UPDATE alerta_stock
               SET resuelta=1, fecha_resolucion=datetime('now','localtime') WHERE id=?""",
            (alerta_id,))

    def registrar_evento(self, evento, detalle):
        self.db.ejecutar(
            "INSERT INTO evento_log (evento, detalle) VALUES (?, ?)",
            (evento, detalle))

    def listar_alertas(self, filtro, parametros):
        return self.db.consultar(f"""
            SELECT a.id, s.nombre AS sucursal, p.codigo, p.nombre AS producto,
                   a.libre, a.minimo, a.fecha, a.resuelta, a.fecha_resolucion
            FROM alerta_stock a
            JOIN sucursal s ON s.id = a.sucursal_id
            JOIN producto p ON p.id = a.producto_id
            {filtro}
            ORDER BY a.id DESC""", parametros)

    def listar_eventos(self, limite):
        return self.db.consultar(
            "SELECT evento, detalle, fecha FROM evento_log ORDER BY id DESC LIMIT ?",
            (limite,))
