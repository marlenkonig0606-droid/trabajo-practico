import sqlite3

from database.conexion import BaseDeDatos


class SucursalDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def crear(self, nombre, direccion, tipo):
        try:
            with self.db.transaccion():
                sucursal_id = self.db.ejecutar(
                    'INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?, ?, ?)',
                    (nombre, direccion, tipo),
                )
            return True, sucursal_id
        except sqlite3.IntegrityError:
            return False, 'El nombre debe ser único y el tipo debe ser CD o LOCAL'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def obtener_por_id(self, sucursal_id):
        return self.db.consultar_uno(
            'SELECT * FROM sucursal WHERE id = ?', (sucursal_id,)
        )

    def listar(self):
        return self.db.consultar(
            'SELECT * FROM sucursal ORDER BY tipo, nombre'
        )

    def actualizar(self, sucursal_id, nombre, direccion, tipo):
        if self.obtener_por_id(sucursal_id) is None:
            return False, 'No existe la sucursal'
        try:
            with self.db.transaccion():
                self.db.ejecutar(
                    '''UPDATE sucursal
                       SET nombre = ?, direccion = ?, tipo = ?
                       WHERE id = ?''',
                    (nombre, direccion, tipo, sucursal_id),
                )
            return True, None
        except sqlite3.IntegrityError:
            return False, 'El nombre debe ser único y el tipo debe ser CD o LOCAL'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def eliminar(self, sucursal_id):
        if self.obtener_por_id(sucursal_id) is None:
            return False, 'No existe la sucursal'
        try:
            with self.db.transaccion():
                self.db.ejecutar(
                    'DELETE FROM sucursal WHERE id = ?', (sucursal_id,)
                )
            return True, None
        except sqlite3.IntegrityError:
            return False, 'No se puede eliminar: la sucursal tiene registros asociados'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'