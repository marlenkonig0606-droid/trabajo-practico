from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class OrdenReposicion(Base):
    __tablename__ = "orden_reposicion"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE', 'EN_PREPARACION', 'DESPACHADA', 'CERRADA')"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    origen_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    destino_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )
    estado: Mapped[str] = mapped_column(String, nullable=False, default="PENDIENTE")

    def __init__(self, origen_id, destino_id, estado="PENDIENTE", id=None):
        self.id = id
        self.origen_id = origen_id
        self.destino_id = destino_id
        self.estado = estado


class DetalleOrden(Base):
    __tablename__ = "detalle_orden"
    __table_args__ = (CheckConstraint("cantidad > 0"),)

    orden_id: Mapped[int] = mapped_column(
        ForeignKey("orden_reposicion.id"), primary_key=True
    )
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)

    def __init__(self, orden_id, producto_id, cantidad):
        self.orden_id = orden_id
        self.producto_id = producto_id
        self.cantidad = cantidad


class Remito(Base):
    __tablename__ = "remito"
    __table_args__ = (
        UniqueConstraint("orden_id"),
        CheckConstraint("estado IN ('ABIERTO', 'DESPACHADO', 'VERIFICADO', 'RECHAZADO')"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    numero: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("orden_reposicion.id"), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False, default="ABIERTO")

    def __init__(self, numero, orden_id, estado="ABIERTO", id=None):
        self.id = id
        self.numero = numero
        self.orden_id = orden_id
        self.estado = estado
