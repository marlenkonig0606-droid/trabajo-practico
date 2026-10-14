"""
PATRÓN SINGLETON
----------------
Problema: toda la aplicación necesita hablar con la MISMA base de datos.
Si cada servicio creara su propia conexión, habría conexiones duplicadas y
transacciones que no se ven entre sí.

Solución: la clase controla su propia instanciación en __new__.
La primera vez crea el objeto; las siguientes devuelve siempre el mismo.

    a = BaseDeDatos()
    b = BaseDeDatos()
    a is b   # True
"""
import os
import sqlite3

RUTA_SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")
RUTA_DB_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "tp_cd_locales.db")


class BaseDeDatos:
    _instancia = None

    def __new__(cls, ruta=None):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._inicializar(ruta or RUTA_DB_DEFAULT)
        return cls._instancia

    def _inicializar(self, ruta):
        self._ruta = ruta
        # check_same_thread=False porque Flask atiende requests en distintos hilos
        self._conexion = sqlite3.connect(ruta, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row      # filas accesibles por nombre
        self._conexion.execute("PRAGMA foreign_keys = ON")
        with open(RUTA_SCHEMA, encoding="utf-8") as f:
            self._conexion.executescript(f.read())

    # ---------- helpers de consulta ----------
    
    def consultar(self, sql, params=()):
        """Devuelve una lista de dicts."""
        cursor = self._conexion.execute(sql, params)
        return [dict(fila) for fila in cursor.fetchall()]

    def consultar_uno(self, sql, params=()):
        fila = self._conexion.execute(sql, params).fetchone()
        return dict(fila) if fila else None

    def ejecutar(self, sql, params=()):
        """INSERT/UPDATE/DELETE. Devuelve el id insertado (si corresponde)."""
        cursor = self._conexion.execute(sql, params)
        return cursor.lastrowid

    def transaccion(self):
        """Uso:  with db.transaccion():  ...
        Si algo falla adentro, se hace rollback de todo."""
        return self._conexion

    @classmethod
    def reiniciar(cls):
        """Solo para tests: descarta la instancia única."""
        if cls._instancia is not None:
            cls._instancia._conexion.close()
        cls._instancia = None
