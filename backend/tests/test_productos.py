import pytest

from app import crear_app
from database.conexion import BaseDeDatos


@pytest.fixture
def cliente(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "productos.db"))
    app = crear_app()
    app.config.update(TESTING=True)
    yield app.test_client()
    BaseDeDatos.reiniciar()


def producto(**cambios):
    datos = {
        "codigo": "TEST-001",
        "nombre": "Producto de prueba",
        "categoria_id": 1,
        "proveedor_id": None,
        "precio_costo": 10.5,
        "precio_venta": 20,
        "stock_minimo": 3,
    }
    datos.update(cambios)
    return datos


def test_abmc_producto(cliente):
    creado = cliente.post("/api/productos", json=producto())
    assert creado.status_code == 201
    datos = creado.get_json()
    producto_id = datos["id"]
    assert datos["codigo"] == "TEST-001"

    consulta = cliente.get(f"/api/productos/{producto_id}")
    assert consulta.status_code == 200
    assert consulta.get_json()["nombre"] == "Producto de prueba"

    actualizado = cliente.put(
        f"/api/productos/{producto_id}",
        json=producto(nombre="Producto actualizado"),
    )
    assert actualizado.status_code == 200
    assert actualizado.get_json()["nombre"] == "Producto actualizado"

    eliminado = cliente.delete(f"/api/productos/{producto_id}")
    assert eliminado.status_code == 200
    assert cliente.get(f"/api/productos/{producto_id}").status_code == 404


def test_edicion_parcial_y_listado(cliente):
    creado = cliente.post("/api/productos", json=producto())
    producto_id = creado.get_json()["id"]

    actualizado = cliente.patch(
        f"/api/productos/{producto_id}",
        json={"nombre": "Nombre parcial"},
    )
    assert actualizado.status_code == 200
    assert actualizado.get_json()["codigo"] == "TEST-001"
    assert actualizado.get_json()["nombre"] == "Nombre parcial"
    assert any(
        item["id"] == producto_id
        for item in cliente.get("/api/productos").get_json()
    )


def test_rechaza_codigo_duplicado_y_datos_invalidos(cliente):
    assert cliente.post("/api/productos", json=producto()).status_code == 201
    duplicado = cliente.post(
        "/api/productos",
        json=producto(codigo=" BEB-001 "),
    )
    assert duplicado.status_code == 400
    assert "código" in duplicado.get_json()["error"]

    invalido = cliente.post("/api/productos", json=producto(precio_venta=-1))
    assert invalido.status_code == 400


def test_no_elimina_producto_con_stock_asociado(cliente):
    respuesta = cliente.delete("/api/productos/1")
    assert respuesta.status_code == 400
    assert "stock" in respuesta.get_json()["error"]
