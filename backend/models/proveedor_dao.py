import sqlite3

class ProveedorDAO:
    def __init__(self, db_path='inventario.db'):
        self.db_path = db_path

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def crear(self, razon_social, nombre, cuit, telefono, mail, direccion):
        with self._conn() as cx:
            cx.execute('''INSERT INTO proveedor (razon_social, nombre, cuit, telefono, mail, direccion) VALUES(?,?,?,?,?,?)'''
                       , (razon_social, nombre, cuit, telefono, mail, direccion))

    def obtener_por_cuit(self, cuit):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM proveedor WHERE cuit = ?', (cuit,))
            return cur.fetchone()

    def listar(self):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            cur = cx.execute('SELECT * FROM proveedor')
            return cur.fetchall()

    def eliminar(self, cuit):
        with self._conn() as cx:
            cur = cx.execute('SELECT * FROM proveedor WHERE cuit = ?', (cuit,))
            return cur.rowcount

    
        