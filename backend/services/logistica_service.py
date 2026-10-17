"""
Procesos obligatorios 3, 4, 5 y 6:
  3. Orden de reposición CD -> local
  4. Empaquetar en bultos con remito y precinto
  5. Despachar
  6. Recibir y verificar precinto
"""
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import aliased

from database.conexion import BaseDeDatos
from models.bulto import Bulto, EstadoBulto
from models.orm import (
    BultoORM,
    DetalleBultoORM,
    DetalleOrdenORM,
    HistorialBultoORM,
    OrdenReposicionORM,
    ProductoORM,
    RemitoORM,
    SucursalORM,
)
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
        cd_id = sesion.scalar(select(SucursalORM.id).where(SucursalORM.tipo == "CD").limit(1))
        if cd_id is None:
            raise ReglaNegocioError("No hay un Centro de Distribución cargado")

        with self.db.transaccion() as sesion:
            orden = OrdenReposicionORM(origen_id=cd_id, destino_id=destino_id)
            sesion.add(orden)
            sesion.flush()
            orden_id = orden.id
            sesion.add_all([
                DetalleOrdenORM(
                    orden_id=orden_id,
                    producto_id=item["producto_id"],
                    cantidad=item["cantidad"],
                )
                for item in items
            ])
        return self.obtener_orden(orden_id)

    def obtener_orden(self, orden_id):
        sucursal_destino = aliased(SucursalORM)
        fila = self.db.sesion.execute(
            select(
                OrdenReposicionORM,
                SucursalORM.nombre.label("origen"),
                sucursal_destino.nombre.label("destino"),
                RemitoORM.id.label("remito_id"),
                RemitoORM.numero.label("remito_numero"),
                RemitoORM.estado.label("remito_estado"),
            )
            .join(SucursalORM, SucursalORM.id == OrdenReposicionORM.origen_id)
            .join(sucursal_destino, sucursal_destino.id == OrdenReposicionORM.destino_id)
            .outerjoin(RemitoORM, RemitoORM.orden_id == OrdenReposicionORM.id)
            .where(OrdenReposicionORM.id == orden_id)
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
                DetalleOrdenORM.producto_id,
                ProductoORM.nombre,
                DetalleOrdenORM.cantidad,
                func.coalesce(func.sum(DetalleBultoORM.cantidad), 0).label("empaquetado"),
            )
            .join(ProductoORM, ProductoORM.id == DetalleOrdenORM.producto_id)
            .outerjoin(RemitoORM, RemitoORM.orden_id == DetalleOrdenORM.orden_id)
            .outerjoin(BultoORM, BultoORM.remito_id == RemitoORM.id)
            .outerjoin(
                DetalleBultoORM,
                (DetalleBultoORM.bulto_id == BultoORM.id)
                & (DetalleBultoORM.producto_id == DetalleOrdenORM.producto_id),
            )
            .where(DetalleOrdenORM.orden_id == orden_id)
            .group_by(
                DetalleOrdenORM.producto_id,
                ProductoORM.nombre,
                DetalleOrdenORM.cantidad,
            )
        ).mappings()
        resultado["items"] = [dict(item) for item in items]
        resultado["bultos"] = [bulto.to_dict() for bulto in self._bultos_de_orden(orden_id)]
        return resultado

    def listar_ordenes(self):
        ids = self.db.sesion.scalars(
            select(OrdenReposicionORM.id).order_by(OrdenReposicionORM.id.desc())
        )
        return [self.obtener_orden(orden_id) for orden_id in ids]

    def crear_bulto(self, orden_id, items):
        orden = self.obtener_orden(orden_id)
        if orden["estado"] not in ("PENDIENTE", "EN_PREPARACION"):
            raise ReglaNegocioError("Solo se pueden armar bultos de órdenes pendientes")
        if orden["remito_estado"] not in (None, "ABIERTO"):
            raise ReglaNegocioError("El remito ya fue despachado: no se le pueden agregar bultos")
        if not items:
            raise ReglaNegocioError("El bulto no puede estar vacío")
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
                remito = RemitoORM(numero=f"R-{orden_id:06d}", orden_id=orden_id)
                sesion.add(remito)
                sesion.flush()
                remito_id = remito.id
            bulto = BultoORM(remito_id=remito_id)
            sesion.add(bulto)
            sesion.flush()
            bulto_id = bulto.id
            sesion.add_all([
                DetalleBultoORM(
                    bulto_id=bulto_id,
                    producto_id=item["producto_id"],
                    cantidad=item["cantidad"],
                )
                for item in items
            ])
            self._registrar_historial(bulto_id, EstadoBulto.PREPARADO, "Bulto armado en CD")
            sesion.get(OrdenReposicionORM, orden_id).estado = "EN_PREPARACION"
        return self.obtener_bulto(bulto_id).to_dict()

    def precintar(self, bulto_id, precinto):
        precinto = (precinto or "").strip()
        if not precinto:
            raise ReglaNegocioError("Debe indicar el número de precinto")
        if self.db.sesion.scalar(
            select(BultoORM.id).where(BultoORM.precinto == precinto)
        ):
            raise ReglaNegocioError(f"El precinto {precinto} ya fue usado en otro bulto")

        bulto = self.obtener_bulto(bulto_id)
        with self.db.transaccion() as sesion:
            self._transicionar(bulto, EstadoBulto.PRECINTADO, f"Precinto {precinto}")
            sesion.get(BultoORM, bulto_id).precinto = precinto
        return self.obtener_bulto(bulto_id).to_dict()

    def despachar(self, bulto_id):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)

        with self.db.transaccion() as sesion:
            self._transicionar(bulto, EstadoBulto.EN_TRANSITO, "Despachado desde CD")
            sesion.get(BultoORM, bulto_id).fecha_despacho = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            sesion.get(RemitoORM, bulto.remito_id).estado = "DESPACHADO"
            sesion.get(OrdenReposicionORM, orden["id"]).estado = "DESPACHADA"
            self.notificar(Eventos.BULTO_DESPACHADO, {
                "bulto_id": bulto_id,
                "origen_id": orden["origen_id"],
                "items": bulto.items,
            })
        return self.obtener_bulto(bulto_id).to_dict()

    def recibir(self, bulto_id, precinto_leido, precinto_intacto):
        """Verifica el sello leído en el local y define si el bulto se acepta."""
        bulto = self.obtener_bulto(bulto_id)

        with self.db.transaccion() as sesion:
            self._transicionar(bulto, EstadoBulto.RECIBIDO, "Recibido en local")
            sesion.get(BultoORM, bulto_id).fecha_recepcion = datetime.now().strftime(
                "%Y-%m-%d %H:%M:%S"
            )

            coincide = (precinto_leido or "").strip() == bulto.precinto
            if coincide and precinto_intacto:
                self._transicionar(bulto, EstadoBulto.VERIFICADO, "Precinto OK")
            else:
                motivo = "Precinto roto" if not precinto_intacto else \
                         f"Precinto no coincide (leído {precinto_leido})"
                self._transicionar(bulto, EstadoBulto.RECHAZADO, motivo)
                self.notificar(Eventos.BULTO_RECHAZADO, {"bulto_id": bulto_id, "motivo": motivo})

            self._cerrar_remito_si_corresponde(bulto.remito_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def _cerrar_remito_si_corresponde(self, remito_id):
        """El stock entra al local solo cuando todos los bultos tienen estado final."""
        bultos = self._bultos_de_remito(remito_id)
        if not all(bulto.esta_finalizado() for bulto in bultos):
            return

        verificados = [bulto for bulto in bultos if bulto.estado == EstadoBulto.VERIFICADO]
        estado_remito = "VERIFICADO" if verificados else "RECHAZADO"
        self.db.sesion.get(RemitoORM, remito_id).estado = estado_remito
        orden = self._orden_de_remito(remito_id)
        self.db.sesion.get(OrdenReposicionORM, orden["id"]).estado = "CERRADA"

        if verificados:
            self.notificar(Eventos.REMITO_VERIFICADO, {
                "remito_numero": orden["remito_numero"],
                "destino_id": orden["destino_id"],
                "items_verificados": [
                    item for bulto in verificados for item in bulto.items
                ],
            })

    def obtener_bulto(self, bulto_id):
        fila = self.db.sesion.get(BultoORM, bulto_id)
        if fila is None:
            raise NoEncontradoError(f"No existe el bulto {bulto_id}")
        items = self.db.sesion.execute(
            select(DetalleBultoORM.producto_id, DetalleBultoORM.cantidad)
            .where(DetalleBultoORM.bulto_id == bulto_id)
        ).mappings()
        return Bulto.desde_fila(
            {
                "id": fila.id,
                "remito_id": fila.remito_id,
                "estado": fila.estado,
                "precinto": fila.precinto,
                "fecha_despacho": fila.fecha_despacho,
                "fecha_recepcion": fila.fecha_recepcion,
            },
            [dict(item) for item in items],
        )

    def historial(self, bulto_id):
        self.obtener_bulto(bulto_id)
        filas = self.db.sesion.execute(
            select(
                HistorialBultoORM.estado,
                HistorialBultoORM.fecha,
                HistorialBultoORM.observacion,
            )
            .where(HistorialBultoORM.bulto_id == bulto_id)
            .order_by(HistorialBultoORM.id)
        ).mappings()
        return [dict(fila) for fila in filas]

    def _transicionar(self, bulto: Bulto, nuevo_estado, observacion):
        try:
            bulto.cambiar_estado(nuevo_estado)
        except ValueError as error:
            raise ReglaNegocioError(str(error)) from error

        self.db.sesion.get(BultoORM, bulto.id).estado = nuevo_estado
        self._registrar_historial(bulto.id, nuevo_estado, observacion)

    def _registrar_historial(self, bulto_id, estado, observacion):
        self.db.sesion.add(
            HistorialBultoORM(
                bulto_id=bulto_id,
                estado=estado,
                observacion=observacion,
            )
        )

    def _bultos_de_remito(self, remito_id):
        bulto_ids = self.db.sesion.scalars(
            select(BultoORM.id).where(BultoORM.remito_id == remito_id).order_by(BultoORM.id)
        )
        return [self.obtener_bulto(bulto_id) for bulto_id in bulto_ids]

    def _bultos_de_orden(self, orden_id):
        remito_id = self.db.sesion.scalar(
            select(RemitoORM.id).where(RemitoORM.orden_id == orden_id)
        )
        return self._bultos_de_remito(remito_id) if remito_id else []

    def _orden_de_remito(self, remito_id):
        fila = self.db.sesion.execute(
            select(
                OrdenReposicionORM,
                RemitoORM.numero.label("remito_numero"),
            )
            .join(RemitoORM, RemitoORM.orden_id == OrdenReposicionORM.id)
            .where(RemitoORM.id == remito_id)
        ).first()
        orden = fila[0]
        resultado = {
            nombre: getattr(orden, nombre)
            for nombre in ("id", "origen_id", "destino_id", "fecha", "estado")
        }
        resultado["remito_numero"] = fila.remito_numero
        return resultado

    def _obtener_sucursal(self, sucursal_id):
        fila = self.db.sesion.get(SucursalORM, sucursal_id)
        if fila is None:
            raise NoEncontradoError(f"No existe la sucursal {sucursal_id}")
        return Sucursal.desde_fila({
            "id": fila.id,
            "nombre": fila.nombre,
            "direccion": fila.direccion,
            "tipo": fila.tipo,
        })

    def _validar_items(self, items):
        vistos = set()
        for item in items:
            if item.get("cantidad", 0) <= 0:
                raise ReglaNegocioError("Las cantidades deben ser mayores a cero")
            producto_id = item["producto_id"]
            if producto_id in vistos:
                raise ReglaNegocioError(f"Producto {producto_id} repetido")
            vistos.add(producto_id)
            if self.db.sesion.get(ProductoORM, producto_id) is None:
                raise NoEncontradoError(f"No existe el producto {producto_id}")
