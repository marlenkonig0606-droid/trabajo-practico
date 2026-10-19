class Pago:
    def __init__(self, id, venta_id, medio_pago, importe, cuotas=1, referencia=None):
        self.id = id
        self.venta_id = venta_id
        self.medio_pago = medio_pago
        self.importe = importe
        self.cuotas = cuotas
        self.referencia = referencia

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["venta_id"], fila["medio_pago"],
                   fila["importe"], fila["cuotas"], fila["referencia"])

    def to_dict(self):
        return {
            "id": self.id,
            "venta_id": self.venta_id,
            "medio_pago": self.medio_pago,
            "importe": self.importe,
            "cuotas": self.cuotas,
            "referencia": self.referencia,
        }
