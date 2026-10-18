class Producto:
    def __init__(self, id, codigo, nombre, categoria_id, precio_costo, precio_venta,
                 stock_minimo=0, proveedor_id=None):
        if not nombre:
            raise ValueError("El nombre no puede estar vacío")
        if precio_venta < precio_costo:
            raise ValueError("El precio de venta no puede ser menor al de costo")

        self.id = id
        self.codigo = codigo
        self.nombre = nombre
        self.categoria_id = categoria_id
        self.proveedor_id = proveedor_id
        self.precio_costo = precio_costo
        self.precio_venta = precio_venta
        self.stock_minimo = stock_minimo

    def margen_unitario(self):
        return self.precio_venta - self.precio_costo

    @classmethod
    def desde_fila(cls, fila):
        return cls(fila["id"], fila["codigo"], fila["nombre"], fila["categoria_id"],
                   fila["precio_costo"], fila["precio_venta"], fila["stock_minimo"],
                   fila["proveedor_id"])

    def to_dict(self):
        return {**self.__dict__, "margen_unitario": self.margen_unitario()}

    def __str__(self):
        return f"Producto(id={self.id}, codigo={self.codigo}, nombre={self.nombre}, "

# TODO (vos): clases Categoria y Proveedor siguiendo el mismo estilo.
