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

    def __str__(self):
        return f"{self.codigo} - {self.nombre} (${self.precio_venta})"