"""
PATRÓN OBSERVER
---------------
Problema: cuando un remito queda VERIFICADO tienen que pasar varias cosas
(sumar stock al local, avisar si algo sigue bajo el mínimo, registrar mermas...).
Si LogisticaService hiciera todo eso directamente quedaría acoplado a todo.

Solución:
- El SUJETO (LogisticaService) mantiene una lista de observadores y les avisa.
- Cada OBSERVADOR implementa `actualizar(evento, datos)` y decide qué hacer.
- Agregar una reacción nueva = crear un observador y suscribirlo. No se toca el sujeto.
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


