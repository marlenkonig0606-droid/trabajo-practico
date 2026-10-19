from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Sucursal(Base):
    """Sucursal mapeada a la tabla compartida por locales y el centro de distribución."""

    __tablename__ = "sucursal"
    __table_args__ = (CheckConstraint("tipo IN ('CD', 'LOCAL')"),)
    __mapper_args__ = {"polymorphic_on": "tipo", "polymorphic_abstract": True}

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    direccion: Mapped[str | None] = mapped_column(String)
    tipo: Mapped[str] = mapped_column(String, nullable=False)

    def __init__(self, nombre, tipo, direccion=None, id=None):
        self.id = id
        self.nombre = nombre
        self.direccion = direccion
        self.tipo = tipo

    def puede_vender(self):
        return self.tipo == "LOCAL"

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre,
                "direccion": self.direccion, "tipo": self.tipo}


class CentroDistribucion(Sucursal):
    __mapper_args__ = {"polymorphic_identity": "CD"}

    def __init__(self, nombre, direccion=None, id=None):
        super().__init__(nombre=nombre, direccion=direccion, tipo="CD", id=id)


class LocalVenta(Sucursal):
    __mapper_args__ = {"polymorphic_identity": "LOCAL"}

    def __init__(self, nombre, direccion=None, id=None):
        super().__init__(nombre=nombre, direccion=direccion, tipo="LOCAL", id=id)
