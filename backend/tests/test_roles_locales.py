"""Roles de local (ADMINISTRADOR / EMPLEADO), aprobación de empleados,
contraseña temporal con cambio obligatorio y administrador automático por local."""
import sqlite3

import pytest

from app import crear_app
from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.usuarios_service import NOMBRE_ARCHIVO_CREDENCIALES, UsuariosService
from tests.ayudas import (
    PASSWORD,
    administrador_del_local,
    entrar_con_temporal,
    registrar_local_aprobado,
)


@pytest.fixture
def app_vacia(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "roles.db"))
    cargar(incluir_demo=False)
    app = crear_app(cargar_demo=False)
    app.config.update(TESTING=True)
    yield app
    BaseDeDatos.reiniciar()


def registrar_pendiente(cliente, email, sucursal_id=2, rol="EMPLEADO"):
    respuesta = cliente.post("/api/auth/register", json={
        "email": email, "password": PASSWORD, "sucursal_id": sucursal_id, "rol": rol})
    assert respuesta.status_code == 201
    return respuesta.get_json()


def test_al_iniciar_cada_local_existente_recibe_un_administrador(app_vacia, tmp_path):
    for local_id in (2, 3):
        admin = BaseDeDatos().consultar_uno(
            "SELECT * FROM usuario WHERE sucursal_id=? AND rol='ADMINISTRADOR'",
            (local_id,))
        assert admin["estado"] == "APROBADO"
        assert admin["debe_cambiar_password"] == 1
    archivo = (tmp_path / NOMBRE_ARCHIVO_CREDENCIALES).read_text(encoding="utf-8")
    assert "admin.local2@cdlocales.local" in archivo
    # Reiniciar el backend no crea administradores repetidos.
    assert UsuariosService().asegurar_administradores() == []


def test_crear_local_crea_su_administrador_con_password_temporal(app_vacia, monkeypatch):
    cd = app_vacia.test_client()
    monkeypatch.setenv("CD_REGISTRATION_CODE", "codigo")
    cd.post("/api/auth/register", json={
        "email": "cd@example.com", "password": PASSWORD, "sucursal_id": 1,
        "codigo_cd": "codigo"})

    creado = cd.post("/api/sucursales", json={
        "nombre": "Local Norte", "direccion": "Calle 1", "tipo": "LOCAL",
        "email_admin": "jefa@norte.com"})
    assert creado.status_code == 201
    administrador = creado.get_json()["administrador"]
    assert administrador["email"] == "jefa@norte.com"
    assert len(administrador["password_temporal"]) >= 8

    # Un CD nuevo NO recibe administrador de local.
    otro_cd = cd.post("/api/sucursales", json={
        "nombre": "CD Sur", "direccion": "Ruta 2", "tipo": "CD"})
    assert "administrador" not in otro_cd.get_json()

    # El administrador entra y está obligado a cambiar la contraseña.
    admin = app_vacia.test_client()
    login = admin.post("/api/auth/login", json={
        "email": "jefa@norte.com", "password": administrador["password_temporal"]})
    assert login.status_code == 200
    assert login.get_json()["rol"] == "ADMINISTRADOR"
    bloqueado = admin.get("/api/local/panel")
    assert bloqueado.status_code == 403
    assert bloqueado.get_json()["codigo"] == "CAMBIO_PASSWORD_OBLIGATORIO"

    entrar_con_temporal(admin, "jefa@norte.com", administrador["password_temporal"])
    assert admin.get("/api/local/panel").status_code == 200


def test_crear_local_y_administrador_es_atomico(app_vacia, monkeypatch):
    cd = app_vacia.test_client()
    monkeypatch.setenv("CD_REGISTRATION_CODE", "codigo")
    cd.post("/api/auth/register", json={
        "email": "cd@example.com", "password": PASSWORD, "sucursal_id": 1,
        "codigo_cd": "codigo"})

    # El correo del administrador ya existe -> falla y el local tampoco se crea.
    fallido = cd.post("/api/sucursales", json={
        "nombre": "Local Duplicado", "direccion": "Calle 2", "tipo": "LOCAL",
        "email_admin": "cd@example.com"})
    assert fallido.status_code == 400
    assert BaseDeDatos().consultar_uno(
        "SELECT id FROM sucursal WHERE nombre='Local Duplicado'") is None


def test_empleado_pendiente_no_puede_entrar_hasta_ser_aprobado(app_vacia):
    empleado = app_vacia.test_client()
    pendiente = registrar_pendiente(empleado, "empleado@example.com")
    assert pendiente["estado"] == "PENDIENTE"
    # El registro no inicia sesión.
    assert empleado.get("/api/ventas").status_code == 401

    login = empleado.post("/api/auth/login", json={
        "email": "empleado@example.com", "password": PASSWORD})
    assert login.status_code == 403
    assert login.get_json()["estado"] == "PENDIENTE"
    assert "validación del administrador" in login.get_json()["error"]

    # El administrador lo ve en su equipo y lo aprueba.
    admin = app_vacia.test_client()
    registrar_local_aprobado(admin, "admin2@example.com", 2)
    equipo = admin.get("/api/local/usuarios").get_json()
    assert any(u["email"] == "empleado@example.com" and u["estado"] == "PENDIENTE"
               for u in equipo)
    aprobado = admin.post(f"/api/local/usuarios/{pendiente['id']}/aprobar", json={})
    assert aprobado.status_code == 200
    temporal = aprobado.get_json()["password_temporal"]

    # Su contraseña original ya no sirve: se reemplazó por la temporal.
    assert empleado.post("/api/auth/login", json={
        "email": "empleado@example.com", "password": PASSWORD}).status_code == 401
    sesion = entrar_con_temporal(empleado, "empleado@example.com", temporal,
                                 nueva="mi-clave-nueva")
    assert sesion["rol"] == "EMPLEADO"
    assert sesion["debe_cambiar_password"] is False
    assert empleado.get("/api/ventas").status_code == 200


def test_empleado_no_ve_reportes_ni_habilita_productos(app_vacia):
    admin = app_vacia.test_client()
    registrar_local_aprobado(admin, "admin2@example.com", 2)
    empleado = app_vacia.test_client()
    registrar_local_aprobado(empleado, "empleado@example.com", 2, rol="EMPLEADO")

    for ruta in ("/api/reportes/resumen", "/api/reportes/ventas",
                 "/api/reportes/mas-vendidos", "/api/local/panel", "/api/local/usuarios"):
        assert empleado.get(ruta).status_code == 403, ruta
        assert admin.get(ruta).status_code == 200, ruta

    habilitar = "/api/sucursales/2/productos/1"
    assert empleado.patch(habilitar, json={"habilitado": False}).status_code == 403
    assert admin.patch(habilitar, json={"habilitado": False}).status_code == 200
    # Lo operativo sí lo puede hacer.
    assert empleado.get("/api/stock/2").status_code == 200
    assert empleado.get("/api/ordenes").status_code == 200


def test_administrador_rechaza_y_no_gestiona_otros_locales(app_vacia):
    pendiente = registrar_pendiente(app_vacia.test_client(), "rechazado@example.com")
    ajeno = registrar_pendiente(app_vacia.test_client(), "ajeno@example.com", sucursal_id=3)
    admin = app_vacia.test_client()
    registrar_local_aprobado(admin, "admin2@example.com", 2)

    assert admin.post(f"/api/local/usuarios/{ajeno['id']}/aprobar",
                      json={}).status_code == 403
    rechazo = admin.post(f"/api/local/usuarios/{pendiente['id']}/rechazar",
                         json={"motivo": "No trabaja en este local"})
    assert rechazo.status_code == 200
    # Ya resuelta: no se puede volver a aprobar.
    assert admin.post(f"/api/local/usuarios/{pendiente['id']}/aprobar",
                      json={}).status_code == 400

    login = app_vacia.test_client().post("/api/auth/login", json={
        "email": "rechazado@example.com", "password": PASSWORD})
    assert login.status_code == 403
    assert login.get_json()["estado"] == "RECHAZADO"
    assert login.get_json()["motivo"] == "No trabaja en este local"


def test_administrador_elige_el_rol_al_aprobar_y_en_el_alta_directa(app_vacia):
    pide_admin = registrar_pendiente(app_vacia.test_client(), "quiere@example.com",
                                     rol="ADMINISTRADOR")
    admin = app_vacia.test_client()
    registrar_local_aprobado(admin, "admin2@example.com", 2)

    aprobado = admin.post(f"/api/local/usuarios/{pide_admin['id']}/aprobar",
                          json={"rol": "EMPLEADO"}).get_json()
    assert aprobado["usuario"]["rol"] == "EMPLEADO"

    alta = admin.post("/api/local/usuarios",
                      json={"email": "nuevo@example.com", "rol": "ADMINISTRADOR"})
    assert alta.status_code == 201
    assert alta.get_json()["usuario"]["rol"] == "ADMINISTRADOR"
    assert alta.get_json()["usuario"]["debe_cambiar_password"] == 1
    assert admin.post("/api/local/usuarios",
                      json={"email": "x@example.com", "rol": "JEFE"}).status_code == 400


def test_cambio_de_password_valida_la_actual_y_la_nueva(app_vacia):
    admin = app_vacia.test_client()
    registrar_local_aprobado(admin, "admin2@example.com", 2)
    incorrecta = admin.post("/api/auth/cambiar-password",
                            json={"actual": "otra-cosa-123", "nueva": "nueva-clave-1"})
    assert incorrecta.status_code == 400
    corta = admin.post("/api/auth/cambiar-password",
                       json={"actual": PASSWORD, "nueva": "corta"})
    assert corta.status_code == 400
    igual = admin.post("/api/auth/cambiar-password",
                       json={"actual": PASSWORD, "nueva": PASSWORD})
    assert igual.status_code == 400


def test_migracion_aprueba_cuentas_existentes_y_elige_un_admin_por_local(tmp_path):
    ruta = str(tmp_path / "usuarios_legacy.db")
    legado = sqlite3.connect(ruta)
    legado.executescript("""
        CREATE TABLE sucursal (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nombre TEXT NOT NULL UNIQUE,
            direccion TEXT, tipo TEXT NOT NULL CHECK (tipo IN ('CD', 'LOCAL')));
        CREATE TABLE usuario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE, password_hash TEXT NOT NULL,
            sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
            fecha_alta TEXT NOT NULL DEFAULT (datetime('now', 'localtime')));
        INSERT INTO sucursal (id, nombre, direccion, tipo) VALUES
            (1, 'CD Central', 'x', 'CD'), (2, 'Local Centro', 'y', 'LOCAL');
        INSERT INTO usuario (email, password_hash, sucursal_id) VALUES
            ('cd@x.com', 'h', 1), ('primero@x.com', 'h', 2), ('segundo@x.com', 'h', 2);
    """)
    legado.commit()
    legado.close()

    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        filas = {f["email"]: f for f in db.consultar(
            "SELECT email, rol, estado FROM usuario")}
        assert all(f["estado"] == "APROBADO" for f in filas.values())
        assert filas["cd@x.com"]["rol"] == "ADMINISTRADOR"
        assert filas["primero@x.com"]["rol"] == "ADMINISTRADOR"
        assert filas["segundo@x.com"]["rol"] == "EMPLEADO"
        # Como el local ya tiene administrador, al iniciar no se crea otro.
        cargar(incluir_demo=False)
        assert administrador_del_local(2) is not None
        creados = UsuariosService().asegurar_administradores()
        assert "Local Centro" not in [c["local"] for c in creados]
    finally:
        BaseDeDatos.reiniciar()
