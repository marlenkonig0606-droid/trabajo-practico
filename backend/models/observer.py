"""
PATRÓN OBSERVER
---------------
Problema: cuando un remito queda VERIFICADO tienen que pasar varias cosas
(sumar stock al local, avisar si algo sigue bajo el mínimo, registrar mermas...).
Si LogisticaService hiciera todo eso directamente quedaría acoplado a todo.

Solución:
- El SUJETO mantiene una lista de observadores y les avisa.
- Cada OBSERVADOR implementa `actualizar(evento, datos)` y decide qué hacer.
- Agregar una reacción nueva = crear un observador y suscribirlo. No se toca el sujeto.

En este sistema hay DOS sujetos y TRES observadores (se conectan en app.py):

    LogisticaService ──┬──▶ StockObserver             mueve el stock al despachar / verificar
       (sujeto)        └──▶ AuditoriaObserver         registra cada evento logístico
                                    │
    StockService ──────────▶ AlertaStockMinimoObserver   alerta si un producto queda
       (sujeto)                                         por debajo del stock mínimo

Fijate que StockObserver, al mover el stock, hace que StockService avise a su vez
STOCK_MODIFICADO: los eventos se encadenan sin que ninguna clase conozca a las otras.
"""
from abc import ABC, abstractmethod


class Observador(ABC):
    @abstractmethod
    def actualizar(self, evento: str, datos: dict):
        ...


class Sujeto:
    def __init__(self):
        self._observadores = []

    def suscribir(self, observador: Observador):
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desuscribir(self, observador: Observador):
        self._observadores.remove(observador)

    def notificar(self, evento: str, datos: dict):
        for observador in self._observadores:
            observador.actualizar(evento, datos)


# Nombres de eventos (constantes para no escribir strings sueltos)
class Eventos:
    # los notifica LogisticaService
    BULTO_DESPACHADO = "BULTO_DESPACHADO"
    REMITO_VERIFICADO = "REMITO_VERIFICADO"
    BULTO_RECHAZADO = "BULTO_RECHAZADO"
    # lo notifica StockService cada vez que cambia el stock de un producto en una sucursal
    STOCK_MODIFICADO = "STOCK_MODIFICADO"
