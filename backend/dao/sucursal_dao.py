import sqlite3

from database.conexion import BaseDeDatos


class SucursalDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def crear(self, nombre, direccion, tipo):
        try:
            nombre = nombre.strip()
            with self.db.transaccion() as cx:
                if self._nombre_duplicado(cx, nombre):
                    return False, 'Ya existe una sucursal con ese nombre'
                cursor = cx.execute(
                    'INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?, ?, ?)',
                    (nombre, direccion, tipo),
                )
                sucursal_id = cursor.lastrowid
            return True, sucursal_id
        except sqlite3.IntegrityError:
            return False, 'El nombre debe ser único y el tipo debe ser CD o LOCAL'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def obtener_por_id(self, sucursal_id):
        return self.db.consultar_uno(
            'SELECT * FROM sucursal WHERE id = ?', (sucursal_id,)
        )

    def listar(self, solo_activas=False):
        filtro = "WHERE activo=1" if solo_activas else ""
        return self.db.consultar(
            f'SELECT * FROM sucursal {filtro} ORDER BY tipo, nombre'
        )

    def actualizar(self, sucursal_id, nombre, direccion, tipo):
        try:
            nombre = nombre.strip()
            with self.db.transaccion() as cx:
                if self._nombre_duplicado(cx, nombre, excluir_id=sucursal_id):
                    return False, 'Ya existe una sucursal con ese nombre'
                cursor = cx.execute(
                    '''UPDATE sucursal
                       SET nombre = ?, direccion = ?, tipo = ?
                       WHERE id = ?''',
                    (nombre, direccion, tipo, sucursal_id),
                )
                if cursor.rowcount == 0:
                    return False, 'No existe la sucursal'
                return True, None
        except sqlite3.IntegrityError:
            return False, 'El nombre debe ser único y el tipo debe ser CD o LOCAL'
        except sqlite3.Error as error:
            return False, f'Error de base de datos: {error}'

    def eliminar(self, sucursal_id):
        return self.cambiar_estado(sucursal_id, False)

    @staticmethod
    def _nombre_duplicado(cx, nombre, excluir_id=None):
        filas = cx.execute(
            "SELECT id, nombre FROM sucursal WHERE id != COALESCE(?, -1)",
            (excluir_id,),
        ).fetchall()
        clave = nombre.strip().casefold()
        return any(fila["nombre"].strip().casefold() == clave for fila in filas)

    def cambiar_estado(self, sucursal_id, activo):
        with self.db.transaccion():
            return self.db.ejecutar_contando(
                'UPDATE sucursal SET activo=? WHERE id=?',
                (int(activo), sucursal_id))

    def tiene_bultos_pendientes_de_recepcion(self, sucursal_id):
        return self.db.consultar_uno(
            """SELECT 1 FROM orden_reposicion o
               JOIN remito r ON r.orden_id=o.id
               JOIN bulto b ON b.remito_id=r.id
               WHERE o.destino_id=? AND b.estado IN ('EN_TRANSITO', 'RECIBIDO')
               LIMIT 1""",
            (sucursal_id,)) is not None