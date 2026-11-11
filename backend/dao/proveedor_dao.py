import sqlite3

from database.conexion import BaseDeDatos
from models.proveedor import normalizar_cuit


class ProveedorDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def _conn(self):
        return self.db.transaccion()

    def crear(self, razon_social, cuit, nombre):
        try:
            with self._conn() as cx:
                cuit = normalizar_cuit(cuit)
                existentes = cx.execute("SELECT cuit FROM proveedor").fetchall()
                if any(normalizar_cuit(fila["cuit"]) == cuit for fila in existentes):
                    return False, "Ya existe un proveedor con ese CUIT"
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
            filas = cx.execute('SELECT * FROM proveedor').fetchall()
            cuit_normalizado = normalizar_cuit(cuit)
            return next(
                (dict(fila) for fila in filas
                 if normalizar_cuit(fila["cuit"]) == cuit_normalizado),
                None,
            )

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
                cuit = normalizar_cuit(cuit)
                existentes = cx.execute(
                    "SELECT id, cuit FROM proveedor WHERE id != ?", (proveedor_id,)
                ).fetchall()
                if any(normalizar_cuit(fila["cuit"]) == cuit for fila in existentes):
                    return False, 'Ya existe un proveedor con ese CUIT'
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
        return self.cambiar_estado(proveedor_id, False)

    def cambiar_estado(self, proveedor_id, activo):
        with self._conn() as cx:
            return cx.execute(
                'UPDATE proveedor SET activo=? WHERE id=?',
                (int(activo), proveedor_id),
            ).rowcount



