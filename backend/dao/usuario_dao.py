from database.conexion import BaseDeDatos


class UsuarioDAO:
    """Acceso a datos para la administración de usuarios de un local
    (equipo, aprobación de empleados y panel del administrador)."""

    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    # ---------- alta ----------
    def crear(self, email, password_hash, sucursal_id, rol, estado,
              debe_cambiar_password, aprobado_por_usuario_id=None, cx=None):
        """Inserta un usuario. Si recibe `cx` (una transacción ya abierta, por ejemplo
        la que crea el local), usa esa misma conexión para que todo sea atómico."""
        sql = """INSERT INTO usuario
                   (email, password_hash, sucursal_id, rol, estado, debe_cambiar_password,
                    aprobado_por_usuario_id, fecha_resolucion)
                 VALUES (?, ?, ?, ?, ?, ?, ?,
                         CASE WHEN ? = 'APROBADO' THEN datetime('now', 'localtime') END)"""
        parametros = (email, password_hash, sucursal_id, rol, estado,
                      int(bool(debe_cambiar_password)), aprobado_por_usuario_id, estado)
        if cx is not None:
            return cx.execute(sql, parametros).lastrowid
        with self.db.transaccion():
            return self.db.ejecutar(sql, parametros)

    def email_existe(self, email, cx=None):
        sql, parametros = "SELECT 1 FROM usuario WHERE email=?", (email,)
        if cx is not None:
            return cx.execute(sql, parametros).fetchone() is not None
        return self.db.consultar_uno(sql, parametros) is not None

    # ---------- consultas ----------
    def obtener(self, usuario_id):
        return self.db.consultar_uno(
            """SELECT u.id, u.email, u.sucursal_id, u.rol, u.estado,
                      u.debe_cambiar_password, u.fecha_alta, u.fecha_resolucion,
                      u.motivo_rechazo, s.tipo AS tipo_sucursal
               FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
               WHERE u.id=?""",
            (usuario_id,))

    def listar_por_sucursal(self, sucursal_id):
        return self.db.consultar(
            """SELECT u.id, u.email, u.rol, u.estado, u.debe_cambiar_password,
                      u.fecha_alta, u.fecha_resolucion, u.motivo_rechazo,
                      a.email AS resuelto_por
               FROM usuario u
               LEFT JOIN usuario a ON a.id = u.aprobado_por_usuario_id
               WHERE u.sucursal_id=?
               ORDER BY CASE u.estado WHEN 'PENDIENTE' THEN 0
                                      WHEN 'APROBADO' THEN 1 ELSE 2 END,
                        u.fecha_alta DESC""",
            (sucursal_id,))

    def locales_sin_administrador(self):
        """Locales activos que no tienen ningún administrador aprobado."""
        return self.db.consultar(
            """SELECT s.id, s.nombre FROM sucursal s
               WHERE s.tipo='LOCAL' AND s.activo=1
                 AND NOT EXISTS (
                     SELECT 1 FROM usuario u
                     WHERE u.sucursal_id = s.id
                       AND u.rol='ADMINISTRADOR' AND u.estado='APROBADO')
               ORDER BY s.id""")

    # ---------- aprobación ----------
    def resolver_pendiente(self, usuario_id, estado, rol, admin_id, motivo=None,
                           password_hash=None):
        """Aprueba o rechaza una cuenta PENDIENTE.
        El WHERE estado='PENDIENTE' evita que dos administradores la resuelvan a la vez
        (igual que el UPDATE optimista de los bultos). Devuelve cuántas filas cambió."""
        with self.db.transaccion():
            return self.db.ejecutar_contando(
                """UPDATE usuario
                   SET estado=?, rol=?, aprobado_por_usuario_id=?, motivo_rechazo=?,
                       fecha_resolucion=datetime('now', 'localtime'),
                       password_hash=COALESCE(?, password_hash),
                       debe_cambiar_password=CASE WHEN ? IS NULL
                                                  THEN debe_cambiar_password ELSE 1 END
                   WHERE id=? AND estado='PENDIENTE'""",
                (estado, rol, admin_id, motivo, password_hash, password_hash, usuario_id))

    # ---------- panel del administrador ----------
    def panel_local(self, sucursal_id):
        """Resumen de todo lo que pasa en el local, en una sola consulta por tema."""
        equipo = self.db.consultar_uno(
            """SELECT
                 SUM(CASE WHEN estado='APROBADO' AND rol='ADMINISTRADOR' THEN 1 ELSE 0 END)
                     AS administradores,
                 SUM(CASE WHEN estado='APROBADO' AND rol='EMPLEADO' THEN 1 ELSE 0 END)
                     AS empleados,
                 SUM(CASE WHEN estado='PENDIENTE' THEN 1 ELSE 0 END) AS pendientes,
                 SUM(CASE WHEN estado='RECHAZADO' THEN 1 ELSE 0 END) AS rechazados
               FROM usuario WHERE sucursal_id=?""",
            (sucursal_id,))
        ventas_hoy = self.db.consultar_uno(
            """SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
               FROM venta
               WHERE sucursal_id=? AND date(fecha) = date('now', 'localtime')""",
            (sucursal_id,))
        ventas_mes = self.db.consultar_uno(
            """SELECT COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total
               FROM venta
               WHERE sucursal_id=?
                 AND strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now', 'localtime')""",
            (sucursal_id,))
        alertas = self.db.consultar_uno(
            """SELECT COUNT(*) AS cantidad FROM alerta_stock
               WHERE sucursal_id=? AND resuelta=0""",
            (sucursal_id,))
        ordenes = self.db.consultar_uno(
            """SELECT COUNT(*) AS cantidad FROM orden_reposicion
               WHERE destino_id=? AND estado <> 'CERRADA'""",
            (sucursal_id,))
        bultos = self.db.consultar_uno(
            """SELECT
                 SUM(CASE WHEN b.estado='EN_TRANSITO' THEN 1 ELSE 0 END) AS en_camino,
                 SUM(CASE WHEN b.estado='RECIBIDO' THEN 1 ELSE 0 END) AS sin_verificar
               FROM bulto b
               JOIN remito r ON r.id = b.remito_id
               JOIN orden_reposicion o ON o.id = r.orden_id
               WHERE o.destino_id=?""",
            (sucursal_id,))
        return {
            "equipo": {clave: equipo[clave] or 0 for clave in
                       ("administradores", "empleados", "pendientes", "rechazados")},
            "ventas_hoy": ventas_hoy,
            "ventas_mes": ventas_mes,
            "alertas_stock": alertas["cantidad"],
            "ordenes_abiertas": ordenes["cantidad"],
            "bultos_en_camino": bultos["en_camino"] or 0,
            "bultos_sin_verificar": bultos["sin_verificar"] or 0,
        }
