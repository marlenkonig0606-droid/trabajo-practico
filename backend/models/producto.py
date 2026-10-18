from sqlalchemy import CheckConstraint, ForeignKey, Integer, REAL, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Producto(Base):
    __tablename__ = "producto"
    __table_args__ = (
        CheckConstraint("precio_costo >= 0"),
        CheckConstraint("precio_venta >= 0"),
        CheckConstraint("stock_minimo >= 0"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"), nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedor.id"))
    precio_costo: Mapped[float] = mapped_column(REAL, nullable=False)
    precio_venta: Mapped[float] = mapped_column(REAL, nullable=False)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    def __init__(
        self,
        codigo,
        nombre,
        categoria_id,
        precio_costo,
        precio_venta,
        stock_minimo=0,
        proveedor_id=None,
        id=None,
    ):
        if not nombre:
            raise ValueError("El nombre no puede estar vacío")
        if precio_venta < precio_costo:
            raise ValueError("El precio de venta no puede ser menor al de costo")

        self.id = id
        self.codigo = codigo
        self.nombre = nombre
        self.categoria_id = categoria_id
        self.proveedor_id = proveedor_id
        self.precio_costo = precio_costo
        self.precio_venta = precio_venta
        self.stock_minimo = stock_minimo

    def margen_unitario(self):
        return self.precio_venta - self.precio_costo

    def to_dict(self):
        return {
            "id": self.id,
            "codigo": self.codigo,
            "nombre": self.nombre,
            "categoria_id": self.categoria_id,
            "proveedor_id": self.proveedor_id,
            "precio_costo": self.precio_costo,
            "precio_venta": self.precio_venta,
            "stock_minimo": self.stock_minimo,
            "margen_unitario": self.margen_unitario(),
        }

    def __str__(self):
        return f"Producto(id={self.id}, codigo={self.codigo}, nombre={self.nombre}, "
