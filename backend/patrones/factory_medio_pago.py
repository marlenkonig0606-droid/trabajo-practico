"""
PATRÓN FACTORY  —  👉 TE TOCA COMPLETARLO A VOS (ver README, paso 4)
--------------
Problema: una venta se puede cobrar en efectivo, con tarjeta (débito/crédito con
recargo por cuotas) o por transferencia. Cada medio calcula distinto el total final
y valida distinto. VentasService no debería tener un if/elif gigante por cada medio.

Solución (como en las diapositivas de Patrones):
- Producto abstracto: MedioPago, con lo mínimo que todo medio sabe hacer.
- Productos concretos: Efectivo, TarjetaCredito, ...
- Fábrica: MedioPagoFactory.crear(tipo, **datos) devuelve el objeto correcto.
  VentasService solo conoce MedioPago, nunca las clases concretas.

Preguntas para que pienses antes de escribir:
  1. ¿Qué método(s) tiene que tener SÍ o SÍ cualquier medio de pago?
  2. ¿Qué datos extra necesita una tarjeta que no necesita el efectivo?
  3. ¿Qué debería pasar si piden crear un tipo que no existe?
"""
from abc import ABC, abstractmethod


class MedioPago(ABC):
    @abstractmethod
    def calcular_total(self, importe: float) -> float:
        """Importe final a cobrar (con recargos/descuentos del medio)."""

    @property
    @abstractmethod
    def nombre(self) -> str:
        ...


class Efectivo(MedioPago):
    # Ejemplo hecho para que veas la forma. Ej: 10% de descuento en efectivo.
    DESCUENTO = 0.10

    @property
    def nombre(self):
        return "EFECTIVO"

    def calcular_total(self, importe):
        return round(importe * (1 - self.DESCUENTO), 2)


# TODO: class TarjetaCredito(MedioPago)  -> recibe cuotas; recargo según cuotas
# TODO: class TarjetaDebito(MedioPago)
# TODO: class Transferencia(MedioPago)


class MedioPagoFactory:
    @staticmethod
    def crear(tipo: str, **datos) -> MedioPago:
        # TODO: completar con el resto de los medios.
        if tipo == "EFECTIVO":
            return Efectivo()
        raise ValueError(f"Medio de pago desconocido: {tipo}")
