from dao.producto_dao import ProductoDAO
from dao.categoria_dao import CategoriaDAO
from dao.proveedor_dao import ProveedorDAO
from dao.sucursal_dao import SucursalDAO
from services.excepciones import ReglaNegocioError, NoEncontradoError
from models.producto import normalizar_codigo
from models.proveedor import normalizar_cuit


class CatalogoService:
    def __init__(self):
        self.producto_dao = ProductoDAO()
        self.categoria_dao = CategoriaDAO()
        self.proveedor_dao = ProveedorDAO()
        self.sucursal_dao = SucursalDAO()

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

    def _validar_producto(self, datos, id_producto=None):
        if not isinstance(datos.get("codigo"), str):
            raise ReglaNegocioError("El código es obligatorio")
        codigo = normalizar_codigo(datos["codigo"])
        if not codigo:
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
        if campo == "precio_venta" and valor == 0:
                raise ReglaNegocioError("El precio de venta debe ser mayor que cero")
        stock_minimo = datos.get("stock_minimo")
        if (isinstance(stock_minimo, bool) or not isinstance(stock_minimo, int)
                or stock_minimo < 0):
            raise ReglaNegocioError("El stock minimo no puede ser negativo")

        if datos.get("categoria_id") is None:
            raise ReglaNegocioError("La categoria es obligatoria")
        cat = self.categoria_dao.obtener_por_id(datos["categoria_id"])
        if cat is None:
            raise ReglaNegocioError("La categoria indicada no existe")
        if not cat["activo"]:
            categoria_actual_id = None
            if id_producto is not None:
                producto_actual = self.producto_dao.obtener_por_id(id_producto)
                categoria_actual_id = producto_actual["categoria_id"]
            if categoria_actual_id != datos["categoria_id"]:
                raise ReglaNegocioError(
                    "Solo se pueden asignar categorías activas a productos")

        proveedor_id = datos.get("proveedor_id")
        if proveedor_id is not None:
            pro = self.proveedor_dao.obtener_por_id(proveedor_id)
            if pro is None:
                raise ReglaNegocioError("El id del proveedor no existe")
            proveedor_actual_id = None
            if id_producto is not None:
                producto_actual = self.producto_dao.obtener_por_id(id_producto)
                proveedor_actual_id = producto_actual["proveedor_id"]
            if not pro["activo"] and proveedor_actual_id != proveedor_id:
                raise ReglaNegocioError(
                    "Solo se pueden seleccionar proveedores activos para un producto")
        return codigo

    def listar_productos(self):
        return self._a_lista(self.producto_dao.listar())

    def obtener_producto(self, id_producto):
        producto = self._a_dict(self.producto_dao.obtener_por_id(id_producto))
        if producto is None:
            raise NoEncontradoError(f"No existe el producto con id {id_producto}")
        return producto

    def crear_producto(self, datos):
        codigo = self._validar_producto(datos)
        resultado = self.producto_dao.crear(
            codigo, datos["nombre"], datos["categoria_id"],
            datos["precio_costo"], datos["precio_venta"],
            datos["stock_minimo"], datos.get("proveedor_id")
        )
        nuevo_id = self._id_creado(resultado)
        return self.obtener_producto(nuevo_id)

    def actualizar_producto(self, id_producto, datos):
        existe = self.producto_dao.obtener_por_id(id_producto)
        if not existe:
            raise NoEncontradoError(f"No existe el producto con id {id_producto}")

        codigo = self._validar_producto(datos, id_producto)

        resultado = self.producto_dao.actualizar(
            id_producto,
            codigo, datos["nombre"], datos["categoria_id"],
            datos["precio_costo"], datos["precio_venta"],
            datos["stock_minimo"], datos.get("proveedor_id")
        )
        self._comprobar_resultado(resultado)

        return self.obtener_producto(id_producto)

    def eliminar_producto(self, id_producto):
        self.cambiar_estado_producto(id_producto, False)

    def cambiar_estado_producto(self, id_producto, activo):
        self.obtener_producto(id_producto)
        if not isinstance(activo, bool):
            raise ReglaNegocioError("El estado activo debe ser verdadero o falso")
        if not activo:
            stock = self.producto_dao.stock_activo(id_producto)
            if stock["disponible"] > 0 or stock["reservado"] > 0:
                raise ReglaNegocioError(
                    "No se puede dar de baja un producto con stock disponible o reservado")
            en_transito = self.producto_dao.tiene_bultos_pendientes_en_sucursal(
                None, id_producto)
            if en_transito:
                raise ReglaNegocioError(
                    "No se puede dar de baja un producto con bultos en tránsito o pendientes de verificar")
        resultado = self.producto_dao.cambiar_estado(id_producto, activo)
        self._comprobar_resultado(
            (resultado > 0, "No se pudo cambiar el estado del producto"))

    def productos_de_sucursal(self, sucursal_id):
        sucursal = self.obtener_sucursal(sucursal_id)
        if sucursal["tipo"] != "LOCAL":
            raise ReglaNegocioError("La habilitación de productos corresponde a un local")
        return self.producto_dao.listar_para_sucursal(
            sucursal_id, solo_habilitados=False)

    def productos_habilitados_sucursal(self, sucursal_id):
        sucursal = self.obtener_sucursal(sucursal_id)
        if sucursal["tipo"] != "LOCAL" or not sucursal["activo"]:
            raise ReglaNegocioError("Solo un local activo puede consultar sus productos")
        return self.producto_dao.listar_para_sucursal(
            sucursal_id, solo_habilitados=True)

    def cambiar_habilitacion_producto(self, sucursal_id, producto_id, habilitado):
        sucursal = self.obtener_sucursal(sucursal_id)
        if sucursal["tipo"] != "LOCAL" or not sucursal["activo"]:
            raise ReglaNegocioError(
                "Solo un local activo puede habilitar o deshabilitar productos")
        producto = self.obtener_producto(producto_id)
        if not isinstance(habilitado, bool):
            raise ReglaNegocioError("habilitado debe ser verdadero o falso")
        if not habilitado:
            stock = self.producto_dao.stock_en_sucursal(sucursal_id, producto_id)
            if stock["disponible"] > 0 or stock["reservado"] > 0:
                raise ReglaNegocioError(
                    "Transferí o ajustá el stock del producto antes de deshabilitarlo")
            if self.producto_dao.tiene_bultos_pendientes_en_sucursal(
                    sucursal_id, producto_id):
                raise ReglaNegocioError(
                    "No se puede deshabilitar un producto con bultos en tránsito o pendientes de verificar")
        resultado = self.producto_dao.cambiar_habilitacion(
            sucursal_id, producto_id, habilitado)
        if resultado == 0:
            raise ReglaNegocioError(
                "No existe una habilitación de producto para este local")
        return {
            "sucursal_id": sucursal_id,
            "producto_id": producto_id,
            "nombre": producto["nombre"],
            "habilitado": habilitado,
        }

    def _validar_sucursal(self, datos):
        if not isinstance(datos.get("nombre"), str) or not datos["nombre"].strip():
            raise ReglaNegocioError("El nombre de la sucursal es obligatorio")
        if not isinstance(datos.get("direccion"), str) or not datos["direccion"].strip():
            raise ReglaNegocioError("La dirección de la sucursal es obligatoria")
        if datos.get("tipo") not in ("CD", "LOCAL"):
            raise ReglaNegocioError("El tipo debe ser CD o LOCAL")

    def listar_sucursales(self, solo_activas=False):
        return self._a_lista(self.sucursal_dao.listar(solo_activas))

    def obtener_sucursal(self, id_sucursal):
        sucursal = self._a_dict(self.sucursal_dao.obtener_por_id(id_sucursal))
        if sucursal is None:
            raise NoEncontradoError(f"No existe la sucursal con id {id_sucursal}")
        return sucursal

    def crear_sucursal(self, datos):
        self._validar_sucursal(datos)
        if datos["tipo"] != "CD" and self._cantidad_cd() == 0:
            raise ReglaNegocioError(
                "Debe existir al menos un Centro de Distribución: la primera sucursal debe ser CD")
        resultado = self.sucursal_dao.crear(
            datos["nombre"].strip(), datos["direccion"].strip(), datos["tipo"])
        return self.obtener_sucursal(self._id_creado(resultado))

    def eliminar_sucursal(self, id_sucursal):
        self.cambiar_estado_sucursal(id_sucursal, False)

    def cambiar_estado_sucursal(self, id_sucursal, activo):
        sucursal = self.obtener_sucursal(id_sucursal)
        if not isinstance(activo, bool):
            raise ReglaNegocioError("El estado activo debe ser verdadero o falso")
        if not activo and sucursal["activo"]:
            if sucursal["tipo"] == "CD" and self._cantidad_cd() <= 1:
                raise ReglaNegocioError(
                    "Debe quedar al menos un Centro de Distribución activo")
            if (sucursal["tipo"] == "LOCAL"
                    and self.sucursal_dao.tiene_bultos_pendientes_de_recepcion(id_sucursal)):
                raise ReglaNegocioError(
                    "No se puede desactivar el local mientras tenga bultos en tránsito "
                    "o pendientes de verificación")
        resultado = self.sucursal_dao.cambiar_estado(id_sucursal, activo)
        self._comprobar_resultado((resultado > 0, "No se pudo cambiar el estado de la sucursal"))
        return self.obtener_sucursal(id_sucursal)

    def _cantidad_cd(self):
        sucursales = self.listar_sucursales(solo_activas=True)
        return sum(1 for sucursal in sucursales if sucursal["tipo"] == "CD")

    def actualizar_sucursal(self, id_sucursal, datos):
        sucursal = self.obtener_sucursal(id_sucursal)
        self._validar_sucursal(datos)
        if (sucursal["activo"] and sucursal["tipo"] == "CD"
                and datos["tipo"] != "CD" and self._cantidad_cd() <= 1):
            raise ReglaNegocioError(
                "Debe quedar al menos un Centro de Distribución activo")
        resultado = self.sucursal_dao.actualizar(
            id_sucursal, datos["nombre"].strip(), datos["direccion"].strip(),
            datos["tipo"]
        )
        self._comprobar_resultado(resultado)
        return self.obtener_sucursal(id_sucursal)

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
        return self.cambiar_estado_categoria(id_categoria, False)

    def cambiar_estado_categoria(self, id_categoria, activo):
        self.obtener_categoria(id_categoria)
        if not isinstance(activo, bool):
            raise ReglaNegocioError("El estado activo debe ser verdadero o falso")
        resultado = self.categoria_dao.cambiar_estado(id_categoria, activo)
        self._comprobar_resultado(
            (resultado > 0, "No se pudo cambiar el estado de la categoría"))
        return self.obtener_categoria(id_categoria)

    def _validar_proveedor(self, datos):
        for campo in ("razon_social", "cuit", "nombre"):
            if not isinstance(datos.get(campo), str) or not datos[campo].strip():
                raise ReglaNegocioError(
                    "La razon social, el CUIT y el nombre del proveedor son obligatorios")
        cuit = normalizar_cuit(datos["cuit"])
        if len(cuit) != 11:
            raise ReglaNegocioError("El CUIT debe contener 11 dígitos")
        datos["cuit"] = cuit

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
            datos["razon_social"], datos["cuit"], datos["nombre"])
        nuevo_id = self._id_creado(resultado)
        return self.obtener_proveedor(nuevo_id)

    def actualizar_proveedor(self, id_proveedor, datos):
        self.obtener_proveedor(id_proveedor)
        self._validar_proveedor(datos)
        resultado = self.proveedor_dao.actualizar(
            id_proveedor, datos["razon_social"], datos["cuit"], datos["nombre"])
        self._comprobar_resultado(resultado)
        return self.obtener_proveedor(id_proveedor)

    def cambiar_estado_proveedor(self, id_proveedor, activo):
        self.obtener_proveedor(id_proveedor)
        if not isinstance(activo, bool):
            raise ReglaNegocioError("El estado activo debe ser verdadero o falso")
        resultado = self.proveedor_dao.cambiar_estado(id_proveedor, activo)
        self._comprobar_resultado((resultado > 0, "No se pudo cambiar el estado del proveedor"))
        return self.obtener_proveedor(id_proveedor)

    def eliminar_proveedor(self, id_proveedor):
        return self.cambiar_estado_proveedor(id_proveedor, False)