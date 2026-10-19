from abc import ABC, abstractmethod

from models.medio_pago import (
    Efectivo,
    IMedioDePago,
    TarjetaCredito,
    TarjetaDebito,
    Transferencia,
)
from services.excepciones import ReglaNegocioError



class ICreadorMedioDePago(ABC):   #ICreador
    @abstractmethod
    def crear_medio_de_pago(self, **datos) -> IMedioDePago:
        ...
#acepta cualquier cantidad de argumentos nombrados y los reune en un diccionario llamado datos.

class CreadorEfectivo(ICreadorMedioDePago):    #CreadorConcreto
    def crear_medio_de_pago(self, **_datos):
        return Efectivo()


class CreadorTarjetaCredito(ICreadorMedioDePago):   #CreadorConcreto
    def crear_medio_de_pago(self, **datos):
        cuotas = datos.get("cuotas", 1)
        if isinstance(cuotas, bool) or not isinstance(cuotas, int) or cuotas <= 0:
            raise ReglaNegocioError("La cantidad de cuotas debe ser un entero positivo")
        return TarjetaCredito(cuotas=cuotas)


class CreadorTarjetaDebito(ICreadorMedioDePago):     #CreadorConcreto
    def crear_medio_de_pago(self, **_datos):
        return TarjetaDebito()

 
class CreadorTransferencia(ICreadorMedioDePago):   #CreadorConcreto
    def crear_medio_de_pago(self, **_datos):
        return Transferencia()


# El servicio elige un creador concreto por el tipo solicitado; la creación del
# producto queda delegada al método sobrescrito de ese creador.
CREADORES_MEDIO_DE_PAGO = {
    "EFECTIVO": CreadorEfectivo(),
    "TARJETA_CREDITO": CreadorTarjetaCredito(),
    "TARJETA_DEBITO": CreadorTarjetaDebito(),
    "TRANSFERENCIA": CreadorTransferencia(),
}


def obtener_creador_medio_de_pago(tipo):
    if not isinstance(tipo, str):
        raise ReglaNegocioError(f"Medio de pago desconocido: {tipo}")
    try:
        return CREADORES_MEDIO_DE_PAGO[tipo]
    except KeyError as error:
        raise ReglaNegocioError(f"Medio de pago desconocido: {tipo}") from error
