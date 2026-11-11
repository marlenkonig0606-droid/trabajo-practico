from database.conexion import BaseDeDatos


class LogisticaDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def transaccion(self):
        return self.db.transaccion()

    def primer_cd(self):
        return self.db.consultar_uno(
            "SELECT id FROM sucursal WHERE tipo='CD' ORDER BY id LIMIT 1")

    def crear_orden(self, origen_id, destino_id, solicitante_id, items):
        with self.db.transaccion():
            orden_id = self.db.ejecutar(
                """INSERT INTO orden_reposicion
                   (origen_id, destino_id, solicitado_por_usuario_id)
                   VALUES (?, ?, ?)""",
                (origen_id, destino_id, solicitante_id))
            for item in items:
                self.db.ejecutar(
                    """INSERT INTO detalle_orden (orden_id, producto_id, cantidad)
                       VALUES (?, ?, ?)""",
                    (orden_id, item["producto_id"], item["cantidad"]))
        return orden_id

    def obtener_orden(self, orden_id):
        return self.db.consultar_uno(
            """SELECT o.*, so.nombre AS origen, sd.nombre AS destino,
                      r.id AS remito_id, r.numero AS remito_numero, r.estado AS remito_estado
               FROM orden_reposicion o
               JOIN sucursal so ON so.id = o.origen_id
               JOIN sucursal sd ON sd.id = o.destino_id
               LEFT JOIN remito r ON r.orden_id = o.id
               WHERE o.id = ?""", (orden_id,))

    def items_orden(self, orden_id):
        return self.db.consultar(
            """SELECT d.producto_id, p.nombre, d.cantidad,
                      COALESCE((SELECT SUM(db.cantidad) FROM detalle_bulto db
                                JOIN bulto b ON b.id = db.bulto_id
                                JOIN remito r ON r.id = b.remito_id
                                WHERE r.orden_id = d.orden_id
                                  AND db.producto_id = d.producto_id
                                  AND b.estado != 'ANULADO'), 0) AS empaquetado
               FROM detalle_orden d JOIN producto p ON p.id = d.producto_id
               WHERE d.orden_id = ?""", (orden_id,))

    def listar_orden_ids(self, destino_id=None, solicitante_id=None):
        if destino_id is None and solicitante_id is None:
            return self.db.consultar("SELECT id FROM orden_reposicion ORDER BY id DESC")
        if destino_id is None:
            return self.db.consultar(
                """SELECT id FROM orden_reposicion
                   WHERE solicitado_por_usuario_id=? ORDER BY id DESC""",
                (solicitante_id,))
        if solicitante_id is None:
            return self.db.consultar(
                "SELECT id FROM orden_reposicion WHERE destino_id=? ORDER BY id DESC",
                (destino_id,))
        return self.db.consultar(
            """SELECT id FROM orden_reposicion
               WHERE destino_id=? OR solicitado_por_usuario_id=? ORDER BY id DESC""",
            (destino_id, solicitante_id))

    def crear_remito(self, numero, orden_id):
        return self.db.ejecutar(
            "INSERT INTO remito (numero, orden_id) VALUES (?, ?)", (numero, orden_id))

    def crear_bulto(self, remito_id):
        return self.db.ejecutar("INSERT INTO bulto (remito_id) VALUES (?)", (remito_id,))

    def agregar_item_bulto(self, bulto_id, producto_id, cantidad):
        self.db.ejecutar(
            """INSERT INTO detalle_bulto (bulto_id, producto_id, cantidad)
               VALUES (?, ?, ?)""", (bulto_id, producto_id, cantidad))

    def marcar_orden_en_preparacion(self, orden_id):
        self.db.ejecutar(
            "UPDATE orden_reposicion SET estado='EN_PREPARACION' WHERE id=?",
            (orden_id,))

    def precinto_existente(self, precinto):
        return self.db.consultar_uno(
            "SELECT id FROM bulto WHERE precinto=?", (precinto,))

    def asignar_precinto(self, bulto_id, precinto):
        self.db.ejecutar("UPDATE bulto SET precinto=? WHERE id=?", (precinto, bulto_id))

    def fijar_fecha_despacho(self, bulto_id):
        self.db.ejecutar(
            "UPDATE bulto SET fecha_despacho=datetime('now','localtime') WHERE id=?",
            (bulto_id,))

    def marcar_remito_despachado(self, remito_id):
        self.db.ejecutar("UPDATE remito SET estado='DESPACHADO' WHERE id=?", (remito_id,))

    def marcar_orden_despachada(self, orden_id):
        self.db.ejecutar(
            "UPDATE orden_reposicion SET estado='DESPACHADA' WHERE id=?", (orden_id,))

    def fijar_fecha_recepcion(self, bulto_id):
        self.db.ejecutar(
            "UPDATE bulto SET fecha_recepcion=datetime('now','localtime') WHERE id=?",
            (bulto_id,))

    def cerrar_remito(self, remito_id, estado):
        self.db.ejecutar("UPDATE remito SET estado=? WHERE id=?", (estado, remito_id))

    def cerrar_orden(self, orden_id):
        self.db.ejecutar(
            "UPDATE orden_reposicion SET estado='CERRADA' WHERE id=?", (orden_id,))

    def obtener_bulto(self, bulto_id):
        return self.db.consultar_uno("SELECT * FROM bulto WHERE id=?", (bulto_id,))

    def items_bulto(self, bulto_id):
        return self.db.consultar(
            "SELECT producto_id, cantidad FROM detalle_bulto WHERE bulto_id=?",
            (bulto_id,))

    def actualizar_estado_bulto(self, bulto_id, estado):
        self.db.ejecutar("UPDATE bulto SET estado=? WHERE id=?", (estado, bulto_id))

    def registrar_historial(self, bulto_id, estado, observacion):
        self.db.ejecutar(
            """INSERT INTO historial_bulto (bulto_id, estado, observacion)
               VALUES (?, ?, ?)""", (bulto_id, estado, observacion))

    def listar_historial(self, bulto_id):
        return self.db.consultar(
            """SELECT estado, fecha, observacion FROM historial_bulto
               WHERE bulto_id=? ORDER BY id""", (bulto_id,))

    def listar_bulto_ids_remito(self, remito_id):
        return self.db.consultar(
            "SELECT id FROM bulto WHERE remito_id=? ORDER BY id", (remito_id,))

    def remito_de_orden(self, orden_id):
        return self.db.consultar_uno(
            "SELECT id FROM remito WHERE orden_id=?", (orden_id,))

    def orden_de_remito(self, remito_id):
        return self.db.consultar_uno(
            """SELECT o.*, r.numero AS remito_numero FROM remito r
               JOIN orden_reposicion o ON o.id = r.orden_id WHERE r.id=?""",
            (remito_id,))

    def obtener_sucursal(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT * FROM sucursal WHERE id=?", (sucursal_id,))

    def existe_producto(self, producto_id):
        return self.db.consultar_uno(
            "SELECT id FROM producto WHERE id=?", (producto_id,))
