"""Ayudas para los tests de la API: registrar un usuario de local y dejarlo
operativo recorriendo el flujo real (pendiente -> aprobado -> contraseña temporal
-> cambio obligatorio)."""
from database.conexion import BaseDeDatos
from services.usuarios_service import UsuariosService

PASSWORD = "contraseña-segura"


def administrador_del_local(sucursal_id):
    return BaseDeDatos().consultar_uno(
        """SELECT id, sucursal_id FROM usuario
           WHERE sucursal_id=? AND rol='ADMINISTRADOR' AND estado='APROBADO'
           ORDER BY id LIMIT 1""",
        (sucursal_id,))


def entrar_con_temporal(cliente, email, password_temporal, nueva=PASSWORD):
    """Inicia sesión con la contraseña temporal y la cambia (paso obligatorio)."""
    login = cliente.post("/api/auth/login",
                         json={"email": email, "password": password_temporal})
    assert login.status_code == 200, login.get_json()
    assert login.get_json()["debe_cambiar_password"] is True
    cambio = cliente.post("/api/auth/cambiar-password",
                          json={"actual": password_temporal, "nueva": nueva})
    assert cambio.status_code == 200, cambio.get_json()
    return cambio.get_json()


def registrar_local_aprobado(cliente, email, sucursal_id, rol="ADMINISTRADOR"):
    """Registra un usuario de local, lo aprueba el administrador del local
    y entra cambiando la contraseña temporal. Deja la sesión iniciada."""
    cliente.post("/api/auth/logout")
    registro = cliente.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "sucursal_id": sucursal_id, "rol": rol,
    })
    assert registro.status_code == 201, registro.get_json()
    assert registro.get_json()["pendiente"] is True
    admin = administrador_del_local(sucursal_id)
    resultado = UsuariosService().aprobar(admin, registro.get_json()["id"])
    return entrar_con_temporal(cliente, email, resultado["password_temporal"])
