from database.conexion import BaseDeDatos
from services.excepciones import ReglaNegocioError
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
        total = medio_pago_concreto.calcular_total(subtotal)
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
        raise NotImplementedError("registrar_devolucion: completar")
