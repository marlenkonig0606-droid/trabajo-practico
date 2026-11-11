from database.conexion import BaseDeDatos


class LogisticaDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def transaccion(self):
        return self.db.transaccion()

    def primer_cd(self):
        return self.db.consultar_uno(
            "SELECT id FROM sucursal WHERE tipo='CD' AND activo=1 ORDER BY id LIMIT 1")

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
                                  AND b.estado NOT IN ('ANULADO', 'RECHAZADO', 'PERDIDO')), 0)
                      AS empaquetado
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

    def ordenes_proximas_a_vencer(self):
        return self.db.consultar(
            """SELECT id, destino_id FROM orden_reposicion
               WHERE estado IN ('PENDIENTE', 'EN_PREPARACION')
                 AND aviso_vencimiento_enviado=0
                 AND fecha_vencimiento > datetime('now', 'localtime')
                 AND fecha_vencimiento <= datetime('now', 'localtime', '+1 day')""")

    def reposicion_pendiente(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            """SELECT COALESCE(SUM(d.cantidad), 0) AS cantidad
               FROM detalle_orden d
               JOIN orden_reposicion o ON o.id=d.orden_id
               WHERE o.destino_id=? AND d.producto_id=?
                 AND o.estado IN ('PENDIENTE', 'EN_PREPARACION', 'DESPACHADA')""",
            (sucursal_id, producto_id))
        return fila["cantidad"]

    def ordenes_vencidas(self):
        return self.db.consultar(
            """SELECT id FROM orden_reposicion
               WHERE estado IN ('PENDIENTE', 'EN_PREPARACION')
                 AND fecha_vencimiento <= datetime('now', 'localtime')
               ORDER BY id""")

    def marcar_aviso_vencimiento(self, orden_id):
        return self.db.ejecutar_contando(
            """UPDATE orden_reposicion SET aviso_vencimiento_enviado=1
               WHERE id=? AND aviso_vencimiento_enviado=0
                 AND estado IN ('PENDIENTE', 'EN_PREPARACION')""", (orden_id,))

    def cerrar_orden_con_resolucion(self, orden_id, resolucion, motivo):
        return self.db.ejecutar_contando(
            """UPDATE orden_reposicion
               SET estado='CERRADA', resolucion=?, motivo_resolucion=?
               WHERE id=? AND estado IN ('PENDIENTE', 'EN_PREPARACION')""",
            (resolucion, motivo, orden_id))

    def registrar_evento(self, evento, detalle):
        self.db.ejecutar(
            "INSERT INTO evento_log (evento, detalle) VALUES (?, ?)",
            (evento, detalle))

    def registrar_notificacion(self, sucursal_id, evento, referencia, mensaje):
        self.db.ejecutar(
            """INSERT INTO notificacion
               (sucursal_id, evento, referencia, mensaje)
               VALUES (?, ?, ?, ?)""",
            (sucursal_id, evento, referencia, mensaje))

    def listar_notificaciones(self, sucursal_id):
        return self.db.consultar(
            """SELECT id, evento, referencia, mensaje, fecha, leida
               FROM notificacion WHERE sucursal_id=?
               ORDER BY id DESC LIMIT 20""",
            (sucursal_id,))

    def marcar_notificaciones_leidas(self, sucursal_id):
        return self.db.ejecutar_contando(
            "UPDATE notificacion SET leida=1 WHERE sucursal_id=? AND leida=0",
            (sucursal_id,))

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
            """SELECT id FROM bulto WHERE precinto=?
               UNION
               SELECT bulto_id AS id FROM precinto_anulado WHERE precinto=?""",
            (precinto, precinto))

    def asignar_precinto(self, bulto_id, precinto):
        self.db.ejecutar("UPDATE bulto SET precinto=? WHERE id=?", (precinto, bulto_id))

    def reabrir_bulto(self, bulto_id, precinto, motivo):
        self.db.ejecutar(
            """INSERT INTO precinto_anulado (precinto, bulto_id, motivo)
               VALUES (?, ?, ?)""",
            (precinto, bulto_id, motivo))
        self.db.ejecutar(
            """UPDATE bulto SET precinto=NULL, intento=intento+1
               WHERE id=? AND estado='PREPARADO'""",
            (bulto_id,))

    def registrar_usuario_despacho(self, bulto_id, usuario_id):
        self.db.ejecutar(
            "UPDATE bulto SET usuario_despacho_id=? WHERE id=?",
            (usuario_id, bulto_id))

    def guardar_motivo_rechazo(self, bulto_id, motivo):
        self.db.ejecutar(
            "UPDATE bulto SET observacion_rechazo=? WHERE id=?", (motivo, bulto_id))

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

    def fecha_despacho_bulto(self, bulto_id):
        return self.db.consultar_uno(
            "SELECT fecha_despacho FROM bulto WHERE id=?", (bulto_id,))

    def cerrar_remito(self, remito_id, estado):
        self.db.ejecutar("UPDATE remito SET estado=? WHERE id=?", (estado, remito_id))

    def cerrar_orden(self, orden_id):
        self.db.ejecutar(
            "UPDATE orden_reposicion SET estado='CERRADA' WHERE id=?", (orden_id,))

    def reabrir_orden(self, orden_id):
        self.db.ejecutar(
            """UPDATE orden_reposicion SET estado='EN_PREPARACION'
               WHERE id=? AND estado='CERRADA' AND resolucion IS NULL""",
            (orden_id,))

    def reabrir_remito(self, remito_id):
        self.db.ejecutar(
            """UPDATE remito SET estado='ABIERTO'
               WHERE id=? AND estado='RECHAZADO'""",
            (remito_id,))

    def obtener_bulto(self, bulto_id):
        return self.db.consultar_uno("SELECT * FROM bulto WHERE id=?", (bulto_id,))

    def items_bulto(self, bulto_id):
        return self.db.consultar(
            """SELECT producto_id, cantidad, costo_unitario
               FROM detalle_bulto WHERE bulto_id=?""",
            (bulto_id,))

    def ordenes_anteriores_pendientes(self, origen_id, orden_id, producto_id):
        return self.db.consultar(
            """SELECT o.id, d.cantidad -
                      COALESCE(SUM(CASE WHEN b.estado NOT IN
                                                    ('ANULADO', 'RECHAZADO', 'PERDIDO')
                                        THEN db.cantidad ELSE 0 END), 0) AS restante
               FROM orden_reposicion o
               JOIN detalle_orden d ON d.orden_id=o.id
               LEFT JOIN remito r ON r.orden_id=o.id
               LEFT JOIN bulto b ON b.remito_id=r.id
               LEFT JOIN detalle_bulto db
                 ON db.bulto_id=b.id AND db.producto_id=d.producto_id
               WHERE o.origen_id=? AND o.id<? AND d.producto_id=?
                 AND o.estado IN ('PENDIENTE', 'EN_PREPARACION', 'DESPACHADA')
               GROUP BY o.id, d.cantidad
               HAVING restante>0
               ORDER BY o.id""",
            (origen_id, orden_id, producto_id))

    def actualizar_estado_bulto_desde(self, bulto_id, desde_estado, nuevo_estado):
        return self.db.ejecutar_contando(
            "UPDATE bulto SET estado=? WHERE id=? AND estado=?",
            (nuevo_estado, bulto_id, desde_estado))

    def fijar_costos_bulto(self, bulto_id):
        self.db.ejecutar(
            """UPDATE detalle_bulto SET costo_unitario=(
                   SELECT precio_costo FROM producto WHERE id=detalle_bulto.producto_id)
               WHERE bulto_id=? AND costo_unitario IS NULL""",
            (bulto_id,))

    def registrar_historial(self, bulto_id, estado, observacion, desde_estado,
                            usuario_id, intento):
        self.db.ejecutar(
            """INSERT INTO historial_bulto
               (bulto_id, estado, observacion, desde_estado, usuario_id, intento)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (bulto_id, estado, observacion, desde_estado, usuario_id, intento))

    def listar_historial(self, bulto_id):
        return self.db.consultar(
            """SELECT estado, fecha, observacion, desde_estado, usuario_id, intento
               FROM historial_bulto
               WHERE bulto_id=? ORDER BY id""", (bulto_id,))

    def listar_bulto_ids_remito(self, remito_id):
        return self.db.consultar(
            "SELECT id FROM bulto WHERE remito_id=? ORDER BY id", (remito_id,))

    def remito_de_orden(self, orden_id):
        return self.db.consultar_uno(
            "SELECT id FROM remito WHERE orden_id=?", (orden_id,))

    def orden_de_remito(self, remito_id):
        return self.db.consultar_uno(
            """SELECT o.*, r.numero AS remito_numero, s.nombre AS destino
               FROM remito r
               JOIN orden_reposicion o ON o.id = r.orden_id
               JOIN sucursal s ON s.id=o.destino_id
               WHERE r.id=?""",
            (remito_id,))

    def obtener_sucursal(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT * FROM sucursal WHERE id=?", (sucursal_id,))

    def existe_producto(self, producto_id):
        return self.db.consultar_uno(
            "SELECT id, activo FROM producto WHERE id=?", (producto_id,))

    def producto_para_sucursal(self, producto_id, sucursal_id):
        return self.db.consultar_uno(
            """SELECT p.activo, COALESCE(ps.habilitado, 0) AS habilitado
               FROM producto p
               LEFT JOIN producto_sucursal ps
                 ON ps.producto_id=p.id AND ps.sucursal_id=?
               WHERE p.id=?""",
            (sucursal_id, producto_id))
