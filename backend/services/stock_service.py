from database.conexion import BaseDeDatos
from patrones.observer import Observador, Eventos
from services.excepciones import ReglaNegocioError


class StockService:
    """Operaciones sobre el stock DISPONIBLE (el único que se puede vender)."""

    def __init__(self):
        self.db = BaseDeDatos()          # Singleton: siempre la misma conexión

    def disponible(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            "SELECT disponible FROM stock WHERE sucursal_id=? AND producto_id=?",
            (sucursal_id, producto_id))
        return fila["disponible"] if fila else 0

    def sumar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        self.db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)
               ON CONFLICT(sucursal_id, producto_id)
               DO UPDATE SET disponible = disponible + excluded.disponible""",
            (sucursal_id, producto_id, cantidad))
        self._registrar_movimiento(sucursal_id, producto_id, cantidad, motivo, referencia)

    def restar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        """Valida que alcance ANTES de descontar. Lo vas a reusar en ventas."""
        actual = self.disponible(sucursal_id, producto_id)
        if cantidad > actual:
            raise ReglaNegocioError(
                f"Stock insuficiente del producto {producto_id}: "
                f"hay {actual}, se pidieron {cantidad}")
        self.db.ejecutar(
            "UPDATE stock SET disponible = disponible - ? WHERE sucursal_id=? AND producto_id=?",
            (cantidad, sucursal_id, producto_id))
        self._registrar_movimiento(sucursal_id, producto_id, -cantidad, motivo, referencia)

    def _registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo, referencia):
        self.db.ejecutar(
            """INSERT INTO movimiento_stock (sucursal_id, producto_id, cantidad, motivo, referencia)
               VALUES (?, ?, ?, ?, ?)""",
            (sucursal_id, producto_id, cantidad, motivo, referencia))

    def listar(self, sucursal_id):
        return self.db.consultar(
            """SELECT p.id AS producto_id, p.codigo, p.nombre, p.stock_minimo,
                      COALESCE(s.disponible, 0) AS disponible
               FROM producto p
               LEFT JOIN stock s ON s.producto_id = p.id AND s.sucursal_id = ?
               ORDER BY p.nombre""", (sucursal_id,))


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
