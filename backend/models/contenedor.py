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
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, Text
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
    __allow_unmapped__ = True

    def __init__(
        self,
        remito_id,
        estado=EstadoContenedor.PREPARADO,
        precinto=None,
        fecha_despacho=None,
        fecha_recepcion=None,
        items=None,
        id=None,
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


class DetalleContenedor(Base):
    __tablename__ = "detalle_contenedor"
    __table_args__ = (CheckConstraint("cantidad > 0"),)

    contenedor_id: Mapped[int] = mapped_column(
        ForeignKey("contenedor.id"), primary_key=True
    )
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(self, contenedor_id, producto_id, cantidad):
        self.contenedor_id = contenedor_id
        self.producto_id = producto_id
        self.cantidad = cantidad


class HistorialContenedor(Base):
    __tablename__ = "historial_contenedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    contenedor_id: Mapped[int] = mapped_column(
        ForeignKey("contenedor.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )
    observacion: Mapped[str | None] = mapped_column(Text)

    def __init__(self, contenedor_id, estado, observacion=None, id=None, fecha=None):
        self.id = id
        self.contenedor_id = contenedor_id
        self.estado = estado
        self.observacion = observacion
        if fecha is not None:
            self.fecha = fecha
