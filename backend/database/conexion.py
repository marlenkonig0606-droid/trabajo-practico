"""Configuración compartida de SQLAlchemy para la base de datos de la aplicación."""
from contextlib import contextmanager
import os

from sqlalchemy import create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import scoped_session, sessionmaker

from models.orm import Base

RUTA_DB_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "tp_cd_locales.db")


class BaseDeDatos:
    _instancia = None

    def __new__(cls, ruta=None):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._inicializar(ruta or RUTA_DB_DEFAULT)
        return cls._instancia

    def _inicializar(self, ruta):
        self._ruta = os.path.abspath(ruta)
        database_url = URL.create("sqlite", database=self._ruta)
        self.engine = create_engine(database_url, connect_args={"check_same_thread": False})
        event.listen(self.engine, "connect", self._habilitar_foreign_keys)
        self._sesiones = scoped_session(sessionmaker(bind=self.engine, autoflush=True))
        Base.metadata.create_all(self.engine)
        self._crear_triggers_historial()

    @staticmethod
    def _habilitar_foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    def _crear_triggers_historial(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """CREATE TRIGGER IF NOT EXISTS historial_contenedor_sin_update
                   BEFORE UPDATE ON historial_contenedor
                   BEGIN
                       SELECT RAISE(ABORT, 'El historial de contenedores es inmutable');
                   END"""
            )
            connection.exec_driver_sql(
                """CREATE TRIGGER IF NOT EXISTS historial_contenedor_sin_delete
                   BEFORE DELETE ON historial_contenedor
                   BEGIN
                       SELECT RAISE(ABORT, 'El historial de contenedores es inmutable');
                   END"""
            )

    @property
    def sesion(self):
        return self._sesiones()

    def transaccion(self):
        """Confirma la sesión compartida o revierte todos sus cambios al fallar."""
        return self._transaccion()

    @contextmanager
    def _transaccion(self):
        try:
            yield self.sesion
            self.sesion.commit()
        except Exception:
            self.sesion.rollback()
            raise

    def limpiar_sesion(self):
        self._sesiones.remove()

    @classmethod
    def reiniciar(cls):
        """Solo para tests: descarta la instancia y libera sus recursos."""
        if cls._instancia is not None:
            cls._instancia._sesiones.remove()
            cls._instancia.engine.dispose()
        cls._instancia = None
