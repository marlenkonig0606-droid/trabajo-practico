from database.conexion import BaseDeDatos
from services.excepciones import NoEncontradoError, ReglaNegocioError
from services.medio_pago_service import obtener_creador_medio_de_pago
from services.stock_service import StockService


class VentasService:
    def __init__(self, stock_service=None):
        self.db = BaseDeDatos()
        self.stock = stock_service if stock_service is not None else StockService()

    def registrar_venta(self, sucursal_id, items, medio_pago, **datos_pago):
        sucursal = self.db.consultar_uno(
            "SELECT tipo FROM sucursal WHERE id=?", (sucursal_id,))
        if sucursal is None:
            raise ReglaNegocioError(f"No existe la sucursal {sucursal_id}")
        if sucursal["tipo"] != "LOCAL":
            raise ReglaNegocioError("Solo se pueden registrar ventas en un LOCAL")
        if not isinstance(items, list) or not items:
            raise ReglaNegocioError("La venta debe incluir al menos un producto")

        creador = obtener_creador_medio_de_pago(medio_pago)
        medio_pago_concreto = creador.crear_medio_de_pago(**datos_pago)
        items_validados = []
        productos_vistos = set()
        subtotal = 0

        for item in items:
            if not isinstance(item, dict):
                raise ReglaNegocioError("Cada producto debe incluir producto_id y cantidad")
            producto_id = item.get("producto_id")
            cantidad = item.get("cantidad")
            if isinstance(producto_id, bool) or not isinstance(producto_id, int):
                raise ReglaNegocioError("El producto_id debe ser un entero")
            if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
                raise ReglaNegocioError("La cantidad debe ser un entero positivo")
            if producto_id in productos_vistos:
                raise ReglaNegocioError(f"El producto {producto_id} está repetido")

            producto = self.db.consultar_uno(
                "SELECT precio_venta FROM producto WHERE id=?", (producto_id,))
            if producto is None:
                raise ReglaNegocioError(f"No existe el producto {producto_id}")
            precio_unitario = producto["precio_venta"]
            subtotal += precio_unitario * cantidad
            productos_vistos.add(producto_id)
            items_validados.append({
                "producto_id": producto_id,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
            })

        subtotal = round(subtotal, 2)
        total = round(medio_pago_concreto.calcular_total(subtotal), 2)
        cuotas = getattr(medio_pago_concreto, "cuotas", 1)
        referencia = datos_pago.get("referencia")

        with self.db.transaccion():
            venta_id = self.db.ejecutar(
                """INSERT INTO venta (sucursal_id, subtotal, total)
                   VALUES (?, ?, ?)""",
                (sucursal_id, subtotal, total),
            )
            for item in items_validados:
                self.db.ejecutar(
                    """INSERT INTO detalle_venta
                       (venta_id, producto_id, cantidad, precio_unitario)
                       VALUES (?, ?, ?, ?)""",
                    (venta_id, item["producto_id"], item["cantidad"],
                     item["precio_unitario"]),
                )
                self.stock.restar(
                    sucursal_id, item["producto_id"], item["cantidad"],
                    "VENTA", f"venta {venta_id}",
                )

            pago_id = self.db.ejecutar(
                """INSERT INTO pago (venta_id, medio_pago, importe, cuotas, referencia)
                   VALUES (?, ?, ?, ?, ?)""",
                (venta_id, medio_pago_concreto.nombre, total, cuotas, referencia),
            )
            numero_comprobante = self.db.consultar_uno(
                "SELECT COALESCE(MAX(numero), 0) + 1 AS numero FROM comprobante"
            )["numero"]
            comprobante_id = self.db.ejecutar(
                """INSERT INTO comprobante (venta_id, numero)
                   VALUES (?, ?)""",
                (venta_id, numero_comprobante),
            )

        return {
            "id": venta_id,
            "sucursal_id": sucursal_id,
            "subtotal": subtotal,
            "total": total,
            "pago_id": pago_id,
            "medio_pago": medio_pago_concreto.nombre,
            "comprobante_id": comprobante_id,
            "comprobante_numero": numero_comprobante,
            "items": items_validados,
        }

    def registrar_devolucion(self, venta_id, items, motivo):
        #valida que existe la venta
        venta = self.db.consultar_uno(
            """SELECT v.id, v.sucursal_id, v.subtotal, p.importe AS importe_pagado
               FROM venta v
               JOIN pago p ON p.venta_id = v.id
               WHERE v.id=?""",
            (venta_id,),
        )
        if venta is None:
            raise NoEncontradoError(f"No existe la venta {venta_id}")
        if not isinstance(items, list) or not items:
            raise ReglaNegocioError("La devolución debe incluir al menos un producto")
        if not isinstance(motivo, str) or not motivo.strip():
            raise ReglaNegocioError("El motivo de la devolución es obligatorio")

  #valida que los items pertenezcan a la venta
        detalles_venta = self.db.consultar(
            """SELECT producto_id, cantidad, precio_unitario
               FROM detalle_venta WHERE venta_id=?""",
            (venta_id,),
        )
        vendidos = {item["producto_id"]: item for item in detalles_venta}
        devoluciones_previas = self.db.consultar(
            """SELECT dd.producto_id, dd.cantidad, dd.precio_unitario
               FROM detalle_devolucion dd
               JOIN devolucion d ON d.id = dd.devolucion_id
               WHERE d.venta_id=?""",
            (venta_id,),
        )
        cantidades_devueltas = {}
        subtotal_previamente_devuelto = 0
        for detalle in devoluciones_previas:
            producto_id = detalle["producto_id"]
            cantidades_devueltas[producto_id] = (
                cantidades_devueltas.get(producto_id, 0) + detalle["cantidad"]
            )
            subtotal_previamente_devuelto += (
                detalle["cantidad"] * detalle["precio_unitario"]
            )

        items_validados = []
        productos_vistos = set()
        subtotal_devolucion = 0
        for item in items:
            if not isinstance(item, dict):
                raise ReglaNegocioError("Cada producto debe incluir producto_id y cantidad")
            producto_id = item.get("producto_id")
            cantidad = item.get("cantidad")
            if isinstance(producto_id, bool) or not isinstance(producto_id, int):
                raise ReglaNegocioError("El producto_id debe ser un entero")
            if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
                raise ReglaNegocioError("La cantidad debe ser un entero positivo")
            if producto_id in productos_vistos:
                raise ReglaNegocioError(f"El producto {producto_id} está repetido")

            detalle_vendido = vendidos.get(producto_id)
            if detalle_vendido is None:
                raise ReglaNegocioError(
                    f"El producto {producto_id} no pertenece a la venta {venta_id}"
                )
            cantidad_disponible = (
                detalle_vendido["cantidad"] - cantidades_devueltas.get(producto_id, 0)
            )
            if cantidad > cantidad_disponible:
                raise ReglaNegocioError(
                    f"No se pueden devolver {cantidad} unidades del producto {producto_id}; "
                    f"quedan {cantidad_disponible} por devolver"
                )

            precio_unitario = detalle_vendido["precio_unitario"]
            subtotal_devolucion += cantidad * precio_unitario
            productos_vistos.add(producto_id)
            items_validados.append({
                "producto_id": producto_id,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
            })

        subtotal_devolucion = round(subtotal_devolucion, 2)
        subtotal_acumulado = round(
            subtotal_previamente_devuelto + subtotal_devolucion, 2
        )
        subtotal_venta = venta["subtotal"]
        if subtotal_venta:
            total_previo_objetivo = round(
                venta["importe_pagado"] * subtotal_previamente_devuelto / subtotal_venta, 2
            )
            total_acumulado_objetivo = round(
                venta["importe_pagado"] * subtotal_acumulado / subtotal_venta, 2
            )
            total_devolucion = round(
                total_acumulado_objetivo - total_previo_objetivo, 2
            )
        else:
            total_devolucion = 0

        with self.db.transaccion():
            devolucion_id = self.db.ejecutar(
                """INSERT INTO devolucion (venta_id, motivo, total)
                   VALUES (?, ?, ?)""",
                (venta_id, motivo.strip(), total_devolucion),
            )
            for item in items_validados:
                self.db.ejecutar(
                    """INSERT INTO detalle_devolucion
                       (devolucion_id, producto_id, cantidad, precio_unitario)
                       VALUES (?, ?, ?, ?)""",
                    (devolucion_id, item["producto_id"], item["cantidad"],
                     item["precio_unitario"]),
                )
                #repone stock de productos devueltos
                self.stock.sumar(
                    venta["sucursal_id"], item["producto_id"], item["cantidad"],
                    "DEVOLUCION", f"devolucion {devolucion_id}",
                )
                #registra la devolucion de dinero como EGRESO en movimiento_caja
            movimiento_caja_id = self.db.ejecutar(
                """INSERT INTO movimiento_caja
                   (sucursal_id, devolucion_id, tipo, importe)
                   VALUES (?, ?, 'EGRESO', ?)""",
                (venta["sucursal_id"], devolucion_id, total_devolucion),
            )

        return {
            "id": devolucion_id,
            "venta_id": venta_id,
            "motivo": motivo.strip(),
            "total": total_devolucion,
            "movimiento_caja_id": movimiento_caja_id,
            "items": items_validados,
        }
