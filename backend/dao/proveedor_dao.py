import sqlite3

from database.conexion import BaseDeDatos


class ProveedorDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def _conn(self):
        return self.db.transaccion()

    def crear(self, razon_social, cuit, nombre):
        try:
            with self._conn() as cx:
                cursor = cx.execute(
                    '''INSERT INTO proveedor (razon_social, cuit, nombre)
                       VALUES (?, ?, ?)''',
                    (razon_social, cuit, nombre),
                )
                return True, cursor.lastrowid
        except sqlite3.IntegrityError:
            return False, 'Ya existe un proveedor con ese CUIT'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def obtener_por_cuit(self, cuit):
        with self._conn() as cx:
            fila = cx.execute(
                'SELECT * FROM proveedor WHERE cuit = ?', (cuit,)
            ).fetchone()
            if fila is None:
                return None
            return dict(fila)

    def obtener_por_id(self, proveedor_id):
        with self._conn() as cx:
            fila = cx.execute(
                'SELECT * FROM proveedor WHERE id = ?', (proveedor_id,)
            ).fetchone()
            if fila is None:
                return None
            return dict(fila)

    def listar(self):
        with self._conn() as cx:
            filas = cx.execute(
                'SELECT * FROM proveedor ORDER BY razon_social'
            ).fetchall()
            resultado = []
            for fila in filas:
                resultado.append(dict(fila))
            return resultado

    def actualizar(self, proveedor_id, razon_social, cuit, nombre):
        try:
            with self._conn() as cx:
                cursor = cx.execute(
                    '''UPDATE proveedor
                       SET razon_social = ?, cuit = ?, nombre = ?
                       WHERE id = ?''',
                    (razon_social, cuit, nombre, proveedor_id),
                )
                return cursor.rowcount
        except sqlite3.IntegrityError:
            return False, 'Ya existe un proveedor con ese CUIT'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def eliminar(self, proveedor_id):
        try:
            with self._conn() as cx:
                cursor = cx.execute(
                    'DELETE FROM proveedor WHERE id = ?', (proveedor_id,)
                )
                return cursor.rowcount
        except sqlite3.IntegrityError:
            return False, 'No se puede eliminar: el proveedor tiene productos asociados'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'



