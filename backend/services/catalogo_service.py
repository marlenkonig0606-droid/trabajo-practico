from dao.producto_dao import ProductoDAO
from dao.categoria_dao import CategoriaDAO
from dao.proveedor_dao import ProveedorDAO
from services.excepciones import ReglaNegocioError, NoEncontradoError


class CatalogoService:
    def __init__(self):
        self.producto_dao = ProductoDAO()
        self.categoria_dao = CategoriaDAO()
        self.proveedor_dao = ProveedorDAO()

    # ------------------------------------------------------------------
    # Utilidades: convierten filas sqlite3.Row (o dicts) en dicts,
    # así app.py puede devolver todo como JSON
    # ------------------------------------------------------------------
    def _a_dict(self, fila):
        if fila is None:
            return None
        return dict(fila)

    def _a_lista(self, filas):
        return [dict(f) for f in filas]

    def _comprobar_resultado(self, resultado):
        if isinstance(resultado, tuple) and resultado and resultado[0] is False:
            detalle = resultado[1] if len(resultado) > 1 else "Error de persistencia"
            raise ReglaNegocioError(str(detalle))
        return resultado

    def _id_creado(self, resultado):
        self._comprobar_resultado(resultado)
        if not isinstance(resultado, tuple) or len(resultado) < 2 or resultado[0] is not True:
            raise ReglaNegocioError("No se pudo crear el registro")
        return resultado[1]

    # ------------------------------------------------------------------
    # PRODUCTOS
    # ------------------------------------------------------------------
    def _validar_producto(self, datos):
        if not isinstance(datos.get("codigo"), str) or not datos["codigo"].strip():
            raise ReglaNegocioError("El código es obligatorio")
        if not isinstance(datos.get("nombre"), str) or not datos["nombre"].strip():
            raise ReglaNegocioError("El nombre es obligatorio")
        for campo, mensaje in (
            ("precio_costo", "El precio de costo no puede ser negativo"),
            ("precio_venta", "El precio de venta no puede ser negativo"),
        ):
            valor = datos.get(campo)
            if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
                raise ReglaNegocioError(mensaje)
        stock_minimo = datos.get("stock_minimo")
        if (isinstance(stock_minimo, bool) or not isinstance(stock_minimo, int)
                or stock_minimo < 0):
            raise ReglaNegocioError("El stock minimo no puede ser negativo")

        if datos.get("categoria_id") is None:
            raise ReglaNegocioError("La categoria es obligatoria")
        cat = self.categoria_dao.obtener_por_id(datos["categoria_id"])
        if cat is None:
            raise ReglaNegocioError("La categoria indicada no existe")

        proveedor_id = datos.get("proveedor_id")
        if proveedor_id is not None:
            pro = self.proveedor_dao.obtener_por_id(proveedor_id)
            if pro is None:
                raise ReglaNegocioError("El id del proveedor no existe")

    def listar_productos(self):
        return self._a_lista(self.producto_dao.listar())

    def obtener_producto(self, id_producto):
        producto = self._a_dict(self.producto_dao.obtener_por_id(id_producto))
        if producto is None:
            raise NoEncontradoError(f"No existe el producto con id {id_producto}")
        return producto

    def crear_producto(self, datos):
        self._validar_producto(datos)
        resultado = self.producto_dao.crear(
            datos["codigo"], datos["nombre"], datos["categoria_id"],
            datos["precio_costo"], datos["precio_venta"],
            datos["stock_minimo"], datos.get("proveedor_id")
        )
        nuevo_id = self._id_creado(resultado)
        return self.obtener_producto(nuevo_id)

    def actualizar_producto(self, id_producto, datos):
        existe = self.producto_dao.obtener_por_id(id_producto)
        if not existe:
            raise NoEncontradoError(f"No existe el producto con id {id_producto}")

        self._validar_producto(datos)

        resultado = self.producto_dao.actualizar(
            id_producto,
            datos["codigo"], datos["nombre"], datos["categoria_id"],
            datos["precio_costo"], datos["precio_venta"],
            datos["stock_minimo"], datos.get("proveedor_id")
        )
        self._comprobar_resultado(resultado)

        return self.obtener_producto(id_producto)

    def eliminar_producto(self, id_producto):
        self.obtener_producto(id_producto)  # lanza NoEncontradoError si no existe
        resultado = self.producto_dao.eliminar(id_producto)
        self._comprobar_resultado(resultado)

    # ------------------------------------------------------------------
    # CATEGORÍAS
    # ------------------------------------------------------------------
    def _validar_categoria(self, datos):
        if not isinstance(datos.get("nombre"), str) or not datos["nombre"].strip():
            raise ReglaNegocioError("El nombre de la categoria es obligatorio")

    def listar_categorias(self):
        return self._a_lista(self.categoria_dao.listar())

    def obtener_categoria(self, id_categoria):
        categoria = self._a_dict(self.categoria_dao.obtener_por_id(id_categoria))
        if categoria is None:
            raise NoEncontradoError(f"No existe la categoria con id {id_categoria}")
        return categoria

    def crear_categoria(self, datos):
        self._validar_categoria(datos)
        resultado = self.categoria_dao.crear(
            datos["nombre"], datos.get("descripcion")
        )
        nuevo_id = self._id_creado(resultado)
        return self.obtener_categoria(nuevo_id)

    def actualizar_categoria(self, id_categoria, datos):
        self.obtener_categoria(id_categoria)
        self._validar_categoria(datos)
        resultado = self.categoria_dao.actualizar(
            id_categoria, datos["nombre"], datos.get("descripcion")
        )
        self._comprobar_resultado(resultado)
        return self.obtener_categoria(id_categoria)

    def eliminar_categoria(self, id_categoria):
        self.obtener_categoria(id_categoria)
        resultado = self.categoria_dao.eliminar(id_categoria)
        self._comprobar_resultado(resultado)

    # ------------------------------------------------------------------
    # PROVEEDORES
    # ------------------------------------------------------------------
    def _validar_proveedor(self, datos):
        for campo in ("razon_social", "cuit", "nombre"):
            if not isinstance(datos.get(campo), str) or not datos[campo].strip():
                raise ReglaNegocioError(
                    "La razon social, el CUIT y el nombre del proveedor son obligatorios"
                )

    def listar_proveedores(self):
        return self._a_lista(self.proveedor_dao.listar())

    def obtener_proveedor(self, id_proveedor):
        proveedor = self._a_dict(self.proveedor_dao.obtener_por_id(id_proveedor))
        if proveedor is None:
            raise NoEncontradoError(f"No existe el proveedor con id {id_proveedor}")
        return proveedor

    def crear_proveedor(self, datos):
        self._validar_proveedor(datos)
        resultado = self.proveedor_dao.crear(
            datos["razon_social"], datos["cuit"], datos["nombre"]
        )
        nuevo_id = self._id_creado(resultado)
        return self.obtener_proveedor(nuevo_id)

    def actualizar_proveedor(self, id_proveedor, datos):
        self.obtener_proveedor(id_proveedor)
        self._validar_proveedor(datos)
        resultado = self.proveedor_dao.actualizar(
            id_proveedor, datos["razon_social"], datos["cuit"], datos["nombre"]
        )
        self._comprobar_resultado(resultado)
        return self.obtener_proveedor(id_proveedor)

    def eliminar_proveedor(self, id_proveedor):
        self.obtener_proveedor(id_proveedor)
        resultado = self.proveedor_dao.eliminar(id_proveedor)
        self._comprobar_resultado(resultado)