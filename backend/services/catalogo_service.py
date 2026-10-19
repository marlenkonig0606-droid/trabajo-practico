from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from database.conexion import BaseDeDatos
from models.categoria import Categoria
from models.producto import Producto
from models.proveedor import Proveedor
from services.excepciones import NoEncontradoError, ReglaNegocioError


class CatalogoService:
    def __init__(self):
        self.db = BaseDeDatos()

    def listar_categorias(self):
        filas = self.db.sesion.scalars(
            select(Categoria).order_by(Categoria.nombre, Categoria.id)
        )
        return [fila.to_dict() for fila in filas]

    def obtener_categoria(self, categoria_id):
        return self._categoria_modelo(categoria_id).to_dict()

    def crear_categoria(self, datos):
        valores = self._validar_texto(datos, "nombre")
        self._validar_nombre_categoria(valores["nombre"])
        entidad = Categoria(**valores)
        try:
            with self.db.transaccion() as sesion:
                sesion.add(entidad)
                sesion.flush()
                categoria_id = entidad.id
        except IntegrityError as error:
            raise ReglaNegocioError(
                f"Ya existe una categoría con el nombre '{valores['nombre']}'"
            ) from error
        return self.obtener_categoria(categoria_id)

    def actualizar_categoria(self, categoria_id, datos, parcial=False):
        categoria = self._categoria_modelo(categoria_id)
        valores = self._validar_texto(
            datos, "nombre", parcial=parcial, nombre_actual=categoria.nombre
        )
        self._validar_nombre_categoria(valores["nombre"], excluir_id=categoria_id)
        try:
            with self.db.transaccion() as sesion:
                sesion.get(Categoria, categoria_id).nombre = valores["nombre"]
        except IntegrityError as error:
            raise ReglaNegocioError(
                f"Ya existe una categoría con el nombre '{valores['nombre']}'"
            ) from error
        return self.obtener_categoria(categoria_id)

    def eliminar_categoria(self, categoria_id):
        categoria = self._categoria_modelo(categoria_id)
        if self.db.sesion.scalar(
            select(Producto.id).where(
                Producto.categoria_id == categoria_id
            ).limit(1)
        ) is not None:
            raise ReglaNegocioError(
                "No se puede eliminar la categoría porque tiene productos asociados"
            )
        try:
            with self.db.transaccion() as sesion:
                sesion.delete(sesion.get(Categoria, categoria_id))
        except IntegrityError as error:
            raise ReglaNegocioError(
                "No se puede eliminar la categoría porque tiene registros asociados"
            ) from error
        return {"mensaje": f"Categoría {categoria.id} eliminada"}

    def listar_proveedores(self):
        filas = self.db.sesion.scalars(
            select(Proveedor).order_by(Proveedor.razon_social, Proveedor.id)
        )
        return [fila.to_dict() for fila in filas]

    def obtener_proveedor(self, proveedor_id):
        return self._proveedor_modelo(proveedor_id).to_dict()

    def crear_proveedor(self, datos):
        valores = self._validar_proveedor(datos)
        self._validar_cuit(valores["cuit"])
        entidad = Proveedor(**valores)
        try:
            with self.db.transaccion() as sesion:
                sesion.add(entidad)
                sesion.flush()
                proveedor_id = entidad.id
        except IntegrityError as error:
            raise ReglaNegocioError(
                f"Ya existe un proveedor con el CUIT '{valores['cuit']}'"
            ) from error
        return self.obtener_proveedor(proveedor_id)

    def actualizar_proveedor(self, proveedor_id, datos, parcial=False):
        proveedor = self._proveedor_modelo(proveedor_id)
        valores = self._validar_proveedor(
            datos, parcial=parcial, existente=proveedor
        )
        self._validar_cuit(valores["cuit"], excluir_id=proveedor_id)
        try:
            with self.db.transaccion() as sesion:
                entidad = sesion.get(Proveedor, proveedor_id)
                entidad.cuit = valores["cuit"]
                entidad.razon_social = valores["razon_social"]
        except IntegrityError as error:
            raise ReglaNegocioError(
                f"Ya existe un proveedor con el CUIT '{valores['cuit']}'"
            ) from error
        return self.obtener_proveedor(proveedor_id)

    def eliminar_proveedor(self, proveedor_id):
        proveedor = self._proveedor_modelo(proveedor_id)
        if self.db.sesion.scalar(
            select(Producto.id).where(
                Producto.proveedor_id == proveedor_id
            ).limit(1)
        ) is not None:
            raise ReglaNegocioError(
                "No se puede eliminar el proveedor porque tiene productos asociados"
            )
        try:
            with self.db.transaccion() as sesion:
                sesion.delete(sesion.get(Proveedor, proveedor_id))
        except IntegrityError as error:
            raise ReglaNegocioError(
                "No se puede eliminar el proveedor porque tiene registros asociados"
            ) from error
        return {"mensaje": f"Proveedor {proveedor.id} eliminado"}

    def _validar_proveedor(self, datos, parcial=False, existente=None):
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")
        permitidos = {"cuit", "razon_social"}
        desconocidos = set(datos) - permitidos
        if desconocidos:
            raise ReglaNegocioError(f"Campos desconocidos: {', '.join(sorted(desconocidos))}")

        valores = {}
        for campo in permitidos:
            if campo in datos:
                valores[campo] = datos[campo]
            elif parcial and existente is not None:
                valores[campo] = getattr(existente, campo)
            else:
                raise ReglaNegocioError(f"El campo '{campo}' es obligatorio")

        for campo in permitidos:
            valor = valores[campo]
            if not isinstance(valor, str) or not valor.strip():
                raise ReglaNegocioError(f"El campo '{campo}' debe ser un texto no vacío")
            valores[campo] = valor.strip()
        return valores

    @staticmethod
    def _validar_texto(datos, campo, parcial=False, nombre_actual=None):
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")
        desconocidos = set(datos) - {campo}
        if desconocidos:
            raise ReglaNegocioError(f"Campos desconocidos: {', '.join(sorted(desconocidos))}")
        valor = datos.get(campo, nombre_actual if parcial else None)
        if not isinstance(valor, str) or not valor.strip():
            raise ReglaNegocioError(f"El campo '{campo}' debe ser un texto no vacío")
        return {campo: valor.strip()}

    def _validar_nombre_categoria(self, nombre, excluir_id=None):
        consulta = select(Categoria.id).where(Categoria.nombre == nombre)
        if excluir_id is not None:
            consulta = consulta.where(Categoria.id != excluir_id)
        if self.db.sesion.scalar(consulta.limit(1)) is not None:
            raise ReglaNegocioError(f"Ya existe una categoría con el nombre '{nombre}'")

    def _validar_cuit(self, cuit, excluir_id=None):
        consulta = select(Proveedor.id).where(Proveedor.cuit == cuit)
        if excluir_id is not None:
            consulta = consulta.where(Proveedor.id != excluir_id)
        if self.db.sesion.scalar(consulta.limit(1)) is not None:
            raise ReglaNegocioError(f"Ya existe un proveedor con el CUIT '{cuit}'")

    def _categoria_modelo(self, categoria_id):
        entidad = self.db.sesion.get(Categoria, categoria_id)
        if entidad is None:
            raise NoEncontradoError(f"No existe la categoría {categoria_id}")
        return entidad

    def _proveedor_modelo(self, proveedor_id):
        entidad = self.db.sesion.get(Proveedor, proveedor_id)
        if entidad is None:
            raise NoEncontradoError(f"No existe el proveedor {proveedor_id}")
        return entidad
