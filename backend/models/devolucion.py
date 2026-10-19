class Devolucion:
    def __init__(self, id, venta_id, fecha, motivo, total):
        self.id = id
        self.venta_id = venta_id
        self.fecha = fecha
        self.motivo = motivo
        self.total = total

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["venta_id"], fila["fecha"],
                   fila["motivo"], fila["total"])

    def to_dict(self):
        return {
            "id": self.id,
            "venta_id": self.venta_id,
            "fecha": self.fecha,
            "motivo": self.motivo,
            "total": self.total,
        }


class DetalleDevolucion:
    def __init__(self, devolucion_id, producto_id, cantidad, precio_unitario):
        self.devolucion_id = devolucion_id
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.precio_unitario = precio_unitario

    def to_dict(self):
        return {
            "devolucion_id": self.devolucion_id,
            "producto_id": self.producto_id,
            "cantidad": self.cantidad,
            "precio_unitario": self.precio_unitario,
        }
