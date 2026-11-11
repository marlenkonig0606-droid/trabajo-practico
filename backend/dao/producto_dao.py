import sqlite3
from database.conexion import BaseDeDatos
from models.producto import normalizar_codigo


class ProductoDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def _conn(self):
        return self.db.transaccion()

    def crear(self, codigo, nombre, categoria_id, precio_costo, precio_venta,
              stock_minimo, proveedor_id=None):
        try:
            with self._conn() as cx:
                codigo = normalizar_codigo(codigo)
                if self._codigo_duplicado(cx, codigo):
                    return False, 'Ya existe un producto con ese código'
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

    def listar(self, solo_activos=False):
        with self._conn() as cx:
            cx.row_factory = sqlite3.Row
            filtro = "WHERE activo=1" if solo_activos else ""
            cur = cx.execute(f'SELECT * FROM producto {filtro} ORDER BY nombre')
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
                codigo = normalizar_codigo(codigo)
                if self._codigo_duplicado(cx, codigo, excluir_id=id):
                    return False, 'Ya existe un producto con ese código'
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
        return self.cambiar_estado(producto_id, False)

    def cambiar_estado(self, producto_id, activo):
        with self._conn() as cx:
            return cx.execute(
                'UPDATE producto SET activo=? WHERE id=?',
                (int(activo), producto_id),
            ).rowcount

    def listar_para_sucursal(self, sucursal_id, solo_habilitados=True):
        filtro_habilitado = "AND ps.habilitado=1" if solo_habilitados else ""
        return self.db.consultar(
            f"""SELECT p.*, COALESCE(ps.habilitado, 0) AS habilitado
                FROM producto p
                LEFT JOIN producto_sucursal ps
                  ON ps.producto_id=p.id AND ps.sucursal_id=?
                WHERE p.activo=1 {filtro_habilitado}
                ORDER BY p.nombre""",
            (sucursal_id,),
        )

    def esta_habilitado_en_sucursal(self, sucursal_id, producto_id):
        fila = self.db.consultar_uno(
            """SELECT ps.habilitado, p.activo FROM producto p
               LEFT JOIN producto_sucursal ps
                 ON ps.producto_id=p.id AND ps.sucursal_id=?
               WHERE p.id=?""",
            (sucursal_id, producto_id),
        )
        return bool(fila and fila["activo"] and fila["habilitado"])

    def cambiar_habilitacion(self, sucursal_id, producto_id, habilitado):
        with self._conn() as cx:
            return cx.execute(
                """UPDATE producto_sucursal SET habilitado=?
                   WHERE sucursal_id=? AND producto_id=?""",
                (int(habilitado), sucursal_id, producto_id),
            ).rowcount

    def stock_en_sucursal(self, sucursal_id, producto_id):
        return self.db.consultar_uno(
            """SELECT disponible, reservado FROM stock
               WHERE sucursal_id=? AND producto_id=?""",
            (sucursal_id, producto_id),
        ) or {"disponible": 0, "reservado": 0}

    def tiene_bultos_pendientes_en_sucursal(self, sucursal_id, producto_id):
        filtro_sucursal = "AND o.destino_id=?" if sucursal_id is not None else ""
        parametros = ((producto_id, sucursal_id) if sucursal_id is not None
                      else (producto_id,))
        return self.db.consultar_uno(
            f"""SELECT 1 FROM detalle_bulto db
               JOIN bulto b ON b.id=db.bulto_id
               JOIN remito r ON r.id=b.remito_id
               JOIN orden_reposicion o ON o.id=r.orden_id
               WHERE db.producto_id=? {filtro_sucursal}
                 AND b.estado IN ('EN_TRANSITO', 'RECIBIDO')
               LIMIT 1""",
            parametros,
        ) is not None

    def _codigo_duplicado(self, cx, codigo, excluir_id=None):
        filas = cx.execute(
            'SELECT id, codigo FROM producto WHERE id != COALESCE(?, -1)',
            (excluir_id,),
        ).fetchall()
        codigo_normalizado = normalizar_codigo(codigo)
        return any(normalizar_codigo(fila["codigo"]) == codigo_normalizado for fila in filas)

    def stock_activo(self, producto_id):
        return self.db.consultar_uno(
            """SELECT COALESCE(SUM(disponible), 0) AS disponible,
                      COALESCE(SUM(reservado), 0) AS reservado
               FROM stock WHERE producto_id=?""",
            (producto_id,))