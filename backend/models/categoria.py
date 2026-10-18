class Categoria:
    def __init__(self, id, nombre):
        self.id = id
        self.nombre = nombre

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["nombre"])

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}
