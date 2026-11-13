from abc import ABC, abstractmethod

class IMedioDePago(ABC):   #IProducto  - interface
    def __init__(self, nombre: str):
        self.nombre = nombre   #todos los medios de pago tienen un nombre

    @abstractmethod
    def calcular_total(self, importe: float) -> float:    
        ...
 #todos los medios de pago deben implementar el metodo: calcular_total, que recibe un importe y devuelve el total a pagar según el medio de pago.


class Efectivo(IMedioDePago):  #ProductoConcreto
    DESCUENTO = 0.10

    def __init__(self):
        super().__init__(nombre="EFECTIVO")

    def calcular_total(self, importe):
        return importe * (1 - self.DESCUENTO)


class TarjetaCredito(IMedioDePago):   #ProductoConcreto
    RECARGO_POR_CUOTA = 0.05

    def __init__(self, cuotas):
        if isinstance(cuotas, bool) or not isinstance(cuotas, int) or cuotas <= 0:
            raise ValueError("La cantidad de cuotas debe ser un entero positivo")
        super().__init__(nombre="TARJETA_CREDITO")
        self.cuotas = cuotas

    def calcular_total(self, importe):
        recargo = self.RECARGO_POR_CUOTA * self.cuotas
        return importe * (1 + recargo)


class TarjetaDebito(IMedioDePago):    #ProductoConcreto
    def __init__(self):
        super().__init__(nombre="TARJETA_DEBITO")

    def calcular_total(self, importe):
        return importe


class Transferencia(IMedioDePago):    #ProductoConcreto
    def __init__(self):
        super().__init__(nombre="TRANSFERENCIA")

    def calcular_total(self, importe):
        return importe
