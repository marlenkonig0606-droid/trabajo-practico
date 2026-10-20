"""
Herencia: Sucursal es la clase base; LocalVenta y CentroDistribucion la especializan.
Ambas se guardan en la misma tabla `sucursal` diferenciadas por la columna `tipo`.
"""
from abc import ABC, abstractmethod


class Sucursal(ABC):
    def __init__(self, id, nombre, direccion=None):
        self.id = id
        self.nombre = nombre
        self.direccion = direccion

    @property
    @abstractmethod
    def tipo(self):
        ...

    @abstractmethod
    def puede_vender(self):
        """¿Se le puede vender al público desde esta sucursal?"""

    @staticmethod
    def desde_fila(fila):
        clase = CentroDistribucion if fila["tipo"] == "CD" else LocalVenta
        return clase(fila["id"], fila["nombre"], fila["direccion"])

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre,
                "direccion": self.direccion, "tipo": self.tipo}


class CentroDistribucion(Sucursal):
    @property
    def tipo(self):
        return "CD"

    def puede_vender(self):
        return False


class LocalVenta(Sucursal):
    @property
    def tipo(self):
        return "LOCAL"

    def puede_vender(self):
        return True
