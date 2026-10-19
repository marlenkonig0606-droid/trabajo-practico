import sqlite3
from dao.producto_dao import ProductoDAO  
from dao.categoria_dao import CategoriaDAO
from dao.proveedor_dao import ProveedorDAO        
from excepciones import ReglaNegocioError, NoEncontradoError

class CatalogoService:
    def __init__(self):
        self.producto_dao = ProductoDAO()
        self.categoria_dao = CategoriaDAO()
        self.proveedor_dao = ProveedorDAO()

    def crear_producto(self, datos):
        nombre = datos.get("nombre", "").strip()
        precio_costo = datos.get("precio_costo")
        precio_venta = datos.get("precio_venta")
        if not nombre:
            raise ReglaNegocioError("El nombre es obligatorio")
        if precio_costo is None or precio_costo < 0:
            raise ReglaNegocioError("El precio costo no puede ser negativo")
        if precio_venta is None or precio_venta < 0:
            raise ReglaNegocioError("El precio venta no puede ser negativo")

        # 2 y 3. Llamar al DAO y traducir errores
        try:
            nuevo_id = self.producto_dao.crear(datos["codigo"], nombre, precio_costo, precio_venta)
        except sqlite3.IntegrityError:
            raise ReglaNegocioError("Ya existe un producto con ese código")

        # 4. Devolver
        return self.producto_dao.obtener_por_id(nuevo_id)


    def _validar_producto(self, datos):
        if not datos.get("codigo", "").strip():
            raise ReglaNegocioError("El código es obligatorio")
        if not datos.get("nombre", "").strip():
            raise ReglaNegocioError("El nombre es obligatorio")
        if datos.get("precio_costo") is None or datos["precio_costo"] < 0:
            raise ReglaNegocioError("El precio de costo no puede ser negativo")
        if datos.get("precio_venta") is None or datos["precio_venta"] < 0:
            raise ReglaNegocioError("El precio de venta no puede ser negativo")
        if datos.get("stock_minimo") is None or datos["stock_minimo"] < 0:
            raise ReglaNegocioError("El stock minimo no puede ser negativo")
        cat = self.categoria_dao.obtener_por_id["categoria_id"]
        if cat is None:
            raise ReglaNegocioError("La categoria indicada no existe")
        pro = self.proveedor_dao.obtener_por_id["proveedor_id"]
        if pro is None:
            raise ReglaNegocioError("El id del provedor no existe")
        # seguí vos: precio_venta, stock_minimo,
        
        # categoria_id (¿existe?), proveedor_id (¿si viene, existe?)

    def actualizar_producto(self, id_producto, datos):
        existe = self.producto_dao.obtener_por_id(id_producto)
        if not existe:
            raise NoEncontradoError("id no encontrado/inexistente")
        

        

