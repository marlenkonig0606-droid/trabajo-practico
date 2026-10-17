from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    REAL,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SucursalORM(Base):
    __tablename__ = "sucursal"
    __table_args__ = (CheckConstraint("tipo IN ('CD', 'LOCAL')"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    direccion: Mapped[str | None] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String, nullable=False)


class CategoriaORM(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)


class ProveedorORM(Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cuit: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    razon_social: Mapped[str] = mapped_column(String, nullable=False)


class ProductoORM(Base):
    __tablename__ = "producto"
    __table_args__ = (
        CheckConstraint("precio_costo >= 0"),
        CheckConstraint("precio_venta >= 0"),
        CheckConstraint("stock_minimo >= 0"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    codigo: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False)
    categoria_id: Mapped[int] = mapped_column(ForeignKey("categoria.id"), nullable=False)
    proveedor_id: Mapped[int | None] = mapped_column(ForeignKey("proveedor.id"))
    precio_costo: Mapped[float] = mapped_column(REAL, nullable=False)
    precio_venta: Mapped[float] = mapped_column(REAL, nullable=False)
    stock_minimo: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StockORM(Base):
    __tablename__ = "stock"
    __table_args__ = (CheckConstraint("disponible >= 0"),)

    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    disponible: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class MovimientoStockORM(Base):
    __tablename__ = "movimiento_stock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), nullable=False)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)
    motivo: Mapped[str] = mapped_column(String, nullable=False)
    referencia: Mapped[str | None] = mapped_column(String)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )


class OrdenReposicionORM(Base):
    __tablename__ = "orden_reposicion"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('PENDIENTE', 'EN_PREPARACION', 'DESPACHADA', 'CERRADA')"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    origen_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    destino_id: Mapped[int] = mapped_column(ForeignKey("sucursal.id"), nullable=False)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )
    estado: Mapped[str] = mapped_column(String, nullable=False, default="PENDIENTE")


class DetalleOrdenORM(Base):
    __tablename__ = "detalle_orden"
    __table_args__ = (CheckConstraint("cantidad > 0"),)

    orden_id: Mapped[int] = mapped_column(ForeignKey("orden_reposicion.id"), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)


class RemitoORM(Base):
    __tablename__ = "remito"
    __table_args__ = (
        UniqueConstraint("orden_id"),
        CheckConstraint("estado IN ('ABIERTO', 'DESPACHADO', 'VERIFICADO', 'RECHAZADO')"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    numero: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    orden_id: Mapped[int] = mapped_column(ForeignKey("orden_reposicion.id"), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False, default="ABIERTO")


class BultoORM(Base):
    __tablename__ = "bulto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    remito_id: Mapped[int] = mapped_column(ForeignKey("remito.id"), nullable=False)
    precinto: Mapped[str | None] = mapped_column(String, unique=True)
    estado: Mapped[str] = mapped_column(String, nullable=False, default="PREPARADO")
    fecha_despacho: Mapped[str | None] = mapped_column(String)
    fecha_recepcion: Mapped[str | None] = mapped_column(String)


class DetalleBultoORM(Base):
    __tablename__ = "detalle_bulto"
    __table_args__ = (CheckConstraint("cantidad > 0"),)

    bulto_id: Mapped[int] = mapped_column(ForeignKey("bulto.id"), primary_key=True)
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"), primary_key=True)
    cantidad: Mapped[int] = mapped_column(Integer, nullable=False)


class HistorialBultoORM(Base):
    __tablename__ = "historial_bulto"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bulto_id: Mapped[int] = mapped_column(ForeignKey("bulto.id"), nullable=False)
    estado: Mapped[str] = mapped_column(String, nullable=False)
    fecha: Mapped[str] = mapped_column(
        String, nullable=False, server_default="(datetime('now', 'localtime'))"
    )
    observacion: Mapped[str | None] = mapped_column(Text)
