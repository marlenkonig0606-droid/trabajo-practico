from sqlalchemy import CheckConstraint, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Stock(Base):
    __tablename__ = "stock"
    __table_args__ = (CheckConstraint("disponible >= 0"),)

    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(self, sucursal_id, producto_id, disponible=0):
        self.sucursal_id = sucursal_id
        self.producto_id = producto_id
        self.disponible = disponible


class MovimientoStock(Base):
    __tablename__ = "movimiento_stock"

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(String, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )

    def __init__(
        self, sucursal_id, producto_id, cantidad, motivo, referencia=None, id=None
    ):
        self.id = id
        self.sucursal_id = sucursal_id
        self.producto_id = producto_id
        self.cantidad = cantidad
        self.motivo = motivo
        self.referencia = referencia
