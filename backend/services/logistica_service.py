"""
Procesos obligatorios 3, 4, 5 y 6:
  3. Orden de reposición CD -> local
  4. Empaquetar en contenedores con remito y precinto
  5. Despachar
  6. Recibir y verificar precinto
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from database.conexion import BaseDeDatos
from models.contenedor import Contenedor, EstadoContenedor
from models.contenedor import DetalleContenedor, HistorialContenedor
from models.orden_reposicion import DetalleOrden, OrdenReposicion, Remito
from models.producto import Producto
from models.sucursal import Sucursal
from models.sucursal import Sucursal
from patrones.observer import Sujeto, Eventos
from services.excepciones import ReglaNegocioError, NoEncontradoError


class LogisticaService(Sujeto):
    def __init__(self):
        super().__init__()
        self.db = BaseDeDatos()

    def crear_orden(self, destino_id, items):
        """items: [{"producto_id": 1, "cantidad": 10}, ...]"""
        destino = self._obtener_sucursal(destino_id)
        if destino.tipo != "LOCAL":
            raise ReglaNegocioError("El destino de una orden de reposición debe ser un local")
        if not items:
            raise ReglaNegocioError("La orden debe tener al menos un producto")
        self._validar_items(items)

        sesion = self.db.sesion
        cd_id = sesion.scalar(select(Sucursal.id).where(Sucursal.tipo == "CD").limit(1))
        if cd_id is None:
            raise ReglaNegocioError("No hay un Centro de Distribución cargado")

        with self.db.transaccion() as sesion:
            orden = OrdenReposicion(origen_id=cd_id, destino_id=destino_id)
            sesion.add(orden)
            sesion.flush()
            orden_id = orden.id
            sesion.add_all([
                DetalleOrden(
                    orden_id=orden_id,
                    producto_id=item["producto_id"],
                    cantidad=item["cantidad"],
                )
                for item in items
            ])
        return self.obtener_orden(orden_id)

    def obtener_orden(self, orden_id):
        sucursal_destino = aliased(Sucursal)
        fila = self.db.sesion.execute(
            select(
                OrdenReposicion,
                Sucursal.nombre.label("origen"),
                sucursal_destino.nombre.label("destino"),
                Remito.id.label("remito_id"),
                Remito.numero.label("remito_numero"),
                Remito.estado.label("remito_estado"),
            )
            .join(Sucursal, Sucursal.id == OrdenReposicion.origen_id)
            .join(sucursal_destino, sucursal_destino.id == OrdenReposicion.destino_id)
            .outerjoin(Remito, Remito.orden_id == OrdenReposicion.id)
            .where(OrdenReposicion.id == orden_id)
        ).first()
        if fila is None:
            raise NoEncontradoError(f"No existe la orden {orden_id}")

        orden = fila[0]
        resultado = {
            nombre: getattr(orden, nombre)
            for nombre in ("id", "origen_id", "destino_id", "fecha", "estado")
        }
        resultado.update({
            "origen": fila.origen,
            "destino": fila.destino,
            "remito_id": fila.remito_id,
            "remito_numero": fila.remito_numero,
            "remito_estado": fila.remito_estado,
        })
        items = self.db.sesion.execute(
            select(
                DetalleOrden.producto_id,
                Producto.nombre,
                DetalleOrden.cantidad,
                func.coalesce(func.sum(DetalleContenedor.cantidad), 0).label("empaquetado"),
            )
            .join(Producto, Producto.id == DetalleOrden.producto_id)
            .outerjoin(Remito, Remito.orden_id == DetalleOrden.orden_id)
            .outerjoin(Contenedor, Contenedor.remito_id == Remito.id)
            .outerjoin(
                DetalleContenedor,
                (DetalleContenedor.contenedor_id == Contenedor.id)
                & (DetalleContenedor.producto_id == DetalleOrden.producto_id),
            )
            .where(DetalleOrden.orden_id == orden_id)
            .group_by(
                DetalleOrden.producto_id,
                Producto.nombre,
                DetalleOrden.cantidad,
            )
        ).mappings()
        resultado["items"] = [dict(item) for item in items]
        resultado["contenedores"] = [contenedor.to_dict() for contenedor in self._contenedores_de_orden(orden_id)]
        return resultado

    def listar_ordenes(self):
        ids = self.db.sesion.scalars(
            select(OrdenReposicion.id).order_by(OrdenReposicion.id.desc())
        )
        return [self.obtener_orden(orden_id) for orden_id in ids]

    def crear_contenedor(self, orden_id, items):
        orden = self.obtener_orden(orden_id)
        if orden["estado"] not in ("PENDIENTE", "EN_PREPARACION"):
            raise ReglaNegocioError("Solo se pueden armar contenedores de órdenes pendientes")
        if orden["remito_estado"] not in (None, "ABIERTO"):
            raise ReglaNegocioError("El remito ya fue despachado: no se le pueden agregar contenedores")
        if not items:
            raise ReglaNegocioError("El contenedor no puede estar vacío")
        self._validar_items(items)

        pendientes = {item["producto_id"]: item["cantidad"] - item["empaquetado"]
                      for item in orden["items"]}
        for item in items:
            producto_id = item["producto_id"]
            if producto_id not in pendientes:
                raise ReglaNegocioError(f"El producto {producto_id} no está en la orden")
            if item["cantidad"] > pendientes[producto_id]:
                raise ReglaNegocioError(
                    f"Producto {producto_id}: quedan {pendientes[producto_id]} "
                    f"por empaquetar y se intentó empaquetar {item['cantidad']}"
                )

        with self.db.transaccion() as sesion:
            remito_id = orden["remito_id"]
            if remito_id is None:
                remito = Remito(numero=f"R-{orden_id:06d}", orden_id=orden_id)
                sesion.add(remito)
                sesion.flush()
                remito_id = remito.id
            contenedor = Contenedor(remito_id=remito_id, items=items)
            sesion.add(contenedor)
            sesion.flush()
            contenedor_id = contenedor.id
            sesion.add_all([
                DetalleContenedor(
                    contenedor_id=contenedor_id,
                    producto_id=item["producto_id"],
                    cantidad=item["cantidad"],
                )
                for item in items
            ])
            self._registrar_historial(contenedor_id, EstadoContenedor.PREPARADO, "Contenedor armado en CD")
            sesion.get(OrdenReposicion, orden_id).estado = "EN_PREPARACION"
        return self.obtener_contenedor(contenedor_id).to_dict()

    def precintar(self, contenedor_id, precinto):
        precinto = (precinto or "").strip()
        if not precinto:
            raise ReglaNegocioError("Debe indicar el número de precinto")
        if self.db.sesion.scalar(
            select(Contenedor.id).where(Contenedor.precinto == precinto)
        ):
            raise ReglaNegocioError(f"El precinto {precinto} ya fue usado en otro contenedor")

        contenedor = self.obtener_contenedor(contenedor_id)
        with self.db.transaccion() as sesion:
            self._transicionar(contenedor, EstadoContenedor.PRECINTADO, f"Precinto {precinto}")
            contenedor.precinto = precinto
        return self.obtener_contenedor(contenedor_id).to_dict()

    def despachar(self, contenedor_id):
        contenedor = self.obtener_contenedor(contenedor_id)
        orden = self._orden_de_remito(contenedor.remito_id)

        with self.db.transaccion() as sesion:
            self._transicionar(contenedor, EstadoContenedor.EN_TRANSITO, "Despachado desde CD")
            contenedor.fecha_despacho = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            sesion.get(Remito, contenedor.remito_id).estado = "DESPACHADO"
            sesion.get(OrdenReposicion, orden["id"]).estado = "DESPACHADA"
            self.notificar(Eventos.CONTENEDOR_DESPACHADO, {
                "contenedor_id": contenedor_id,
                "origen_id": orden["origen_id"],
                "items": contenedor.items,
            })
        return self.obtener_contenedor(contenedor_id).to_dict()

    def recibir(self, contenedor_id, precinto_leido, precinto_intacto):
        """Verifica el sello leído en el local y define si el contenedor se acepta."""
        contenedor = self.obtener_contenedor(contenedor_id)

        with self.db.transaccion() as sesion:
            self._transicionar(contenedor, EstadoContenedor.RECIBIDO, "Recibido en local")
            contenedor.fecha_recepcion = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            coincide = (precinto_leido or "").strip() == contenedor.precinto
            if coincide and precinto_intacto:
                self._transicionar(contenedor, EstadoContenedor.VERIFICADO, "Precinto OK")
            else:
                motivo = "Precinto roto" if not precinto_intacto else \
                         f"Precinto no coincide (leído {precinto_leido})"
                self._transicionar(contenedor, EstadoContenedor.RECHAZADO, motivo)
                self.notificar(Eventos.CONTENEDOR_RECHAZADO, {"contenedor_id": contenedor_id, "motivo": motivo})

            self._cerrar_remito_si_corresponde(contenedor.remito_id)
        return self.obtener_contenedor(contenedor_id).to_dict()

    def _cerrar_remito_si_corresponde(self, remito_id):
        """El stock entra al local solo cuando todos los contenedores tienen estado final."""
        contenedores = self._contenedores_de_remito(remito_id)
        if not all(contenedor.esta_finalizado() for contenedor in contenedores):
            return

        verificados = [contenedor for contenedor in contenedores if contenedor.estado == EstadoContenedor.VERIFICADO]
        estado_remito = "VERIFICADO" if verificados else "RECHAZADO"
        self.db.sesion.get(Remito, remito_id).estado = estado_remito
        orden = self._orden_de_remito(remito_id)
        self.db.sesion.get(OrdenReposicion, orden["id"]).estado = "CERRADA"

        if verificados:
            self.notificar(Eventos.REMITO_VERIFICADO, {
                "remito_numero": orden["remito_numero"],
                "destino_id": orden["destino_id"],
                "items_verificados": [
                    item for contenedor in verificados for item in contenedor.items
                ],
            })

    def obtener_contenedor(self, contenedor_id):
        contenedor = self.db.sesion.get(Contenedor, contenedor_id)
        if contenedor is None:
            raise NoEncontradoError(f"No existe el contenedor {contenedor_id}")
        items = self.db.sesion.execute(
            select(DetalleContenedor.producto_id, DetalleContenedor.cantidad)
            .where(DetalleContenedor.contenedor_id == contenedor_id)
        ).mappings()
        contenedor.items = [dict(item) for item in items]
        return contenedor

    def historial(self, contenedor_id):
        self.obtener_contenedor(contenedor_id)
        filas = self.db.sesion.execute(
            select(
                HistorialContenedor.estado,
                HistorialContenedor.fecha,
                HistorialContenedor.observacion,
            )
            .where(HistorialContenedor.contenedor_id == contenedor_id)
            .order_by(HistorialContenedor.id)
        ).mappings()
        return [dict(fila) for fila in filas]

    def _transicionar(self, contenedor: Contenedor, nuevo_estado, observacion):
        try:
            contenedor.cambiar_estado(nuevo_estado)
        except ValueError as error:
            raise ReglaNegocioError(str(error)) from error

        self._registrar_historial(contenedor.id, nuevo_estado, observacion)

    def _registrar_historial(self, contenedor_id, estado, observacion):
        self.db.sesion.add(
            HistorialContenedor(
                contenedor_id=contenedor_id,
                estado=estado,
                fecha=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                observacion=observacion,
            )
        )

    def _contenedores_de_remito(self, remito_id):
        contenedor_ids = self.db.sesion.scalars(
            select(Contenedor.id).where(Contenedor.remito_id == remito_id).order_by(Contenedor.id)
        )
        return [self.obtener_contenedor(contenedor_id) for contenedor_id in contenedor_ids]

    def _contenedores_de_orden(self, orden_id):
        remito_id = self.db.sesion.scalar(
            select(Remito.id).where(Remito.orden_id == orden_id)
        )
        return self._contenedores_de_remito(remito_id) if remito_id else []

    def _orden_de_remito(self, remito_id):
        fila = self.db.sesion.execute(
            select(
                OrdenReposicion,
                Remito.numero.label("remito_numero"),
            )
            .join(Remito, Remito.orden_id == OrdenReposicion.id)
            .where(Remito.id == remito_id)
        ).first()
        orden = fila[0]
        resultado = {
            nombre: getattr(orden, nombre)
            for nombre in ("id", "origen_id", "destino_id", "fecha", "estado")
        }
        resultado["remito_numero"] = fila.remito_numero
        return resultado

    def _obtener_sucursal(self, sucursal_id):
        sucursal = self.db.sesion.get(Sucursal, sucursal_id)
        if sucursal is None:
            raise NoEncontradoError(f"No existe la sucursal {sucursal_id}")
        return sucursal

    def _validar_items(self, items):
        vistos = set()
        for item in items:
            if item.get("cantidad", 0) <= 0:
                raise ReglaNegocioError("Las cantidades deben ser mayores a cero")
            producto_id = item["producto_id"]
            if producto_id in vistos:
                raise ReglaNegocioError(f"Producto {producto_id} repetido")
            vistos.add(producto_id)
            if self.db.sesion.get(Producto, producto_id) is None:
                raise NoEncontradoError(f"No existe el producto {producto_id}")
