"""
Ciclo de vida del contenedor (lo que la cátedra va a evaluar "críticamente").

    PREPARADO ──precintar──▶ PRECINTADO ──despachar──▶ EN_TRANSITO
                                                          │
                                                       recibir
                                                          ▼
                                                      RECIBIDO
                                                     ╱        ╲
                                     precinto intacto          precinto roto
                                           ▼                        ▼
                                      VERIFICADO               RECHAZADO

VERIFICADO y RECHAZADO son estados FINALES: desde ahí no se puede ir a ningún lado.
"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class EstadoContenedor:
    PREPARADO = "PREPARADO"
    PRECINTADO = "PRECINTADO"
    EN_TRANSITO = "EN_TRANSITO"
    RECIBIDO = "RECIBIDO"
    VERIFICADO = "VERIFICADO"
    RECHAZADO = "RECHAZADO"

    # Tabla de transiciones válidas: estado actual -> estados a los que puede pasar
    TRANSICIONES = {
        PREPARADO: {PRECINTADO},
        PRECINTADO: {EN_TRANSITO},
        EN_TRANSITO: {RECIBIDO},
        RECIBIDO: {VERIFICADO, RECHAZADO},
        VERIFICADO: set(),
        RECHAZADO: set(),
    }

    FINALES = {VERIFICADO, RECHAZADO}

    @classmethod
    def puede_pasar(cls, desde, hacia):
        return hacia in cls.TRANSICIONES.get(desde, set())


class Contenedor(Base):
    __tablename__ = "contenedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    remito_id: Mapped[int] = mapped_column(ForeignKey("remito.id"), nullable=False)
    precinto: Mapped[str | None] = mapped_column(String, unique=True)
    estado: Mapped[str] = mapped_column(
        String, nullable=False, default=EstadoContenedor.PREPARADO
    )
    fecha_despacho: Mapped[str | None] = mapped_column(String)
    fecha_recepcion: Mapped[str | None] = mapped_column(String)

    def __init__(
        self,
        id=None,
        remito_id=None,
        estado=EstadoContenedor.PREPARADO,
        precinto=None,
        fecha_despacho=None,
        fecha_recepcion=None,
        items=None,
    ):
        self.id = id
        self.remito_id = remito_id
        self.estado = estado
        self.precinto = precinto
        self.fecha_despacho = fecha_despacho
        self.fecha_recepcion = fecha_recepcion
        self.items = items

    @property
    def items(self):
        return self.__dict__.get("_items", [])

    @items.setter
    def items(self, items):
        self.__dict__["_items"] = items or []

    def cambiar_estado(self, nuevo_estado):
        """El objeto se protege a sí mismo: no acepta transiciones inválidas."""
        if not EstadoContenedor.puede_pasar(self.estado, nuevo_estado):
            raise ValueError(
                f"El contenedor {self.id} no puede pasar de {self.estado} a {nuevo_estado}"
            )
        self.estado = nuevo_estado

    def esta_finalizado(self):
        return self.estado in EstadoContenedor.FINALES

    def to_dict(self):
        return {
            "id": self.id, "remito_id": self.remito_id, "estado": self.estado,
            "precinto": self.precinto, "fecha_despacho": self.fecha_despacho,
            "fecha_recepcion": self.fecha_recepcion, "items": self.items,
        }
