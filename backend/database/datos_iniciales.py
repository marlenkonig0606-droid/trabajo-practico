"""Carga datos de prueba si la base está vacía.  Uso:  python -m database.datos_iniciales"""
from database.conexion import BaseDeDatos
from models.categoria import Categoria
from models.producto import Producto
from models.proveedor import Proveedor
from models.stock import Stock
from models.sucursal import CentroDistribucion, LocalVenta, Sucursal
from sqlalchemy import select


def cargar():
    db = BaseDeDatos()
    with db.transaccion() as sesion:
        if sesion.scalar(select(Sucursal.id).limit(1)):
            return  # ya hay datos

        cd = CentroDistribucion(nombre="CD Central", direccion="Ruta 9 km 695")
        sesion.add_all([
            cd,
            LocalVenta(nombre="Local Centro", direccion="27 de Abril 300"),
            LocalVenta(nombre="Local Nueva Córdoba", direccion="Bv. Illia 500"),
        ])
        bebidas = Categoria(nombre="Bebidas")
        almacen = Categoria(nombre="Almacén")
        proveedor = Proveedor(cuit="30-12345678-9", razon_social="Distribuidora Norte SA")
        sesion.add_all([bebidas, almacen, proveedor])
        sesion.flush()

        productos = [
            ("BEB-001", "Agua 1.5L", bebidas.id, 400, 700, 20),
            ("BEB-002", "Gaseosa cola 2L", bebidas.id, 1100, 1900, 15),
            ("ALM-001", "Yerba 1kg", almacen.id, 2500, 3800, 10),
            ("ALM-002", "Fideos 500g", almacen.id, 600, 1050, 25),
        ]
        for codigo, nombre, categoria_id, costo, venta, minimo in productos:
            producto = Producto(
                codigo=codigo,
                nombre=nombre,
                categoria_id=categoria_id,
                proveedor_id=proveedor.id,
                precio_costo=costo,
                precio_venta=venta,
                stock_minimo=minimo,
            )
            sesion.add(producto)
            sesion.flush()
            # El stock inicial solo se carga en el CD.
            sesion.add(Stock(sucursal_id=cd.id, producto_id=producto.id, disponible=500))


if __name__ == "__main__":
    cargar()
    print("Datos iniciales cargados.")
