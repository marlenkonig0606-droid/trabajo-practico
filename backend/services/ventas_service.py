from dao.ventas_dao import VentasDAO
from database.conexion import BaseDeDatos
from services.excepciones import NoEncontradoError, ReglaNegocioError
from services.medio_pago_service import obtener_creador_medio_de_pago
from services.stock_service import StockService


class VentasService:
    def __init__(self, stock_service=None):
        self.db = BaseDeDatos()
        self.dao = VentasDAO(self.db)
        self.stock = stock_service if stock_service is not None else StockService()

    def listar_ventas(self, sucursal_id=None):
        return self.dao.listar(sucursal_id)

    def obtener_venta(self, venta_id):
        venta = self.dao.obtener(venta_id)
        if venta is None:
            raise NoEncontradoError(f"No existe la venta {venta_id}")

        venta["items"] = self.dao.items_venta(venta_id)
        venta["devoluciones"] = self.dao.devoluciones_venta(venta_id)
        return venta

    def sucursal_de_venta(self, venta_id):
        return self.dao.sucursal_de_venta(venta_id)

    def registrar_venta(self, sucursal_id, items, medio_pago, **datos_pago):
        sucursal = self.dao.tipo_sucursal(sucursal_id)
        if sucursal is None:
            raise ReglaNegocioError(f"No existe la sucursal {sucursal_id}")
        if not sucursal["activo"]:
            raise ReglaNegocioError("No se pueden registrar ventas en una sucursal inactiva")
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

            producto = self.dao.precio_producto(producto_id, sucursal_id)
            if producto is None:
                raise ReglaNegocioError(f"No existe el producto {producto_id}")
            if not producto["activo"]:
                raise ReglaNegocioError(f"El producto {producto_id} está inactivo")
            if not producto["habilitado"]:
                raise ReglaNegocioError(
                    f"El producto {producto_id} no está habilitado para este local")
            precio_unitario = producto["precio_venta"]
            if precio_unitario is None or precio_unitario <= 0:
                raise ReglaNegocioError(
                    f"El producto {producto_id} no tiene un precio de venta válido")
            subtotal += precio_unitario * cantidad
            productos_vistos.add(producto_id)
            items_validados.append({
                "producto_id": producto_id,
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "costo_unitario": producto["precio_costo"],
            })

        subtotal = round(subtotal, 2)
        total = round(medio_pago_concreto.calcular_total(subtotal), 2)
        cuotas = getattr(medio_pago_concreto, "cuotas", 1)
        referencia = datos_pago.get("referencia")

        with self.dao.transaccion():
            venta_id = self.dao.crear_venta(sucursal_id, subtotal, total)
            for item in items_validados:
                self.dao.crear_detalle_venta(
                    venta_id, item["producto_id"], item["cantidad"],
                    item["precio_unitario"], item["costo_unitario"])
                self.stock.restar(
                    sucursal_id, item["producto_id"], item["cantidad"],
                    "VENTA", f"venta {venta_id}",
                    item["costo_unitario"],
                )

            pago_id = self.dao.crear_pago(
                venta_id, medio_pago_concreto.nombre, total, cuotas, referencia)
            numero_comprobante = self.dao.siguiente_numero_comprobante()
            comprobante_id = self.dao.crear_comprobante(venta_id, numero_comprobante)

        return {
            "id": venta_id,
            "sucursal_id": sucursal_id,
            "subtotal": subtotal,
            "total": total,
            "pago_id": pago_id,
            "medio_pago": medio_pago_concreto.nombre,
            "comprobante_id": comprobante_id,
            "comprobante_numero": numero_comprobante,
            "items": [
                {clave: valor for clave, valor in item.items()
                 if clave != "costo_unitario"}
                for item in items_validados
            ],
        }

    def registrar_devolucion(self, venta_id, items, motivo):
        #valida que existe la venta
        venta = self.dao.obtener_para_devolucion(venta_id)
        if venta is None:
            raise NoEncontradoError(f"No existe la venta {venta_id}")
        if self._devolucion_vencida(venta["fecha"]):
            raise ReglaNegocioError("No se permiten devoluciones luego de los 30 días")
        if not isinstance(items, list) or not items:
            raise ReglaNegocioError("La devolución debe incluir al menos un producto")
        if not isinstance(motivo, str) or not motivo.strip():
            raise ReglaNegocioError("El motivo de la devolución es obligatorio")

  #valida que los items pertenezcan a la venta
        detalles_venta = self.dao.detalles_para_devolucion(venta_id)
        vendidos = {item["producto_id"]: item for item in detalles_venta}
        devoluciones_previas = self.dao.devoluciones_previas(venta_id)
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
                "costo_unitario": detalle_vendido["costo_unitario"],
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

        with self.dao.transaccion():
            venta_actual = self.dao.obtener_para_devolucion(venta_id)
            if venta_actual is None:
                raise NoEncontradoError(f"No existe la venta {venta_id}")
            if self._devolucion_vencida(venta_actual["fecha"]):
                raise ReglaNegocioError("No se permiten devoluciones luego de los 30 días")
            devoluciones_actuales = self.dao.devoluciones_previas(venta_id)
            cantidades_actuales = {}
            subtotal_actual = 0
            for detalle in devoluciones_actuales:
                cantidades_actuales[detalle["producto_id"]] = (
                    cantidades_actuales.get(detalle["producto_id"], 0)
                    + detalle["cantidad"])
                subtotal_actual += detalle["cantidad"] * detalle["precio_unitario"]
            for item in items_validados:
                cantidad_restante = (
                    vendidos[item["producto_id"]]["cantidad"]
                    - cantidades_actuales.get(item["producto_id"], 0))
                if item["cantidad"] > cantidad_restante:
                    raise ReglaNegocioError(
                        f"No se pueden devolver {item['cantidad']} unidades del producto "
                        f"{item['producto_id']}; quedan {cantidad_restante} por devolver")
            subtotal_actualizado = round(subtotal_actual + subtotal_devolucion, 2)
            if venta_actual["subtotal"]:
                objetivo_previo = round(
                    venta_actual["importe_pagado"] * subtotal_actual
                    / venta_actual["subtotal"], 2)
                objetivo_actualizado = round(
                    venta_actual["importe_pagado"] * subtotal_actualizado
                    / venta_actual["subtotal"], 2)
                total_devolucion = round(objetivo_actualizado - objetivo_previo, 2)
            else:
                total_devolucion = 0
            devolucion_id = self.dao.crear_devolucion(
                venta_id, motivo.strip(), total_devolucion)
            for item in items_validados:
                self.dao.crear_detalle_devolucion(
                    devolucion_id, item["producto_id"], item["cantidad"],
                    item["precio_unitario"], item["costo_unitario"])
                #repone stock de productos devueltos
                self.stock.sumar(
                    venta["sucursal_id"], item["producto_id"], item["cantidad"],
                    "DEVOLUCION", f"devolucion {devolucion_id}",
                    item["costo_unitario"],
                )
                #registra la devolucion de dinero como EGRESO en movimiento_caja
            movimiento_caja_id = self.dao.crear_movimiento_caja(
                venta["sucursal_id"], devolucion_id, total_devolucion)

        return {
            "id": devolucion_id,
            "venta_id": venta_id,
            "motivo": motivo.strip(),
            "total": total_devolucion,
            "movimiento_caja_id": movimiento_caja_id,
            "items": items_validados,
        }

    @staticmethod
    def _devolucion_vencida(fecha_venta):
        from datetime import datetime, timedelta

        fecha = datetime.fromisoformat(fecha_venta)
        if fecha.tzinfo is None:
            fecha_limite = fecha + timedelta(days=30)
            return datetime.now() > fecha_limite
        return datetime.now(fecha.tzinfo) > fecha + timedelta(days=30)
