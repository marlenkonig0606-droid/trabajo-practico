import sqlite3
from database.conexion import BaseDeDatos


class ProductoDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def _conn(self):
        return self.db.transaccion()

    def crear(self, codigo, nombre, categoria_id, precio_costo, precio_venta,
              stock_minimo, proveedor_id=None):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    INSERT INTO producto (codigo, nombre, categoria_id, precio_costo,
                                          precio_venta, stock_minimo, proveedor_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, nombre, categoria_id, precio_costo, precio_venta,
                      stock_minimo, proveedor_id))
                return True, cur.lastrowid
        except sqlite3.IntegrityError as error:
            if 'UNIQUE constraint failed: producto.codigo' in str(error):
                return False, 'Ya existe un producto con ese código'
            return False, f'Datos inválidos para el producto: {error}'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def obtener_por_id(self, producto_id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute(
                'SELECT * FROM producto WHERE id = ?', (producto_id,)
            )
            return cur.fetchone()

    def obtener_por_codigo(self, codigo):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM producto WHERE codigo = ?', (codigo,))
            return cur.fetchone()

    def listar(self):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM producto ORDER BY nombre')
            return cur.fetchall()

    def obtener_por_categoria(self, categoria_id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM producto WHERE categoria_id = ?',
                             (categoria_id,))
            return cur.fetchall()

    def obtener_por_proveedor(self, proveedor_id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM producto WHERE proveedor_id = ?',
                             (proveedor_id,))
            return cur.fetchall()

    def actualizar(self, id, codigo, nombre, categoria_id, precio_costo,
                   precio_venta, stock_minimo, proveedor_id=None):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    UPDATE producto
                    SET codigo = ?, nombre = ?, categoria_id = ?, precio_costo = ?,
                        precio_venta = ?, stock_minimo = ?, proveedor_id = ?
                    WHERE id = ?
                ''', (codigo, nombre, categoria_id, precio_costo, precio_venta,
                      stock_minimo, proveedor_id, id))
                return cur.rowcount
        except sqlite3.IntegrityError as error:
            if 'UNIQUE constraint failed: producto.codigo' in str(error):
                return False, 'Ya existe un producto con ese código'
            return False, f'Datos inválidos para el producto: {error}'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def eliminar(self, producto_id):
        try:
            with self._conn() as cx:
                cur = cx.execute(
                    'DELETE FROM producto WHERE id = ?', (producto_id,)
                )
                return cur.rowcount
        except sqlite3.IntegrityError:
            return False, 'No se puede eliminar: el producto tiene registros asociados'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'