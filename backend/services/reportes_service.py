"""
La consigna pide AL MENOS 4 reportes no triviales.
Hay 2 hechos (ambos de logística). Te quedan los de ventas/stock (ver README, paso 6).
"""
from database.conexion import BaseDeDatos
from models.contenedor import Contenedor
from models.orm import (
    DetalleContenedorORM,
    HistorialContenedorORM,
    OrdenReposicionORM,
    ProductoORM,
    RemitoORM,
    SucursalORM,
)
from sqlalchemy import func, select


class ReportesService:
    def __init__(self):
        self.db = BaseDeDatos()

    # ✅ HECHO: contenedores rechazados y merma valorizada por rotura de precinto
    def contenedores_rechazados(self, desde=None, hasta=None):
        motivo = (
            select(HistorialContenedorORM.observacion)
            .where(
                HistorialContenedorORM.contenedor_id == Contenedor.id,
                HistorialContenedorORM.estado == "RECHAZADO",
            )
            .order_by(HistorialContenedorORM.id)
            .limit(1)
            .scalar_subquery()
        )
        filtros = [Contenedor.estado == "RECHAZADO"]
        if desde:
            filtros.append(func.date(Contenedor.fecha_recepcion) >= func.date(desde))
        if hasta:
            filtros.append(func.date(Contenedor.fecha_recepcion) <= func.date(hasta))

        filas = self.db.sesion.execute(
            select(
                Contenedor.id.label("contenedor_id"),
                Contenedor.precinto,
                RemitoORM.numero.label("remito"),
                SucursalORM.nombre.label("destino"),
                Contenedor.fecha_recepcion,
                motivo.label("motivo"),
                func.sum(DetalleContenedorORM.cantidad).label("unidades"),
                func.round(
                    func.sum(DetalleContenedorORM.cantidad * ProductoORM.precio_costo), 2
                ).label("merma_valorizada"),
            )
            .join(RemitoORM, RemitoORM.id == Contenedor.remito_id)
            .join(OrdenReposicionORM, OrdenReposicionORM.id == RemitoORM.orden_id)
            .join(SucursalORM, SucursalORM.id == OrdenReposicionORM.destino_id)
            .join(DetalleContenedorORM, DetalleContenedorORM.contenedor_id == Contenedor.id)
            .join(ProductoORM, ProductoORM.id == DetalleContenedorORM.producto_id)
            .where(*filtros)
            .group_by(Contenedor.id)
            .order_by(Contenedor.fecha_recepcion.desc())
        ).mappings()
        return [dict(fila) for fila in filas]

    # ✅ HECHO: tiempo promedio de tránsito CD -> cada local (en horas)
    def tiempo_promedio_transito(self):
        filas = self.db.sesion.execute(
            select(
                SucursalORM.nombre.label("local"),
                func.count().label("contenedores"),
                func.round(
                    func.avg(
                        (
                            func.julianday(Contenedor.fecha_recepcion)
                            - func.julianday(Contenedor.fecha_despacho)
                        )
                        * 24
                    ),
                    2,
                ).label("horas_promedio"),
            )
            .join(OrdenReposicionORM, OrdenReposicionORM.destino_id == SucursalORM.id)
            .join(RemitoORM, RemitoORM.orden_id == OrdenReposicionORM.id)
            .join(Contenedor, Contenedor.remito_id == RemitoORM.id)
            .where(
                Contenedor.fecha_despacho.is_not(None),
                Contenedor.fecha_recepcion.is_not(None),
            )
            .group_by(SucursalORM.id)
            .order_by(func.round(
                func.avg(
                    (
                        func.julianday(Contenedor.fecha_recepcion)
                        - func.julianday(Contenedor.fecha_despacho)
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
