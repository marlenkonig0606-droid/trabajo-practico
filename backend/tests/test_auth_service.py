import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.auth_service import AuthService
from services.excepciones import CuentaNoHabilitadaError, ReglaNegocioError
from services.catalogo_service import CatalogoService


def db_usuario(ruta, email):
    return BaseDeDatos(ruta).consultar_uno(
        "SELECT rol, estado FROM usuario WHERE email=?", (email,))


def test_registro_local_guarda_hash_y_persiste_tras_reabrir_db(tmp_path):
    ruta = str(tmp_path / "auth.db")
    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        cargar(incluir_demo=False)
        servicio = AuthService()
        usuario = servicio.registrar_local(
            "LOCAL@EXAMPLE.COM", "contraseña-segura", 2)

        guardado = db.consultar_uno(
            "SELECT email, password_hash FROM usuario WHERE id=?",
            (usuario["id"],),
        )
        assert guardado["email"] == "local@example.com"
        assert guardado["password_hash"] != "contraseña-segura"

        # Queda pendiente: con la contraseña correcta igual no puede entrar.
        with pytest.raises(CuentaNoHabilitadaError) as pendiente:
            servicio.autenticar("local@example.com", "contraseña-segura")
        assert pendiente.value.estado == "PENDIENTE"

        BaseDeDatos.reiniciar()
        BaseDeDatos(ruta)
        assert db_usuario(ruta, "local@example.com")["estado"] == "PENDIENTE"
    finally:
        BaseDeDatos.reiniciar()


def test_registro_no_permite_asignar_tipo_de_sucursal_incorrecto(tmp_path):
    BaseDeDatos.reiniciar()
    try:
        BaseDeDatos(str(tmp_path / "auth_roles.db"))
        cargar(incluir_demo=False)
        servicio = AuthService()

        with pytest.raises(ReglaNegocioError, match="tipo LOCAL"):
            servicio.registrar_local("cd@example.com", "contraseña-segura", 1)
    finally:
        BaseDeDatos.reiniciar()


def test_sucursal_inactiva_no_acepta_cuentas_ni_autenticacion(tmp_path):
    BaseDeDatos.reiniciar()
    try:
        BaseDeDatos(str(tmp_path / "auth_sucursal_inactiva.db"))
        cargar(incluir_demo=False)
        auth = AuthService()
        auth.registrar_local("local@example.com", "contraseña-segura", 2)

        CatalogoService().cambiar_estado_sucursal(2, False)

        with pytest.raises(ReglaNegocioError, match="sucursal inactiva"):
            auth.registrar_local("otro@example.com", "contraseña-segura", 2)
        assert auth.autenticar("local@example.com", "contraseña-segura") is None
    finally:
        BaseDeDatos.reiniciar()
