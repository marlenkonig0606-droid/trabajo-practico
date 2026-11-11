from database.conexion import BaseDeDatos
from dao.stock_dao import StockDAO
from models.observer import Observador, Sujeto, Eventos
from services.excepciones import ReglaNegocioError

_COSTO_NO_INDICADO = object()


class StockService(Sujeto):            # también es SUJETO: avisa cada cambio de stock
    """Operaciones sobre el stock de cada sucursal."""

    def __init__(self):
        super().__init__()
        self.db = BaseDeDatos()          # Singleton: siempre la misma conexión
        self.dao = StockDAO(self.db)

    def _avisar_cambio(self, sucursal_id, producto_id):
        self.notificar(Eventos.STOCK_MODIFICADO, {
            "sucursal_id": sucursal_id, "producto_id": producto_id,
            "libre": self.libre(sucursal_id, producto_id)})

    def disponible(self, sucursal_id, producto_id):
        fila = self.dao.disponible(sucursal_id, producto_id)
        return fila["disponible"] if fila else 0

    def reservado(self, sucursal_id, producto_id):
        fila = self.dao.reservado(sucursal_id, producto_id)
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
        with self.dao.transaccion():
            self._validar_consistencia(sucursal_id, producto_id)
            filas = self.dao.reservar(sucursal_id, producto_id, cantidad)
            if filas == 0:
                raise ReglaNegocioError(
                    f"Stock insuficiente del producto {producto_id}: hay "
                    f"{self.libre(sucursal_id, producto_id)} libres y se pidieron {cantidad} "
                    "(puede que otro usuario lo haya tomado recién)")
            self._avisar_cambio(sucursal_id, producto_id)

    def consumir_reserva(self, sucursal_id, producto_id, cantidad, motivo, referencia=None,
                         costo_unitario=_COSTO_NO_INDICADO):
        """Al despachar: la mercadería reservada sale físicamente del CD."""
        with self.dao.transaccion():
            self._validar_consistencia(sucursal_id, producto_id)
            filas = self.dao.consumir_reserva(sucursal_id, producto_id, cantidad)
            if filas == 0:
                raise ReglaNegocioError(
                    f"No hay una reserva de {cantidad} unidades del producto {producto_id}")
            self._registrar_movimiento(
                sucursal_id, producto_id, -cantidad, motivo, referencia, costo_unitario)
            self._avisar_cambio(sucursal_id, producto_id)

    def liberar_reserva(self, sucursal_id, producto_id, cantidad):
        """Al anular un bulto: las unidades vuelven a estar libres en el CD."""
        with self.dao.transaccion():
            self._validar_consistencia(sucursal_id, producto_id)
            filas = self.dao.liberar_reserva(sucursal_id, producto_id, cantidad)
            if filas == 0:
                raise ReglaNegocioError(
                    f"No hay una reserva de {cantidad} unidades del producto {producto_id}")
            self._avisar_cambio(sucursal_id, producto_id)

    def sumar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None,
              costo_unitario=_COSTO_NO_INDICADO):
        with self.dao.transaccion():
            self._validar_consistencia(sucursal_id, producto_id)
            self.dao.sumar(sucursal_id, producto_id, cantidad)
            self._registrar_movimiento(
                sucursal_id, producto_id, cantidad, motivo, referencia, costo_unitario)
            self._avisar_cambio(sucursal_id, producto_id)

    def ajustar_disponible(self, sucursal_id, producto_id, disponible, referencia=None):
        if (isinstance(disponible, bool) or not isinstance(disponible, int)
                or disponible < 0):
            raise ReglaNegocioError("El stock disponible debe ser un entero no negativo")
        producto = self.dao.obtener_producto(producto_id)
        if producto is None:
            raise ReglaNegocioError(f"No existe el producto {producto_id}")

        with self.dao.transaccion():
            fila = self.dao.obtener_existencia(sucursal_id, producto_id)
            anterior = fila["disponible"] if fila else 0
            reservado = fila["reservado"] if fila else 0
            if disponible < reservado:
                raise ReglaNegocioError(
                    f"El stock no puede quedar por debajo de las {reservado} unidades reservadas")
            registrado = self.dao.cantidad_registrada_en_movimientos(
                sucursal_id, producto_id)
            inconsistente = anterior != registrado
            if inconsistente and not (isinstance(referencia, str) and referencia.strip()):
                raise ReglaNegocioError(
                    "La conciliación de stock requiere un motivo explícito")
            self.dao.fijar_disponible(sucursal_id, producto_id, disponible)
            diferencia = disponible - registrado
            if diferencia:
                self._registrar_movimiento(
                    sucursal_id, producto_id, diferencia,
                    "CONCILIACION" if inconsistente else "AJUSTE", referencia)
                self._avisar_cambio(sucursal_id, producto_id)
        return self.disponible(sucursal_id, producto_id)

    def restar(self, sucursal_id, producto_id, cantidad, motivo, referencia=None,
               costo_unitario=_COSTO_NO_INDICADO):
        """Descuenta stock LIBRE en una sola sentencia atómica. Lo van a reusar en ventas:
        igual que en crear_bulto, bloquear los productos con GestorBloqueos antes de
        abrir la transacción."""
        with self.dao.transaccion():
            self._validar_consistencia(sucursal_id, producto_id)
            filas = self.dao.restar(sucursal_id, producto_id, cantidad)
            if filas == 0:
                raise ReglaNegocioError(
                    f"Stock insuficiente del producto {producto_id}: "
                    f"hay {self.libre(sucursal_id, producto_id)} libres, se pidieron {cantidad}")
            self._registrar_movimiento(
                sucursal_id, producto_id, -cantidad, motivo, referencia, costo_unitario)
            self._avisar_cambio(sucursal_id, producto_id)

    def _registrar_movimiento(self, sucursal_id, producto_id, cantidad, motivo,
                              referencia, costo_unitario=_COSTO_NO_INDICADO):
        if costo_unitario is _COSTO_NO_INDICADO:
            producto = self.dao.obtener_producto(producto_id)
            if producto is None:
                raise ReglaNegocioError(f"No existe el producto {producto_id}")
            costo_unitario = producto["precio_costo"]
        self.dao.registrar_movimiento(
            sucursal_id, producto_id, cantidad, motivo, referencia, costo_unitario)

    def _validar_consistencia(self, sucursal_id, producto_id):
        existencia = self.dao.obtener_existencia(sucursal_id, producto_id)
        disponible = existencia["disponible"] if existencia else 0
        registrado = self.dao.cantidad_registrada_en_movimientos(
            sucursal_id, producto_id)
        if disponible != registrado:
            raise ReglaNegocioError(
                f"Stock bloqueado para producto {producto_id} en sucursal "
                f"{sucursal_id}: el saldo ({disponible}) no coincide con los movimientos "
                f"({registrado}). Registrá un ajuste de conciliación.")

    def listar(self, sucursal_id):
        return self.dao.listar(sucursal_id)


class StockObserver(Observador):
    """Reacciona a los eventos de logística moviendo el stock."""

    critico = True

    def __init__(self, stock_service: StockService):
        self.stock = stock_service

    def actualizar(self, evento, datos):
        if evento == Eventos.BULTO_DESPACHADO:
            # Sale del CD la mercadería que se había reservado al armar el bulto
            for item in datos["items"]:
                self.stock.consumir_reserva(datos["origen_id"], item["producto_id"],
                                            item["cantidad"], "DESPACHO",
                                            f"bulto {datos['bulto_id']}",
                                            item["costo_unitario"])

        elif evento == Eventos.REMITO_VERIFICADO:
            # Recién ahora entra como DISPONIBLE en el local, y solo lo de bultos verificados
            for item in datos["items_verificados"]:
                self.stock.sumar(datos["destino_id"], item["producto_id"], item["cantidad"],
                                 "RECEPCION", f"remito {datos['remito_numero']}",
                                 item["costo_unitario"])

        elif evento == Eventos.BULTO_RECHAZADO:
            for item in datos["items"]:
                self.stock.sumar(
                    datos["origen_id"], item["producto_id"], item["cantidad"],
                    "RECHAZO_REINGRESO", f"bulto {datos['bulto_id']}",
                    item["costo_unitario"])


# Los otros dos observadores están en services/observadores.py
