
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Categoria(Base):
    __tablename__ = "categoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String, nullable=False, unique=True)

    def __init__(self, nombre, id=None):
        self.id = id
        self.nombre = nombre

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}