"""
La consigna pide AL MENOS 4 reportes no triviales.
Hay 2 hechos (ambos de logística). Te quedan los de ventas/stock (ver README, paso 6).
"""
from database.conexion import BaseDeDatos
from models.contenedor import Contenedor, DetalleContenedor, HistorialContenedor
from models.orden_reposicion import OrdenReposicion, Remito
from models.producto import Producto
from models.sucursal import Sucursal
from sqlalchemy import func, select


class ReportesService:
    def __init__(self):
        self.db = BaseDeDatos()

    # ✅ HECHO: contenedores rechazados y merma valorizada por rotura de precinto
    def contenedores_rechazados(self, desde=None, hasta=None):
        motivo = (
            select(HistorialContenedor.observacion)
            .where(
                HistorialContenedor.contenedor_id == Contenedor.id,
                HistorialContenedor.estado == "RECHAZADO",
            )
            .order_by(HistorialContenedor.id)
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
                Remito.numero.label("remito"),
                Sucursal.nombre.label("destino"),
                Contenedor.fecha_recepcion,
                motivo.label("motivo"),
                func.sum(DetalleContenedor.cantidad).label("unidades"),
                func.round(
                    func.sum(DetalleContenedor.cantidad * Producto.precio_costo), 2
                ).label("merma_valorizada"),
            )
            .join(Remito, Remito.id == Contenedor.remito_id)
            .join(OrdenReposicion, OrdenReposicion.id == Remito.orden_id)
            .join(Sucursal, Sucursal.id == OrdenReposicion.destino_id)
            .join(DetalleContenedor, DetalleContenedor.contenedor_id == Contenedor.id)
            .join(Producto, Producto.id == DetalleContenedor.producto_id)
            .where(*filtros)
            .group_by(Contenedor.id)
            .order_by(Contenedor.fecha_recepcion.desc())
        ).mappings()
        return [dict(fila) for fila in filas]

    # ✅ HECHO: tiempo promedio de tránsito CD -> cada local (en horas)
    def tiempo_promedio_transito(self):
        filas = self.db.sesion.execute(
            select(
                Sucursal.nombre.label("local"),
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
            .join(OrdenReposicion, OrdenReposicion.destino_id == Sucursal.id)
            .join(Remito, Remito.orden_id == OrdenReposicion.id)
            .join(Contenedor, Contenedor.remito_id == Remito.id)
            .where(
                Contenedor.fecha_despacho.is_not(None),
                Contenedor.fecha_recepcion.is_not(None),
            )
            .group_by(Sucursal.id)
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
