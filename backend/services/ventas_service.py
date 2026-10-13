"""
👉 PROCESO 7 — TE TOCA A VOS (README, paso 5)

Registrar ventas (uno o más productos), cobro con medio de pago, comprobante
y devoluciones con impacto en stock y caja.

Validaciones de la consigna que aplican acá:
  - No vender más que el stock DISPONIBLE y VERIFICADO
      -> ya existe StockService.restar(), que valida y descuenta.
  - No aceptar devoluciones que no correspondan a una venta registrada
    (ni devolver más unidades de las que se vendieron).
  - Solo se vende en sucursales tipo LOCAL (Sucursal.puede_vender()).

Usá LogisticaService como modelo: validar primero, después
`with self.db.transaccion():` para que si algo falla no quede nada a medias.
"""
from database.conexion import BaseDeDatos
from patrones.factory_medio_pago import MedioPagoFactory
from services.stock_service import StockService
from services.excepciones import ReglaNegocioError


class VentasService:
    def __init__(self):
        self.db = BaseDeDatos()
        self.stock = StockService()

    def registrar_venta(self, sucursal_id, items, medio_pago, **datos_pago):
        # 1. ¿la sucursal existe y puede vender?
        # 2. validar items (cantidades > 0, productos existentes, sin repetidos)
        # 3. calcular subtotal con producto.precio_venta
        # 4. medio = MedioPagoFactory.crear(medio_pago, **datos_pago); total = medio.calcular_total(subtotal)
        # 5. en una transacción: insertar venta + detalle + pago + comprobante,
        #    y por cada item self.stock.restar(..., "VENTA", f"venta {id}")
        raise NotImplementedError("registrar_venta: completar")

    def registrar_devolucion(self, venta_id, items, motivo):
        raise NotImplementedError("registrar_devolucion: completar")
