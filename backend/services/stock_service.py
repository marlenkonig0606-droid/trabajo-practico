from database.conexion import BaseDeDatos
from models.orm import MovimientoStockORM, ProductoORM, StockORM
from patrones.observer import Observador, Eventos
from services.excepciones import ReglaNegocioError
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert


class StockService:
    """Operaciones sobre el stock DISPONIBLE (el único que se puede vender)."""

    def __init__(self):
        self.db = BaseDeDatos()

    def disponible(self, sucursal_id, producto_id):
        stock = self.db.sesion.get(StockORM, (sucursal_id, producto_id))
        return stock.disponible if stock else 0

    def sumar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        insertar = sqlite_insert(StockORM).values(
            sucursal_id=sucursal_id, producto_id=producto_id, disponible=cantidad
        )
        self.db.sesion.execute(
            insertar.on_conflict_do_update(
                index_elements=[StockORM.sucursal_id, StockORM.producto_id],
                set_={"disponible": StockORM.disponible + insertar.excluded.disponible},
            )
        )
        self._registrar_movimiento(sucursal_id, producto_id, cantidad, motivo, referencia)

    def restar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        """Valida que alcance ANTES de descontar. Lo vas a reusar en ventas."""
        stock = self.db.sesion.get(StockORM, (sucursal_id, producto_id))
        actual = stock.disponible if stock else 0
        if cantidad > actual:
            raise ReglaNegocioError(
                f"Stock insuficiente del producto {producto_id}: "
                f"hay {actual}, se pidieron {cantidad}")
        stock.disponible -= cantidad
        self._registrar_movimiento(sucursal_id, producto_id, -cantidad, motivo, referencia)

    def _registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo, referencia):
        self.db.sesion.add(
            MovimientoStockORM(
                sucursal_id=sucursal_id,
                producto_id=producto_id,
                cantidad=cantidad,
                motivo=motivo,
                referencia=referencia,
            )
        )

    def listar(self, sucursal_id):
        filas = self.db.sesion.execute(
            select(
                ProductoORM.id.label("producto_id"),
                ProductoORM.codigo,
                ProductoORM.nombre,
                ProductoORM.stock_minimo,
                func.coalesce(StockORM.disponible, 0).label("disponible"),
            )
            .outerjoin(
                StockORM,
                (StockORM.producto_id == ProductoORM.id)
                & (StockORM.sucursal_id == sucursal_id),
            )
            .order_by(ProductoORM.nombre)
        ).mappings()
        return [dict(fila) for fila in filas]


class StockObserver(Observador):
    """Reacciona a los eventos de logística moviendo el stock."""

    def __init__(self, stock_service: StockService):
        self.stock = stock_service

    def actualizar(self, evento, datos):
        if evento == Eventos.BULTO_DESPACHADO:
            # Sale mercadería del CD
            for item in datos["items"]:
                self.stock.restar(datos["origen_id"], item["producto_id"], item["cantidad"],
                                  "DESPACHO", f"bulto {datos['bulto_id']}")

        elif evento == Eventos.REMITO_VERIFICADO:
            # Recién ahora entra como DISPONIBLE en el local, y solo lo de bultos verificados
            for item in datos["items_verificados"]:
                self.stock.sumar(datos["destino_id"], item["producto_id"], item["cantidad"],
                                 "RECEPCION", f"remito {datos['remito_numero']}")


# TODO (vos): class AlertaStockMinimoObserver(Observador)
#   Cuando se descuenta stock (por despacho o por venta), si queda por debajo
#   de producto.stock_minimo, registrar una alerta (tabla nueva o lista en memoria).
#   Pista: ¿qué evento tendrías que agregar en Eventos? ¿Quién lo notificaría?
