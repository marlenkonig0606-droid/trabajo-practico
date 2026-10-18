from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Proveedor(Base):
    __tablename__ = "proveedor"

    id: Mapped[int] = mapped_column(primary_key=True)
    cuit: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    razon_social: Mapped[str] = mapped_column(String, nullable=False)

    def __init__(self, cuit, razon_social, id=None):
        self.id = id
        self.cuit = cuit
        self.razon_social = razon_social

    def to_dict(self):
        return {
            "id": self.id,
            "cuit": self.cuit,
            "razon_social": self.razon_social,
        }
