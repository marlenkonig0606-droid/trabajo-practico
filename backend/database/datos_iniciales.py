"""Carga datos de prueba si la base está vacía.  Uso:  python -m database.datos_iniciales"""
from database.conexion import BaseDeDatos


def cargar():
    db = BaseDeDatos()
    if db.consultar_uno("SELECT id FROM sucursal LIMIT 1"):
        return  # ya hay datos

    with db.transaccion():
        cd = db.ejecutar("INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?,?,?)",
                         ("CD Central", "Ruta 9 km 695", "CD"))
        db.ejecutar("INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?,?,?)",
                    ("Local Centro", "27 de Abril 300", "LOCAL"))
        db.ejecutar("INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?,?,?)",
                    ("Local Nueva Córdoba", "Bv. Illia 500", "LOCAL"))

        bebidas = db.ejecutar("INSERT INTO categoria (nombre) VALUES ('Bebidas')")
        almacen = db.ejecutar("INSERT INTO categoria (nombre) VALUES ('Almacén')")
        prov = db.ejecutar(
            "INSERT INTO proveedor (cuit, razon_social, nombre) VALUES (?,?,?)",
            ("30-12345678-9", "Distribuidora Norte SA", "Distribuidora Norte"),
        )

        productos = [
            ("BEB-001", "Agua 1.5L", bebidas, 400, 700, 20),
            ("BEB-002", "Gaseosa cola 2L", bebidas, 1100, 1900, 15),
            ("ALM-001", "Yerba 1kg", almacen, 2500, 3800, 10),
            ("ALM-002", "Fideos 500g", almacen, 600, 1050, 25),
        ]
        for codigo, nombre, cat, costo, venta, minimo in productos:
            pid = db.ejecutar(
                """INSERT INTO producto (codigo, nombre, categoria_id, proveedor_id,
                   precio_costo, precio_venta, stock_minimo) VALUES (?,?,?,?,?,?,?)""",
                (codigo, nombre, cat, prov, costo, venta, minimo))
            # Stock inicial solo en el CD (los locales arrancan en 0 y se abastecen con bultos)
            db.ejecutar("INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?,?,?)",
                        (cd, pid, 500))


if __name__ == "__main__":
    cargar()
    print("Datos iniciales cargados.")
