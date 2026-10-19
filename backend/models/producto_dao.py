import sqlite3


class ProductoDAO:
    def __init__(self, db_path='inventario.db'):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def crear(self, codigo, nombre, categoria_id, precio_costo, precio_venta,
              stock_minimo, proveedor_id):
        try:
            with self._conn() as cx:
                cur = cx.execute('''
                    INSERT INTO producto (codigo, nombre, categoria_id, precio_costo,
                                          precio_venta, stock_minimo, proveedor_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (codigo, nombre, categoria_id, precio_costo, precio_venta,
                      stock_minimo, proveedor_id))
                return True, cur.lastrowid
        except sqlite3.IntegrityError:
            return False, "Ya existe un producto con ese código"
        except sqlite3.Error as e:
            return False, f"Error de base de datos: {e}"

    def obtener_por_id(self, id):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM producto WHERE id = ?', (id,))
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
                   precio_venta, stock_minimo, proveedor_id):
        with self._conn() as cx:
            cur = cx.execute('''
                UPDATE producto
                SET codigo = ?, nombre = ?, categoria_id = ?, precio_costo = ?,
                    precio_venta = ?, stock_minimo = ?, proveedor_id = ?
                WHERE id = ?
            ''', (codigo, nombre, categoria_id, precio_costo, precio_venta,
                  stock_minimo, proveedor_id, id))
            return cur.rowcount

    def eliminar(self, id):
        with self._conn() as cx:
            cur = cx.execute('DELETE FROM producto WHERE id = ?', (id,))
            return cur.rowcount