import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from database.conexion import BaseDeDatos
from services.excepciones import ReglaNegocioError


class AuthService:
    def __init__(self):
        self.db = BaseDeDatos()

    def registrar_local(self, email, password, sucursal_id):
        return self._registrar(email, password, sucursal_id, "LOCAL")

    def registrar_cd(self, email, password, sucursal_id):
        return self._registrar(email, password, sucursal_id, "CD")

    def _registrar(self, email, password, sucursal_id, tipo_requerido):
        email = email.strip().lower() if isinstance(email, str) else ""
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ReglaNegocioError("Ingresá un correo electrónico válido")
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ReglaNegocioError(
                "La contraseña debe tener entre 8 y 128 caracteres")
        if isinstance(sucursal_id, bool) or not isinstance(sucursal_id, int) or sucursal_id <= 0:
            raise ReglaNegocioError("Elegí un local válido")

        sucursal = self.db.consultar_uno(
            "SELECT tipo FROM sucursal WHERE id=?", (sucursal_id,))
        if sucursal is None or sucursal["tipo"] != tipo_requerido:
            raise ReglaNegocioError(f"Elegí una sucursal de tipo {tipo_requerido}")
        if self.db.consultar_uno(
                "SELECT id FROM usuario WHERE email=?", (email,)):
            raise ReglaNegocioError("Ya existe una cuenta con ese correo")

        try:
            with self.db.transaccion():
                usuario_id = self.db.ejecutar(
                    """INSERT INTO usuario (email, password_hash, sucursal_id)
                       VALUES (?, ?, ?)""",
                    (email, generate_password_hash(password), sucursal_id),
                )
        except sqlite3.IntegrityError as error:
            if self.db.consultar_uno(
                    "SELECT id FROM usuario WHERE email=?", (email,)):
                raise ReglaNegocioError(
                    "Ya existe una cuenta con ese correo") from error
            raise
        return self.obtener_usuario(usuario_id)

    def autenticar(self, email, password):
        email = email.strip().lower() if isinstance(email, str) else ""
        usuario = self.db.consultar_uno(
            """SELECT u.id, u.email, u.password_hash, u.sucursal_id,
                      s.nombre AS sucursal, s.tipo
               FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
               WHERE u.email=?""",
            (email,),
        )
        if usuario is None or not isinstance(password, str) or not check_password_hash(
                usuario["password_hash"], password):
            return None
        return {
            "id": usuario["id"],
            "email": usuario["email"],
            "sucursal_id": usuario["sucursal_id"],
            "sucursal": usuario["sucursal"],
            "tipo": usuario["tipo"],
        }

    def obtener_usuario(self, usuario_id):
        return self.db.consultar_uno(
            """SELECT u.id, u.email, u.sucursal_id,
                      s.nombre AS sucursal, s.tipo
               FROM usuario u JOIN sucursal s ON s.id = u.sucursal_id
               WHERE u.id=?""",
            (usuario_id,),
        )
