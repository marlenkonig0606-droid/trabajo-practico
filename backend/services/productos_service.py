from math import isfinite

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.conexion import BaseDeDatos
from models.orm import (
    CategoriaORM,
    DetalleContenedorORM,
    DetalleOrdenORM,
    MovimientoStockORM,
    ProductoORM,
    ProveedorORM,
    StockORM,
)
from services.excepciones import NoEncontradoError, ReglaNegocioError


class ProductosService:
    CAMPOS_REQUERIDOS = (
        "codigo",
        "nombre",
        "categoria_id",
        "precio_costo",
        "precio_venta",
    )

    def __init__(self):
        self.db = BaseDeDatos()

    def listar(self):
        productos = self.db.sesion.scalars(
            select(ProductoORM).order_by(ProductoORM.nombre, ProductoORM.id)
        )
        return [self._serializar(producto) for producto in productos]

    def obtener(self, producto_id):
        producto = self.db.sesion.get(ProductoORM, producto_id)
        if producto is None:
            raise NoEncontradoError(f"No existe el producto {producto_id}")
        return self._serializar(producto)

    def crear(self, datos):
        valores = self._validar_datos(datos)
        self._validar_referencias(valores)
        self._validar_codigo(valores["codigo"])

        producto = ProductoORM(**valores)
        try:
            with self.db.transaccion() as sesion:
                sesion.add(producto)
                sesion.flush()
                producto_id = producto.id
        except IntegrityError as error:
            raise ReglaNegocioError("No se pudo crear el producto por un dato duplicado o inválido") from error
        return self.obtener(producto_id)

    def actualizar(self, producto_id, datos, parcial=False):
        producto = self._obtener_modelo(producto_id)
        valores = self._validar_datos(datos, parcial=parcial, existentes=producto)
        self._validar_referencias(valores)
        self._validar_codigo(valores["codigo"], excluir_id=producto_id)

        try:
            with self.db.transaccion() as sesion:
                producto = sesion.get(ProductoORM, producto_id)
                for campo, valor in valores.items():
                    setattr(producto, campo, valor)
        except IntegrityError as error:
            raise ReglaNegocioError("No se pudo actualizar el producto por un dato inválido") from error
        return self.obtener(producto_id)

    def eliminar(self, producto_id):
        self._obtener_modelo(producto_id)
        referencias = (
            (StockORM.producto_id, "stock"),
            (MovimientoStockORM.producto_id, "movimientos de stock"),
            (DetalleOrdenORM.producto_id, "órdenes de reposición"),
            (DetalleContenedorORM.producto_id, "contenedores"),
        )
        for columna, descripcion in referencias:
            if self.db.sesion.scalar(select(columna).where(columna == producto_id).limit(1)):
                raise ReglaNegocioError(
                    f"No se puede eliminar el producto: está asociado a {descripcion}"
                )

        try:
            with self.db.transaccion() as sesion:
                sesion.delete(sesion.get(ProductoORM, producto_id))
        except IntegrityError as error:
            raise ReglaNegocioError(
                "No se puede eliminar el producto porque tiene registros asociados"
            ) from error
        return {"mensaje": f"Producto {producto_id} eliminado"}

    def _obtener_modelo(self, producto_id):
        producto = self.db.sesion.get(ProductoORM, producto_id)
        if producto is None:
            raise NoEncontradoError(f"No existe el producto {producto_id}")
        return producto

    def _validar_datos(self, datos, parcial=False, existentes=None):
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")

        permitidos = set(self.CAMPOS_REQUERIDOS) | {"proveedor_id", "stock_minimo"}
        desconocidos = set(datos) - permitidos
        if desconocidos:
            raise ReglaNegocioError(f"Campos desconocidos: {', '.join(sorted(desconocidos))}")

        valores = {}
        for campo in permitidos:
            if campo in datos:
                valores[campo] = datos[campo]
            elif parcial and existentes is not None:
                valores[campo] = getattr(existentes, campo)
            elif campo in self.CAMPOS_REQUERIDOS:
                raise ReglaNegocioError(f"El campo '{campo}' es obligatorio")

        for campo in ("codigo", "nombre"):
            valor = valores.get(campo)
            if not isinstance(valor, str) or not valor.strip():
                raise ReglaNegocioError(f"El campo '{campo}' debe ser un texto no vacío")
            valores[campo] = valor.strip()

        valores["categoria_id"] = self._entero_positivo(
            valores["categoria_id"], "categoria_id"
        )
        proveedor_id = valores.get("proveedor_id")
        valores["proveedor_id"] = (
            None if proveedor_id in (None, "") else
            self._entero_positivo(proveedor_id, "proveedor_id")
        )
        for campo in ("precio_costo", "precio_venta"):
            valores[campo] = self._numero_no_negativo(valores[campo], campo)

        stock_minimo = valores.get("stock_minimo", 0)
        valores["stock_minimo"] = self._entero_no_negativo(stock_minimo, "stock_minimo")
        return valores

    @staticmethod
    def _entero_positivo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise ReglaNegocioError(f"El campo '{campo}' debe ser un entero mayor a cero")
        return valor

    @staticmethod
    def _entero_no_negativo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
            raise ReglaNegocioError(f"El campo '{campo}' debe ser un entero no negativo")
        return valor

    @staticmethod
    def _numero_no_negativo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            raise ReglaNegocioError(f"El campo '{campo}' debe ser un número no negativo")
        if not isfinite(valor) or valor < 0:
            raise ReglaNegocioError(f"El campo '{campo}' debe ser un número no negativo")
        return float(valor)

    def _validar_referencias(self, valores):
        if self.db.sesion.get(CategoriaORM, valores["categoria_id"]) is None:
            raise NoEncontradoError(f"No existe la categoría {valores['categoria_id']}")
        proveedor_id = valores["proveedor_id"]
        if proveedor_id is not None and self.db.sesion.get(ProveedorORM, proveedor_id) is None:
            raise NoEncontradoError(f"No existe el proveedor {proveedor_id}")

    def _validar_codigo(self, codigo, excluir_id=None):
        consulta = select(ProductoORM.id).where(ProductoORM.codigo == codigo)
        if excluir_id is not None:
            consulta = consulta.where(ProductoORM.id != excluir_id)
        if self.db.sesion.scalar(consulta.limit(1)) is not None:
            raise ReglaNegocioError(f"Ya existe un producto con el código '{codigo}'")

    @staticmethod
    def _serializar(producto):
        return {
            "id": producto.id,
            "codigo": producto.codigo,
            "nombre": producto.nombre,
            "categoria_id": producto.categoria_id,
            "proveedor_id": producto.proveedor_id,
            "precio_costo": producto.precio_costo,
            "precio_venta": producto.precio_venta,
            "stock_minimo": producto.stock_minimo,
        }
