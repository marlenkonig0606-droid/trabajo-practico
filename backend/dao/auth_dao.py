from database.conexion import BaseDeDatos

# Columnas que se devuelven al frontend como "usuario de la sesión".
_CAMPOS_SESION = """u.id, u.email, u.sucursal_id, s.nombre AS sucursal, s.tipo,
                    u.rol, u.estado, u.debe_cambiar_password"""


class AuthDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def tipo_sucursal(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT tipo, activo FROM sucursal WHERE id=?", (sucursal_id,))

    def obtener_id_por_email(self, email):
        return self.db.consultar_uno(
            "SELECT id FROM usuario WHERE email=?", (email,))

    def crear_usuario(self, email, password_hash, sucursal_id,
                      rol="EMPLEADO", estado="PENDIENTE"):
        with self.db.transaccion():
            return self.db.ejecutar(
                """INSERT INTO usuario (email, password_hash, sucursal_id, rol, estado)
                   VALUES (?, ?, ?, ?, ?)""",
                (email, password_hash, sucursal_id, rol, estado))

    def obtener_credenciales(self, email):
        """Para el login: trae el hash y el estado aunque la cuenta no esté aprobada,
        así se puede avisar 'pendiente de validación' en vez de 'datos incorrectos'."""
        return self.db.consultar_uno(
            f"""SELECT {_CAMPOS_SESION}, u.password_hash, u.motivo_rechazo
                FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
                WHERE u.email=? AND s.activo=1""",
            (email,))

    def obtener_usuario(self, usuario_id):
        """Usuario de la sesión: solo cuentas APROBADAS de sucursales activas."""
        return self.db.consultar_uno(
            f"""SELECT {_CAMPOS_SESION}
                FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
                WHERE u.id=? AND s.activo=1 AND u.estado='APROBADO'""",
            (usuario_id,))

    def obtener_hash(self, usuario_id):
        return self.db.consultar_uno(
            "SELECT password_hash FROM usuario WHERE id=?", (usuario_id,))

    def actualizar_password(self, usuario_id, password_hash):
        """Guarda la contraseña elegida por el usuario y apaga el cambio obligatorio."""
        with self.db.transaccion():
            return self.db.ejecutar_contando(
                """UPDATE usuario SET password_hash=?, debe_cambiar_password=0
                   WHERE id=?""",
                (password_hash, usuario_id))
