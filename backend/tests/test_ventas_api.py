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
    yield app.test_client()
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
