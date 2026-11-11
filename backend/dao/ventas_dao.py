from database.conexion import BaseDeDatos


class VentasDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def transaccion(self):
        return self.db.transaccion()

    def listar(self, sucursal_id=None):
        return self.db.consultar(
            """SELECT v.id, v.sucursal_id, s.nombre AS sucursal, v.fecha,
                      v.subtotal, v.total, p.medio_pago, p.importe AS importe_pagado,
                      c.numero AS comprobante_numero
               FROM venta v
               JOIN sucursal s ON s.id = v.sucursal_id
               JOIN pago p ON p.venta_id = v.id
               JOIN comprobante c ON c.venta_id = v.id
               WHERE (? IS NULL OR v.sucursal_id = ?)
               ORDER BY v.id DESC""",
            (sucursal_id, sucursal_id))

    def obtener(self, venta_id):
        return self.db.consultar_uno(
            """SELECT v.id, v.sucursal_id, s.nombre AS sucursal, v.fecha,
                      v.subtotal, v.total, p.medio_pago, p.importe AS importe_pagado,
                      p.cuotas, p.referencia, c.numero AS comprobante_numero
               FROM venta v
               JOIN sucursal s ON s.id = v.sucursal_id
               JOIN pago p ON p.venta_id = v.id
               JOIN comprobante c ON c.venta_id = v.id
               WHERE v.id=?""", (venta_id,))

    def items_venta(self, venta_id):
        return self.db.consultar(
            """SELECT dv.producto_id, p.nombre, dv.cantidad, dv.precio_unitario
               FROM detalle_venta dv
               JOIN producto p ON p.id = dv.producto_id
               WHERE dv.venta_id=?
               ORDER BY p.nombre""", (venta_id,))

    def devoluciones_venta(self, venta_id):
        return self.db.consultar(
            """SELECT d.id, d.fecha, d.motivo, d.total AS total_devolucion,
                      dd.producto_id, p.nombre, dd.cantidad, dd.precio_unitario
               FROM devolucion d
               JOIN detalle_devolucion dd ON dd.devolucion_id = d.id
               JOIN producto p ON p.id = dd.producto_id
               WHERE d.venta_id=?
               ORDER BY d.id, p.nombre""", (venta_id,))

    def tipo_sucursal(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT tipo, activo FROM sucursal WHERE id=?", (sucursal_id,))

    def precio_producto(self, producto_id, sucursal_id):
        return self.db.consultar_uno(
            """SELECT p.precio_venta, p.precio_costo, p.activo,
                      COALESCE(ps.habilitado, 0) AS habilitado
               FROM producto p
               LEFT JOIN producto_sucursal ps
                 ON ps.producto_id=p.id AND ps.sucursal_id=?
               WHERE p.id=?""", (sucursal_id, producto_id))

    def crear_venta(self, sucursal_id, subtotal, total):
        return self.db.ejecutar(
            """INSERT INTO venta (sucursal_id, subtotal, total)
               VALUES (?, ?, ?)""", (sucursal_id, subtotal, total))

    def crear_detalle_venta(self, venta_id, producto_id, cantidad, precio_unitario,
                            costo_unitario):
        return self.db.ejecutar(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario, costo_unitario)
               VALUES (?, ?, ?, ?, ?)""",
            (venta_id, producto_id, cantidad, precio_unitario, costo_unitario))

    def siguiente_numero_comprobante(self):
        return self.db.consultar_uno(
            "SELECT COALESCE(MAX(numero), 0) + 1 AS numero FROM comprobante")["numero"]

    def crear_pago(self, venta_id, medio_pago, importe, cuotas, referencia):
        return self.db.ejecutar(
            """INSERT INTO pago (venta_id, medio_pago, importe, cuotas, referencia)
               VALUES (?, ?, ?, ?, ?)""",
            (venta_id, medio_pago, importe, cuotas, referencia))

    def crear_comprobante(self, venta_id, numero):
        return self.db.ejecutar(
            """INSERT INTO comprobante (venta_id, numero)
               VALUES (?, ?)""", (venta_id, numero))

    def obtener_para_devolucion(self, venta_id):
        return self.db.consultar_uno(
            """SELECT v.id, v.sucursal_id, v.fecha, v.subtotal,
                      p.importe AS importe_pagado
               FROM venta v
               JOIN pago p ON p.venta_id = v.id
               WHERE v.id=?""", (venta_id,))

    def sucursal_de_venta(self, venta_id):
        return self.db.consultar_uno(
               "SELECT sucursal_id FROM venta WHERE id=?", (venta_id,))

    def detalles_para_devolucion(self, venta_id):
        return self.db.consultar(
            """SELECT producto_id, cantidad, precio_unitario, costo_unitario
               FROM detalle_venta WHERE venta_id=?""", (venta_id,))

    def devoluciones_previas(self, venta_id):
        return self.db.consultar(
            """SELECT dd.producto_id, dd.cantidad, dd.precio_unitario
               FROM detalle_devolucion dd
               JOIN devolucion d ON d.id = dd.devolucion_id
               WHERE d.venta_id=?""", (venta_id,))

    def crear_devolucion(self, venta_id, motivo, total):
        return self.db.ejecutar(
            """INSERT INTO devolucion (venta_id, motivo, total)
               VALUES (?, ?, ?)""", (venta_id, motivo, total))

    def crear_detalle_devolucion(
            self, devolucion_id, producto_id, cantidad, precio_unitario, costo_unitario):
        return self.db.ejecutar(
            """INSERT INTO detalle_devolucion
               (devolucion_id, producto_id, cantidad, precio_unitario, costo_unitario)
               VALUES (?, ?, ?, ?, ?)""",
            (devolucion_id, producto_id, cantidad, precio_unitario, costo_unitario))

    def crear_movimiento_caja(self, sucursal_id, devolucion_id, importe):
        return self.db.ejecutar(
            """INSERT INTO movimiento_caja
               (sucursal_id, devolucion_id, tipo, importe)
               VALUES (?, ?, 'EGRESO', ?)""", (sucursal_id, devolucion_id, importe))
