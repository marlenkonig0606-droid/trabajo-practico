class Proveedor:
    def __init__(self, id, cuit, razon_social):
        self.id = id
        self.cuit = cuit
        self.razon_social = razon_social

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["cuit"], fila["razon_social"])

    def to_dict(self):
        return {
            "id": self.id,
            "cuit": self.cuit,
            "razon_social": self.razon_social,
        }
