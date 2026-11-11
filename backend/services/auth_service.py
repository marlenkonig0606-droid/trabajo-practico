import re
import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

from dao.auth_dao import AuthDAO
from services.excepciones import ReglaNegocioError


class AuthService:
    def __init__(self):
        self.dao = AuthDAO()

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

        sucursal = self.dao.tipo_sucursal(sucursal_id)
        if sucursal is None or sucursal["tipo"] != tipo_requerido:
            raise ReglaNegocioError(f"Elegí una sucursal de tipo {tipo_requerido}")
        if not sucursal["activo"]:
            raise ReglaNegocioError("No se pueden registrar cuentas en una sucursal inactiva")
        if self.dao.obtener_id_por_email(email):
            raise ReglaNegocioError("Ya existe una cuenta con ese correo")

        try:
            usuario_id = self.dao.crear_usuario(
                email, generate_password_hash(password), sucursal_id)
        except sqlite3.IntegrityError as error:
            if self.dao.obtener_id_por_email(email):
                raise ReglaNegocioError(
                    "Ya existe una cuenta con ese correo") from error
            raise
        return self.obtener_usuario(usuario_id)

    def autenticar(self, email, password):
        email = email.strip().lower() if isinstance(email, str) else ""
        usuario = self.dao.obtener_credenciales(email)
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
        return self.dao.obtener_usuario(usuario_id)

    def obtener_sucursal(self, sucursal_id):
        return self.dao.tipo_sucursal(sucursal_id)
