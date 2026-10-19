import sqlite3


class CategoriaDAO:
    def __init__(self, db_path='inventario.db'):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def crear(self, nombre, descripcion):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    INSERT INTO categoria (nombre, descripcion)
                    VALUES (?, ?)
                ''', (nombre, descripcion))
                return True, cur.lastrowid
        except sqlite3.IntegrityError:
            return False, "Ya existe una categoría con ese nombre"
        except sqlite3.Error as e:
            return False, f"Error de base de datos: {e}"

    def obtener_por_id(self, id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM categoria WHERE id = ?', (id,))
            return cur.fetchone()

    def listar(self):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM categoria ORDER BY nombre')
            return cur.fetchall()

    def actualizar(self, id, nombre, descripcion):
        with self._conn() as cx:
            cur = cx.execute('''
                UPDATE categoria
                SET nombre = ?, descripcion = ?
                WHERE id = ?
            ''', (nombre, descripcion, id))
            return cur.rowcount

    def eliminar(self, id):
        with self._conn() as cx:
            cur = cx.execute('DELETE FROM categoria WHERE id = ?', (id,))
            return cur.rowcount