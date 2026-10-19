from database.conexion import BaseDeDatos
from models.observer import Observador, Sujeto, Eventos
from services.excepciones import ReglaNegocioError


class StockService(Sujeto):            # también es SUJETO: avisa cada cambio de stock
    """Operaciones sobre el stock de cada sucursal."""

    def __init__(self):
        super().__init__()
        self.db = BaseDeDatos()          # Singleton: siempre la misma conexión

    def _avisar_cambio(self, sucursal_id, producto_id):
        self.notificar(Eventos.STOCK_MODIFICADO, {
            "sucursal_id": sucursal_id, "producto_id": producto_id,
            "libre": self.libre(sucursal_id, producto_id)})

    def disponible(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            "SELECT disponible FROM stock WHERE sucursal_id=? AND producto_id=?",
            (sucursal_id, producto_id))
        return fila["disponible"] if fila else 0

    def reservado(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            "SELECT reservado FROM stock WHERE sucursal_id=? AND producto_id=?",
            (sucursal_id, producto_id))
        return fila["reservado"] if fila else 0

    def libre(self, sucursal_id, producto_id):
        """Lo que todavía nadie tomó: disponible - reservado."""
        return self.disponible(sucursal_id, producto_id) - self.reservado(sucursal_id, producto_id)

    # ---------- reservas (se usan al armar bultos en el CD) ----------
    def reservar(self, sucursal_id, producto_id, cantidad, referencia=None):
        """Compromete unidades para un bulto. Llamar con el producto BLOQUEADO
        (GestorBloqueos) y dentro de una transacción.

        El WHERE hace el control y la reserva en una sola sentencia atómica:
        si otro usuario se adelantó, no se cumple la condición y rowcount = 0."""
        filas = self.db.ejecutar_contando(
            """UPDATE stock SET reservado = reservado + ?
               WHERE sucursal_id=? AND producto_id=? AND disponible - reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))
        if filas == 0:
            raise ReglaNegocioError(
                f"Stock insuficiente del producto {producto_id}: hay "
                f"{self.libre(sucursal_id, producto_id)} libres y se pidieron {cantidad} "
                "(puede que otro usuario lo haya tomado recién)")
        self._avisar_cambio(sucursal_id, producto_id)

    def consumir_reserva(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        """Al despachar: la mercadería reservada sale físicamente del CD."""
        filas = self.db.ejecutar_contando(
            """UPDATE stock SET disponible = disponible - ?, reservado = reservado - ?
               WHERE sucursal_id=? AND producto_id=? AND reservado >= ?""",
            (cantidad, cantidad, sucursal_id, producto_id, cantidad))
        if filas == 0:
            raise ReglaNegocioError(
                f"No hay una reserva de {cantidad} unidades del producto {producto_id}")
        self._registrar_movimiento(sucursal_id, producto_id, -cantidad, motivo, referencia)
        self._avisar_cambio(sucursal_id, producto_id)

    def liberar_reserva(self, sucursal_id, producto_id, cantidad):
        """Al anular un bulto: las unidades vuelven a estar libres en el CD."""
        filas = self.db.ejecutar_contando(
            """UPDATE stock SET reservado = reservado - ?
               WHERE sucursal_id=? AND producto_id=? AND reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))
        if filas == 0:
            raise ReglaNegocioError(
                f"No hay una reserva de {cantidad} unidades del producto {producto_id}")
        self._avisar_cambio(sucursal_id, producto_id)

    def sumar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        self.db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)
               ON CONFLICT(sucursal_id, producto_id)
               DO UPDATE SET disponible = disponible + excluded.disponible""",
            (sucursal_id, producto_id, cantidad))
        self._registrar_movimiento(sucursal_id, producto_id, cantidad, motivo, referencia)
        self._avisar_cambio(sucursal_id, producto_id)

    def restar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None):
        """Descuenta stock LIBRE en una sola sentencia atómica. Lo van a reusar en ventas:
        igual que en crear_bulto, bloquear los productos con GestorBloqueos antes de
        abrir la transacción."""
        filas = self.db.ejecutar_contando(
            """UPDATE stock SET disponible = disponible - ?
               WHERE sucursal_id=? AND producto_id=? AND disponible - reservado >= ?""",
            (cantidad, sucursal_id, producto_id, cantidad))
        if filas == 0:
            raise ReglaNegocioError(
                f"Stock insuficiente del producto {producto_id}: "
                f"hay {self.libre(sucursal_id, producto_id)} libres, se pidieron {cantidad}")
        self._registrar_movimiento(sucursal_id, producto_id, -cantidad, motivo, referencia)
        self._avisar_cambio(sucursal_id, producto_id)

    def _registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo, referencia):
        self.db.ejecutar(
            """INSERT INTO movimiento_stock (sucursal_id, producto_id, cantidad, motivo, referencia)
               VALUES (?, ?, ?, ?, ?)""",
            (sucursal_id, producto_id, cantidad, motivo, referencia))

    def listar(self, sucursal_id):
        return self.db.consultar(
            """SELECT p.id AS producto_id, p.codigo, p.nombre, p.stock_minimo,
                      COALESCE(s.disponible, 0) AS disponible,
                      COALESCE(s.reservado, 0) AS reservado,
                      COALESCE(s.disponible, 0) - COALESCE(s.reservado, 0) AS libre
               FROM producto p
               LEFT JOIN stock s ON s.producto_id = p.id AND s.sucursal_id = ?
               ORDER BY p.nombre""", (sucursal_id,))


class StockObserver(Observador):
    """Reacciona a los eventos de logística moviendo el stock."""

    def __init__(self, stock_service: StockService):
        self.stock = stock_service

    def actualizar(self, evento, datos):
        if evento == Eventos.BULTO_DESPACHADO:
            # Sale del CD la mercadería que se había reservado al armar el bulto
            for item in datos["items"]:
                self.stock.consumir_reserva(datos["origen_id"], item["producto_id"],
                                            item["cantidad"], "DESPACHO",
                                            f"bulto {datos['bulto_id']}")

        elif evento == Eventos.REMITO_VERIFICADO:
            # Recién ahora entra como DISPONIBLE en el local, y solo lo de bultos verificados
            for item in datos["items_verificados"]:
                self.stock.sumar(datos["destino_id"], item["producto_id"], item["cantidad"],
                                 "RECEPCION", f"remito {datos['remito_numero']}")


# Los otros dos observadores están en services/observadores.py
