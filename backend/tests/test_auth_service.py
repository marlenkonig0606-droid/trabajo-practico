import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.auth_service import AuthService
from services.excepciones import ReglaNegocioError


def test_registro_local_guarda_hash_y_persiste_tras_reabrir_db(tmp_path):
    ruta = str(tmp_path / "auth.db")
    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        cargar()
        servicio = AuthService()
        usuario = servicio.registrar_local(
            "LOCAL@EXAMPLE.COM", "contraseña-segura", 2)

        guardado = db.consultar_uno(
            "SELECT email, password_hash FROM usuario WHERE id=?",
            (usuario["id"],),
        )
        assert guardado["email"] == "local@example.com"
        assert guardado["password_hash"] != "contraseña-segura"

        BaseDeDatos.reiniciar()
        BaseDeDatos(ruta)
        autenticado = AuthService().autenticar(
            "local@example.com", "contraseña-segura")
        assert autenticado["sucursal_id"] == 2
    finally:
        BaseDeDatos.reiniciar()


def test_registro_no_permite_asignar_tipo_de_sucursal_incorrecto(tmp_path):
    BaseDeDatos.reiniciar()
    try:
        BaseDeDatos(str(tmp_path / "auth_roles.db"))
        cargar()
        servicio = AuthService()

        with pytest.raises(ReglaNegocioError, match="tipo LOCAL"):
            servicio.registrar_local("cd@example.com", "contraseña-segura", 1)
    finally:
        BaseDeDatos.reiniciar()
