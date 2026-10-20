import pytest

from app import crear_app
from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar


@pytest.fixture
def cliente_api(tmp_path):
    BaseDeDatos.reiniciar()
    db = BaseDeDatos(str(tmp_path / "ventas_api.db"))
    cargar()
    with db.transaccion():
        db.ejecutar(
            "INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (2, 1, 5)"
        )
    app = crear_app()
    app.config.update(TESTING=True)
    cliente = app.test_client()
    respuesta = cliente.post(
        "/api/auth/register",
        json={
            "email": "local@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 2,
        },
    )
    assert respuesta.status_code == 201
    yield cliente
    BaseDeDatos.reiniciar()


def test_api_registra_lista_y_consulta_venta(cliente_api):
    respuesta = cliente_api.post(
        "/api/ventas",
        json={
            "sucursal_id": 2,
            "items": [{"producto_id": 1, "cantidad": 2}],
            "medio_pago": "EFECTIVO",
            "referencia": "caja 1",
        },
    )

    assert respuesta.status_code == 201
    venta = respuesta.get_json()
    assert venta["total"] == 1260
    assert venta["comprobante_numero"] == 1

    listado = cliente_api.get("/api/ventas")
    assert listado.status_code == 200
    assert listado.get_json()[0]["id"] == venta["id"]
    assert listado.get_json()[0]["sucursal"] == "Local Centro"

    detalle = cliente_api.get(f"/api/ventas/{venta['id']}")
    assert detalle.status_code == 200
    assert detalle.get_json()["items"] == [{
        "producto_id": 1,
        "nombre": "Agua 1.5L",
        "cantidad": 2,
        "precio_unitario": 700,
    }]
    assert detalle.get_json()["devoluciones"] == []


def test_api_registra_devolucion_y_refleja_en_detalle(cliente_api):
    venta = cliente_api.post(
        "/api/ventas",
        json={
            "sucursal_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
            "medio_pago": "TARJETA_DEBITO",
        },
    ).get_json()

    respuesta = cliente_api.post(
        "/api/devoluciones",
        json={
            "venta_id": venta["id"],
            "items": [{"producto_id": 1, "cantidad": 1}],
            "motivo": "Producto defectuoso",
        },
    )

    assert respuesta.status_code == 201
    assert respuesta.get_json()["total"] == 700
    detalle = cliente_api.get(f"/api/ventas/{venta['id']}").get_json()
    assert detalle["devoluciones"][0]["motivo"] == "Producto defectuoso"


@pytest.mark.parametrize(
    ("payload", "error"),
    [
        (None, "objeto JSON"),
        ({"sucursal_id": "2", "items": [], "medio_pago": "EFECTIVO"},
         "sucursal_id debe ser un entero positivo"),
        ({"sucursal_id": 2, "items": [], "medio_pago": ""},
         "medio_pago es obligatorio"),
    ],
)
def test_api_rechaza_solicitudes_de_venta_invalidas(cliente_api, payload, error):
    respuesta = cliente_api.post("/api/ventas", json=payload)

    assert respuesta.status_code == 400
    assert error in respuesta.get_json()["error"]


def test_api_venta_inexistente_devuelve_404(cliente_api):
    respuesta = cliente_api.get("/api/ventas/999")

    assert respuesta.status_code == 404


def test_api_registro_cd_exige_codigo_de_invitacion(cliente_api, monkeypatch):
    cliente_api.post("/api/auth/logout")
    monkeypatch.setenv("CD_REGISTRATION_CODE", "marlufa")
    datos = {
        "email": "cd@example.com",
        "password": "contraseña-segura",
        "sucursal_id": 1,
    }
    incorrecto = cliente_api.post(
        "/api/auth/register",
        json={**datos, "codigo_cd": "incorrecto"},
    )
    assert incorrecto.status_code == 400

    correcto = cliente_api.post(
        "/api/auth/register",
        json={**datos, "codigo_cd": "marlufa"},
    )
    assert correcto.status_code == 201
    assert correcto.get_json()["tipo"] == "CD"


def test_api_explica_como_habilitar_registro_cd(cliente_api, monkeypatch):
    monkeypatch.delenv("CD_REGISTRATION_CODE", raising=False)
    cliente_api.post("/api/auth/logout")

    respuesta = cliente_api.post(
        "/api/auth/register",
        json={
            "email": "cd@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 1,
            "codigo_cd": "marlufa",
        },
    )

    assert respuesta.status_code == 400
    assert "reiniciá el backend" in respuesta.get_json()["error"]


def test_api_sucursal_local_no_puede_consultar_otra_sucursal(cliente_api):
    respuesta = cliente_api.get("/api/stock/3")

    assert respuesta.status_code == 403


def test_api_exige_sesion_para_datos_de_negocio(cliente_api):
    cliente_api.post("/api/auth/logout")

    respuesta = cliente_api.get("/api/ventas")

    assert respuesta.status_code == 401


def test_api_local_puede_listar_sucursales_para_solicitar_reposicion(cliente_api):
    sucursales = cliente_api.get("/api/sucursales").get_json()
    assert [s["tipo"] for s in sucursales] == ["CD", "LOCAL", "LOCAL"]


def test_local_solicita_reposicion_a_cualquier_local_y_ve_sus_ordenes(cliente_api):
    solicitud = cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 3}],
        },
    )
    assert solicitud.status_code == 201
    orden = solicitud.get_json()
    assert orden["destino_id"] == 2
    assert [orden_publica["id"] for orden_publica in
            cliente_api.get("/api/ordenes").get_json()] == [orden["id"]]

    otra_sucursal = crear_app().test_client()
    assert otra_sucursal.post(
        "/api/auth/register",
        json={
            "email": "otro-local@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 3,
        },
    ).status_code == 201
    orden_forzada = otra_sucursal.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
        },
    )
    assert orden_forzada.status_code == 201
    ordenes_local_3 = otra_sucursal.get("/api/ordenes").get_json()
    assert [o["id"] for o in ordenes_local_3] == [orden_forzada.get_json()["id"]]
    ordenes_local_2 = cliente_api.get("/api/ordenes").get_json()
    assert {o["id"] for o in ordenes_local_2} == {
        orden["id"], orden_forzada.get_json()["id"],
    }


def test_local_solicita_a_cualquier_cd_y_cd_no_puede_crear_orden(cliente_api, monkeypatch):
    db = BaseDeDatos()
    with db.transaccion():
        segundo_cd = db.ejecutar(
            "INSERT INTO sucursal (nombre, tipo) VALUES ('CD Secundario', 'CD')")
        segundo_local = db.ejecutar(
            "INSERT INTO sucursal (nombre, tipo) VALUES ('Local Norte', 'LOCAL')")

    solicitud = cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": segundo_cd,
            "destino_id": segundo_local,
            "items": [{"producto_id": 1, "cantidad": 2}],
        },
    )
    assert solicitud.status_code == 201
    assert solicitud.get_json()["origen_id"] == segundo_cd
    assert solicitud.get_json()["destino_id"] == segundo_local

    monkeypatch.setenv("CD_REGISTRATION_CODE", "marlufa")
    cd = crear_app().test_client()
    assert cd.post(
        "/api/auth/register",
        json={
            "email": "cd-operador@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 1,
            "codigo_cd": "marlufa",
        },
    ).status_code == 201
    respuesta_cd = cd.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
        },
    )
    assert respuesta_cd.status_code == 403


def test_flujo_api_cd_despacha_local_verifica_y_actualiza_stock(cliente_api, monkeypatch):
    monkeypatch.setenv("CD_REGISTRATION_CODE", "marlufa")
    cd = crear_app().test_client()
    alta_cd = cd.post(
        "/api/auth/register",
        json={
            "email": "cd-operador@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 1,
            "codigo_cd": "marlufa",
        },
    )
    assert alta_cd.status_code == 201

    orden_cd = cd.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
        },
    )
    assert orden_cd.status_code == 403

    orden = cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 3}],
        },
    ).get_json()
    bulto = cd.post(
        f"/api/ordenes/{orden['id']}/bultos",
        json={"items": [{"producto_id": 1, "cantidad": 3}]},
    ).get_json()
    precintado = cd.post(
        f"/api/bultos/{bulto['id']}/precintar", json={})
    assert precintado.status_code == 200
    precinto = precintado.get_json()["precinto"]
    assert precinto.startswith("P-")
    assert cd.post(f"/api/bultos/{bulto['id']}/despachar").status_code == 200
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5

    verificacion_anticipada = cliente_api.post(
        f"/api/bultos/{bulto['id']}/verificar",
        json={
            "remito": f"R-{orden['id']:06d}",
            "precinto": precinto,
            "intacto": True,
        },
    )
    assert verificacion_anticipada.status_code == 400
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5

    recepcion_desde_cd = cd.post(
        f"/api/bultos/{bulto['id']}/recibir",
        json={},
    )
    assert recepcion_desde_cd.status_code == 403
    verificacion_desde_cd = cd.post(
        f"/api/bultos/{bulto['id']}/verificar",
        json={
            "remito": f"R-{orden['id']:06d}",
            "precinto": precinto,
            "intacto": True,
        },
    )
    assert verificacion_desde_cd.status_code == 403
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5

    recepcion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/recibir",
        json={},
    )
    assert recepcion.status_code == 200
    assert recepcion.get_json()["estado"] == "RECIBIDO"
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5
    verificacion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/verificar",
        json={
            "remito": f"R-{orden['id']:06d}",
            "precinto": precinto,
            "intacto": True,
        },
    )
    assert verificacion.status_code == 200
    assert verificacion.get_json()["estado"] == "VERIFICADO"
    agua_stock = cliente_api.get("/api/stock/2").get_json()[0]
    assert agua_stock["disponible"] == 8
    assert agua_stock["precio_venta"] == 700
    orden_actualizada = cliente_api.get("/api/ordenes").get_json()[0]
    assert orden_actualizada["remito_estado"] == "VERIFICADO"


def test_local_rechaza_bulto_si_precinto_roto_sin_sumar_stock(cliente_api, monkeypatch):
    monkeypatch.setenv("CD_REGISTRATION_CODE", "marlufa")
    cd = crear_app().test_client()
    cd.post(
        "/api/auth/register",
        json={
            "email": "cd-operador@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 1,
            "codigo_cd": "marlufa",
        },
    )
    orden = cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 3}],
        },
    ).get_json()
    bulto = cd.post(
        f"/api/ordenes/{orden['id']}/bultos",
        json={"items": [{"producto_id": 1, "cantidad": 3}]},
    ).get_json()
    precinto = cd.post(
        f"/api/bultos/{bulto['id']}/precintar", json={}).get_json()["precinto"]
    cd.post(f"/api/bultos/{bulto['id']}/despachar")

    recepcion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/recibir",
        json={},
    )
    assert recepcion.status_code == 200
    assert recepcion.get_json()["estado"] == "RECIBIDO"
    verificacion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/verificar",
        json={
            "remito": f"R-{orden['id']:06d}",
            "precinto": precinto,
            "intacto": False,
        },
    )

    assert verificacion.status_code == 200
    assert verificacion.get_json()["estado"] == "RECHAZADO"
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5


def test_local_rechaza_remito_incorrecto_y_no_suma_stock(cliente_api, monkeypatch):
    monkeypatch.setenv("CD_REGISTRATION_CODE", "marlufa")
    cd = crear_app().test_client()
    assert cd.post(
        "/api/auth/register",
        json={
            "email": "cd-operador@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 1,
            "codigo_cd": "marlufa",
        },
    ).status_code == 201
    orden = cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 3}],
        },
    ).get_json()
    bulto = cd.post(
        f"/api/ordenes/{orden['id']}/bultos",
        json={"items": [{"producto_id": 1, "cantidad": 3}]},
    ).get_json()
    precinto = cd.post(
        f"/api/bultos/{bulto['id']}/precintar", json={}).get_json()["precinto"]
    cd.post(f"/api/bultos/{bulto['id']}/despachar")

    recepcion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/recibir",
        json={},
    )
    assert recepcion.status_code == 200
    verificacion = cliente_api.post(
        f"/api/bultos/{bulto['id']}/verificar",
        json={
            "remito": "R-INCORRECTO",
            "precinto": precinto,
            "intacto": True,
        },
    )

    assert verificacion.status_code == 200
    assert verificacion.get_json()["estado"] == "RECHAZADO"
    assert cliente_api.get("/api/stock/2").get_json()[0]["disponible"] == 5


def test_local_no_consulta_ventas_ni_reportes_de_otro_local(cliente_api):
    venta = cliente_api.post(
        "/api/ventas",
        json={
            "sucursal_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
            "medio_pago": "EFECTIVO",
        },
    )
    assert venta.status_code == 201
    assert cliente_api.post(
        "/api/ordenes",
        json={
            "origen_id": 1,
            "destino_id": 2,
            "items": [{"producto_id": 1, "cantidad": 1}],
        },
    ).status_code == 201

    otra_sucursal = crear_app().test_client()
    registro = otra_sucursal.post(
        "/api/auth/register",
        json={
            "email": "otro-local@example.com",
            "password": "contraseña-segura",
            "sucursal_id": 3,
        },
    )
    assert registro.status_code == 201
    assert otra_sucursal.get("/api/ventas").get_json() == []
    assert otra_sucursal.get("/api/reportes/ventas").get_json() == []
    assert otra_sucursal.get("/api/reportes/mas-vendidos").get_json() == []
    assert {
        fila["sucursal"]
        for fila in otra_sucursal.get("/api/reportes/existencias").get_json()
    } == {"Local Nueva Córdoba"}
    assert otra_sucursal.get("/api/ordenes").get_json() == []


def test_cuenta_cd_se_crea_fuera_del_registro_publico_y_tiene_acceso_global(tmp_path):
    from services.auth_service import AuthService

    BaseDeDatos.reiniciar()
    try:
        BaseDeDatos(str(tmp_path / "cuenta_cd.db"))
        cargar()
        AuthService().registrar_cd("cd@example.com", "contraseña-segura", 1)
        cliente = crear_app().test_client()
        respuesta = cliente.post(
            "/api/auth/login",
            json={"email": "cd@example.com", "password": "contraseña-segura"},
        )

        assert respuesta.status_code == 200
        assert respuesta.get_json()["tipo"] == "CD"
        assert len(cliente.get("/api/sucursales").get_json()) == 3
        assert cliente.get("/api/ordenes").status_code == 200
    finally:
        BaseDeDatos.reiniciar()
