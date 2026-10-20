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
import threading
from contextlib import contextmanager

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
        # Flask atiende cada request en un hilo distinto, pero la conexión es UNA sola.
        # Este candado evita que dos hilos mezclen sus consultas en la misma conexión.
        # Es RLock (reentrante) porque un mismo hilo puede volver a pedirlo
        # (por ejemplo: transaccion() -> ejecutar()).
        self._candado = threading.RLock()
        with open(RUTA_SCHEMA, encoding="utf-8") as f:
            self._conexion.executescript(f.read())
        self._migrar()

    def _migrar(self):
        """Agrega columnas nuevas a bases creadas con una versión anterior del esquema."""
        columnas = [c["name"] for c in self.consultar("PRAGMA table_info(stock)")]
        if "reservado" not in columnas:
            self._conexion.execute(
                "ALTER TABLE stock ADD COLUMN reservado INTEGER NOT NULL DEFAULT 0")
            self._conexion.commit()
        columnas_orden = [
            c["name"] for c in self.consultar("PRAGMA table_info(orden_reposicion)")
        ]
        if "solicitado_por_usuario_id" not in columnas_orden:
            self._conexion.execute(
                """ALTER TABLE orden_reposicion
                   ADD COLUMN solicitado_por_usuario_id INTEGER REFERENCES usuario(id)""")
            self._conexion.commit()

    # ---------- helpers de consulta ----------
    
    def consultar(self, sql, params=()):
        """Devuelve una lista de dicts."""
        with self._candado:
            cursor = self._conexion.execute(sql, params)
            return [dict(fila) for fila in cursor.fetchall()]

    def consultar_uno(self, sql, params=()):
        with self._candado:
            fila = self._conexion.execute(sql, params).fetchone()
            return dict(fila) if fila else None

    def ejecutar(self, sql, params=()):
        """INSERT/UPDATE/DELETE. Devuelve el id insertado (si corresponde)."""
        with self._candado:
            return self._conexion.execute(sql, params).lastrowid

    def ejecutar_contando(self, sql, params=()):
        """UPDATE/DELETE. Devuelve cuántas filas modificó (0 = la condición no se cumplió)."""
        with self._candado:
            return self._conexion.execute(sql, params).rowcount

    @contextmanager
    def transaccion(self):
        """Uso:  with db.transaccion():  ...
        - Mientras dura, ningún otro hilo puede usar la base (candado tomado).
        - Si algo falla adentro, se hace rollback de todo; si no, commit."""
        with self._candado:
            with self._conexion:
                yield self._conexion

    @classmethod
    def reiniciar(cls):
        """Solo para tests: descarta la instancia única."""
        if cls._instancia is not None:
            cls._instancia._conexion.close()
        cls._instancia = None
