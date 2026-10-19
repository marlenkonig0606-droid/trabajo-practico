class Comprobante:
    def __init__(self, id, venta_id, numero, fecha):
        self.id = id
        self.venta_id = venta_id
        self.numero = numero
        self.fecha = fecha

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["venta_id"], fila["numero"], fila["fecha"])

    def to_dict(self):
        return {
            "id": self.id,
            "venta_id": self.venta_id,
            "numero": self.numero,
            "fecha": self.fecha,
        }
