"""
La consigna pide AL MENOS 4 reportes no triviales.
Hay 2 hechos (ambos de logística). Te quedan los de ventas/stock (ver README, paso 6).
"""
from database.conexion import BaseDeDatos
from models.orm import (
    BultoORM,
    DetalleBultoORM,
    HistorialBultoORM,
    OrdenReposicionORM,
    ProductoORM,
    RemitoORM,
    SucursalORM,
)
from sqlalchemy import func, select


class ReportesService:
    def __init__(self):
        self.db = BaseDeDatos()

    # ✅ HECHO: bultos rechazados y merma valorizada por rotura de precinto
    def bultos_rechazados(self, desde=None, hasta=None):
        motivo = (
            select(HistorialBultoORM.observacion)
            .where(
                HistorialBultoORM.bulto_id == BultoORM.id,
                HistorialBultoORM.estado == "RECHAZADO",
            )
            .order_by(HistorialBultoORM.id)
            .limit(1)
            .scalar_subquery()
        )
        filtros = [BultoORM.estado == "RECHAZADO"]
        if desde:
            filtros.append(func.date(BultoORM.fecha_recepcion) >= func.date(desde))
        if hasta:
            filtros.append(func.date(BultoORM.fecha_recepcion) <= func.date(hasta))

        filas = self.db.sesion.execute(
            select(
                BultoORM.id.label("bulto_id"),
                BultoORM.precinto,
                RemitoORM.numero.label("remito"),
                SucursalORM.nombre.label("destino"),
                BultoORM.fecha_recepcion,
                motivo.label("motivo"),
                func.sum(DetalleBultoORM.cantidad).label("unidades"),
                func.round(
                    func.sum(DetalleBultoORM.cantidad * ProductoORM.precio_costo), 2
                ).label("merma_valorizada"),
            )
            .join(RemitoORM, RemitoORM.id == BultoORM.remito_id)
            .join(OrdenReposicionORM, OrdenReposicionORM.id == RemitoORM.orden_id)
            .join(SucursalORM, SucursalORM.id == OrdenReposicionORM.destino_id)
            .join(DetalleBultoORM, DetalleBultoORM.bulto_id == BultoORM.id)
            .join(ProductoORM, ProductoORM.id == DetalleBultoORM.producto_id)
            .where(*filtros)
            .group_by(BultoORM.id)
            .order_by(BultoORM.fecha_recepcion.desc())
        ).mappings()
        return [dict(fila) for fila in filas]

    # ✅ HECHO: tiempo promedio de tránsito CD -> cada local (en horas)
    def tiempo_promedio_transito(self):
        filas = self.db.sesion.execute(
            select(
                SucursalORM.nombre.label("local"),
                func.count().label("bultos"),
                func.round(
                    func.avg(
                        (
                            func.julianday(BultoORM.fecha_recepcion)
                            - func.julianday(BultoORM.fecha_despacho)
                        )
                        * 24
                    ),
                    2,
                ).label("horas_promedio"),
            )
            .join(OrdenReposicionORM, OrdenReposicionORM.destino_id == SucursalORM.id)
            .join(RemitoORM, RemitoORM.orden_id == OrdenReposicionORM.id)
            .join(BultoORM, BultoORM.remito_id == RemitoORM.id)
            .where(
                BultoORM.fecha_despacho.is_not(None),
                BultoORM.fecha_recepcion.is_not(None),
            )
            .group_by(SucursalORM.id)
            .order_by(func.round(
                func.avg(
                    (
                        func.julianday(BultoORM.fecha_recepcion)
                        - func.julianday(BultoORM.fecha_despacho)
                    )
                    * 24
                ),
                2,
            ).desc())
        ).mappings()
        return [dict(fila) for fila in filas]

    # TODO: ventas e ingresos por período, local y medio de pago
    # TODO: productos más vendidos + margen estimado (precio_venta - precio_costo)
    # TODO: existencias actuales y productos en stock mínimo
    #       Pista: StockService.listar() ya te trae disponible y stock_minimo por local.
