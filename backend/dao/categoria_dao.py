import sqlite3
from database.conexion import BaseDeDatos


class CategoriaDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def _conn(self):
        return self.db.transaccion()

    def crear(self, nombre, descripcion=None):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    INSERT INTO categoria (nombre, descripcion)
                    VALUES (?, ?)
                ''', (nombre, descripcion))
                return True, cur.lastrowid
        except sqlite3.IntegrityError as error:
            if 'UNIQUE constraint failed: categoria.nombre' in str(error):
                return False, 'Ya existe una categoría con ese nombre'
            return False, f'Datos inválidos para la categoría: {error}'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def obtener_por_id(self, categoria_id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            fila = cx.execute(
                'SELECT * FROM categoria WHERE id = ?', (categoria_id,)
            ).fetchone()
            if fila is None:
                return None
            return dict(fila)

    def listar(self):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            filas = cx.execute(
                'SELECT * FROM categoria ORDER BY nombre'
            ).fetchall()
            resultado = []
            for fila in filas:
                resultado.append(dict(fila))
            return resultado

    def actualizar(self, categoria_id, nombre, descripcion=None):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    UPDATE categoria
                    SET nombre = ?, descripcion = ?
                    WHERE id = ?
                ''', (nombre, descripcion, categoria_id))
                return cur.rowcount
        except sqlite3.IntegrityError as error:
            if 'UNIQUE constraint failed: categoria.nombre' in str(error):
                return False, 'Ya existe una categoría con ese nombre'
            return False, f'Datos inválidos para la categoría: {error}'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def eliminar(self, categoria_id):
        try:
            with self._conn() as cx:
                cur = cx.execute(
                    'DELETE FROM categoria WHERE id = ?', (categoria_id,)
                )
                return cur.rowcount
        except sqlite3.IntegrityError:
            return False, 'No se puede eliminar: la categoría tiene productos asociados'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'