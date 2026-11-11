from database.conexion import BaseDeDatos


class AuthDAO:
    def __init__(self, db=None):
        self.db = db if db is not None else BaseDeDatos()

    def tipo_sucursal(self, sucursal_id):
        return self.db.consultar_uno(
            "SELECT tipo FROM sucursal WHERE id=?", (sucursal_id,))

    def obtener_id_por_email(self, email):
        return self.db.consultar_uno(
            "SELECT id FROM usuario WHERE email=?", (email,))

    def crear_usuario(self, email, password_hash, sucursal_id):
        with self.db.transaccion():
            return self.db.ejecutar(
                """INSERT INTO usuario (email, password_hash, sucursal_id)
                   VALUES (?, ?, ?)""",
                (email, password_hash, sucursal_id))

    def obtener_credenciales(self, email):
        return self.db.consultar_uno(
            """SELECT u.id, u.email, u.password_hash, u.sucursal_id,
                      s.nombre AS sucursal, s.tipo
               FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
               WHERE u.email=?""",
            (email,))

    def obtener_usuario(self, usuario_id):
        return self.db.consultar_uno(
            """SELECT u.id, u.email, u.sucursal_id,
                      s.nombre AS sucursal, s.tipo
               FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
               WHERE u.id=?""",
            (usuario_id,))
