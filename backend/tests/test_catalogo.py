import pytest

from app import crear_app
from database.conexion import BaseDeDatos
from models.categoria import Categoria
from models.proveedor import Proveedor


@pytest.fixture
def cliente(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "catalogo.db"))
    app = crear_app()
    app.config.update(TESTING=True)
    yield app.test_client()
    BaseDeDatos.reiniciar()


def test_modelos_de_dominio_serializan_entidades():
    categoria = Categoria.desde_fila({"id": 10, "nombre": "Limpieza"})
    proveedor = Proveedor.desde_fila({
        "id": 20,
        "cuit": "30-11111111-2",
        "razon_social": "Proveedor Demo",
    })

    assert categoria.to_dict() == {"id": 10, "nombre": "Limpieza"}
    assert proveedor.to_dict() == {
        "id": 20,
        "cuit": "30-11111111-2",
        "razon_social": "Proveedor Demo",
    }


def test_abmc_categoria(cliente):
    creada = cliente.post("/api/categorias", json={"nombre": "Limpieza"})
    assert creada.status_code == 201
    categoria_id = creada.get_json()["id"]
    assert cliente.get(f"/api/categorias/{categoria_id}").get_json()["nombre"] == "Limpieza"

    actualizada = cliente.put(
        f"/api/categorias/{categoria_id}", json={"nombre": "Higiene"}
    )
    assert actualizada.status_code == 200
    assert actualizada.get_json()["nombre"] == "Higiene"

    parcial = cliente.patch(
        f"/api/categorias/{categoria_id}", json={"nombre": "Cuidado personal"}
    )
    assert parcial.status_code == 200
    assert any(
        item["id"] == categoria_id
        for item in cliente.get("/api/categorias").get_json()
    )

    assert cliente.delete(f"/api/categorias/{categoria_id}").status_code == 200
    assert cliente.get(f"/api/categorias/{categoria_id}").status_code == 404


def test_abmc_proveedor(cliente):
    creado = cliente.post(
        "/api/proveedores",
        json={"cuit": "30-11111111-2", "razon_social": "Proveedor Demo"},
    )
    assert creado.status_code == 201
    proveedor_id = creado.get_json()["id"]
    assert cliente.get(f"/api/proveedores/{proveedor_id}").get_json()["cuit"] == \
        "30-11111111-2"

    actualizado = cliente.put(
        f"/api/proveedores/{proveedor_id}",
        json={"cuit": "30-22222222-3", "razon_social": "Proveedor Actualizado"},
    )
    assert actualizado.status_code == 200
    assert actualizado.get_json()["razon_social"] == "Proveedor Actualizado"

    parcial = cliente.patch(
        f"/api/proveedores/{proveedor_id}",
        json={"razon_social": "Nombre parcial"},
    )
    assert parcial.status_code == 200
    assert any(
        item["id"] == proveedor_id
        for item in cliente.get("/api/proveedores").get_json()
    )

    assert cliente.delete(f"/api/proveedores/{proveedor_id}").status_code == 200
    assert cliente.get(f"/api/proveedores/{proveedor_id}").status_code == 404


def test_service_rechaza_nombres_y_cuit_duplicados(cliente):
    duplicada = cliente.post("/api/categorias", json={"nombre": "Bebidas"})
    assert duplicada.status_code == 400
    assert "Ya existe" in duplicada.get_json()["error"]

    proveedor = {"cuit": "30-12345678-9", "razon_social": "Otro proveedor"}
    duplicado = cliente.post("/api/proveedores", json=proveedor)
    assert duplicado.status_code == 400
    assert "CUIT" in duplicado.get_json()["error"]


def test_update_rechaza_cuit_duplicado_y_permite_conservarlo(cliente):
    primero = cliente.post("/api/proveedores", json={
        "cuit": "30-11111111-2",
        "razon_social": "Primero",
    }).get_json()
    segundo = cliente.post("/api/proveedores", json={
        "cuit": "30-22222222-3",
        "razon_social": "Segundo",
    }).get_json()

    duplicado = cliente.patch(
        f"/api/proveedores/{segundo['id']}",
        json={"cuit": primero["cuit"]},
    )
    assert duplicado.status_code == 400

    sin_cambio_de_cuit = cliente.patch(
        f"/api/proveedores/{primero['id']}",
        json={"razon_social": "Nombre actualizado"},
    )
    assert sin_cambio_de_cuit.status_code == 200


def test_no_elimina_categoria_ni_proveedor_en_uso(cliente):
    categoria = cliente.delete("/api/categorias/1")
    assert categoria.status_code == 400
    assert "productos asociados" in categoria.get_json()["error"]

    proveedor = cliente.delete("/api/proveedores/1")
    assert proveedor.status_code == 400
    assert "productos asociados" in proveedor.get_json()["error"]
