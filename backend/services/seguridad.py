"""Reglas de seguridad compartidas por el registro, la aprobación de empleados
y el cambio de contraseña."""
import re
import secrets

from services.excepciones import ReglaNegocioError

ROLES_LOCAL = ("ADMINISTRADOR", "EMPLEADO")

# Sin caracteres que se confunden al dictarlos o copiarlos (0/O, 1/l/I).
_ALFABETO_TEMPORAL = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
LARGO_PASSWORD_TEMPORAL = 10


def normalizar_email(email):
    email = email.strip().lower() if isinstance(email, str) else ""
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ReglaNegocioError("Ingresá un correo electrónico válido")
    return email


def validar_password(password):
    if not isinstance(password, str) or not 8 <= len(password) <= 128:
        raise ReglaNegocioError("La contraseña debe tener entre 8 y 128 caracteres")
    return password


def validar_rol(rol):
    if rol not in ROLES_LOCAL:
        raise ReglaNegocioError("El rol debe ser ADMINISTRADOR o EMPLEADO")
    return rol


def generar_password_temporal():
    """Contraseña temporal aleatoria. Se usa `secrets` (no `random`) porque es
    criptográficamente segura: no se puede adivinar a partir de otras."""
    return "".join(secrets.choice(_ALFABETO_TEMPORAL)
                   for _ in range(LARGO_PASSWORD_TEMPORAL))
