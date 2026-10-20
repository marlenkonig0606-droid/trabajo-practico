class Venta:
    def __init__(self, id, sucursal_id, fecha, subtotal, total):
        self.id = id
        self.sucursal_id = sucursal_id
        self.fecha = fecha
        self.subtotal = subtotal
        self.total = total

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["sucursal_id"], fila["fecha"],
                   fila["subtotal"], fila["total"])

    def to_dict(self):
        return {
            "id": self.id,
            "sucursal_id": self.sucursal_id,
            "fecha": self.fecha,
            "subtotal": self.subtotal,
            "total": self.total,
        }


class DetalleVenta:
    def __init__(self, venta_id, producto_id, cantidad, precio_unitario):
        self.venta_id = venta_id
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.precio_unitario = precio_unitario

    def to_dict(self):
        return {
            "venta_id": self.venta_id,
            "producto_id": self.producto_id,
            "cantidad": self.cantidad,
            "precio_unitario": self.precio_unitario,
        }
