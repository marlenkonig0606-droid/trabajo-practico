import sqlite3
from werkzeug.security import check_password_hash, generate_password_hash

from dao.auth_dao import AuthDAO
from services.excepciones import CuentaNoHabilitadaError, ReglaNegocioError
from services.seguridad import normalizar_email, validar_password, validar_rol


class AuthService:
    def __init__(self):
        self.dao = AuthDAO()

    def registrar_local(self, email, password, sucursal_id, rol="EMPLEADO"):
        """Un usuario de local se registra PENDIENTE: no puede entrar hasta que el
        administrador de su local lo valide. Puede pedir rol EMPLEADO o ADMINISTRADOR;
        el administrador decide al aprobarlo."""
        return self._registrar(email, password, sucursal_id, "LOCAL",
                               rol=validar_rol(rol), estado="PENDIENTE")

    def registrar_cd(self, email, password, sucursal_id):
        # El CD ya está protegido por el código de invitación: queda aprobado.
        return self._registrar(email, password, sucursal_id, "CD",
                               rol="ADMINISTRADOR", estado="APROBADO")

    def _registrar(self, email, password, sucursal_id, tipo_requerido, rol, estado):
        email = normalizar_email(email)
        validar_password(password)
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
                email, generate_password_hash(password), sucursal_id, rol, estado)
        except sqlite3.IntegrityError as error:
            if self.dao.obtener_id_por_email(email):
                raise ReglaNegocioError(
                    "Ya existe una cuenta con ese correo") from error
            raise
        if estado != "APROBADO":
            return {"id": usuario_id, "email": email, "rol": rol, "estado": estado}
        return self.obtener_usuario(usuario_id)

    def autenticar(self, email, password):
        """Devuelve el usuario si puede entrar, None si las credenciales son incorrectas,
        o lanza CuentaNoHabilitadaError si la cuenta está pendiente o rechazada."""
        email = email.strip().lower() if isinstance(email, str) else ""
        usuario = self.dao.obtener_credenciales(email)
        if usuario is None or not isinstance(password, str) or not check_password_hash(
                usuario["password_hash"], password):
            return None
        # Recién después de validar la contraseña se informa el estado:
        # así nadie puede averiguar qué correos están registrados.
        if usuario["estado"] == "PENDIENTE":
            raise CuentaNoHabilitadaError(
                "Tu cuenta está esperando la validación del administrador de tu local. "
                "Cuando la apruebe, te va a dar una contraseña temporal para entrar.",
                "PENDIENTE")
        if usuario["estado"] == "RECHAZADO":
            raise CuentaNoHabilitadaError(
                "El administrador de tu local rechazó esta cuenta.",
                "RECHAZADO", usuario["motivo_rechazo"])
        return self._a_sesion(usuario)

    def cambiar_password(self, usuario_id, actual, nueva):
        """Cambio de contraseña (obligatorio si la cuenta tiene una temporal)."""
        validar_password(nueva)
        guardado = self.dao.obtener_hash(usuario_id)
        if guardado is None:
            raise ReglaNegocioError("La cuenta no existe")
        if not isinstance(actual, str) or not check_password_hash(
                guardado["password_hash"], actual):
            raise ReglaNegocioError("La contraseña actual no es correcta")
        if actual == nueva:
            raise ReglaNegocioError("La contraseña nueva tiene que ser distinta de la actual")
        self.dao.actualizar_password(usuario_id, generate_password_hash(nueva))
        return self.obtener_usuario(usuario_id)

    def obtener_usuario(self, usuario_id):
        usuario = self.dao.obtener_usuario(usuario_id)
        return self._a_sesion(usuario) if usuario else None

    def obtener_sucursal(self, sucursal_id):
        return self.dao.tipo_sucursal(sucursal_id)

    @staticmethod
    def _a_sesion(fila):
        return {
            "id": fila["id"],
            "email": fila["email"],
            "sucursal_id": fila["sucursal_id"],
            "sucursal": fila["sucursal"],
            "tipo": fila["tipo"],
            "rol": fila["rol"],
            "debe_cambiar_password": bool(fila["debe_cambiar_password"]),
        }
