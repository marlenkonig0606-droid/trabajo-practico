import pytest

from database.conexion import BaseDeDatos
from services.catalogo_service import CatalogoService
from services.excepciones import ReglaNegocioError


@pytest.fixture
def catalogo(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "catalogo.db"))
    yield CatalogoService()
    BaseDeDatos.reiniciar()


def test_catalogo_usa_las_operaciones_de_los_dao(catalogo):
    categoria = catalogo.crear_categoria(
        {"nombre": "Bebidas", "descripcion": "Bebidas sin alcohol"}
    )
    proveedor = catalogo.crear_proveedor({
        "razon_social": "Distribuidora Norte SA",
        "cuit": "30-12345678-9",
        "nombre": "Distribuidora Norte",
    })
    producto = catalogo.crear_producto({
        "codigo": "BEB-001",
        "nombre": "Agua",
        "categoria_id": categoria["id"],
        "precio_costo": 400,
        "precio_venta": 700,
        "stock_minimo": 10,
        "proveedor_id": proveedor["id"],
    })

    assert catalogo.listar_categorias() == [categoria]
    assert catalogo.listar_proveedores() == [proveedor]
    assert catalogo.listar_productos() == [producto]

    categoria = catalogo.actualizar_categoria(
        categoria["id"], {"nombre": "Aguas", "descripcion": "Agua envasada"}
    )
    proveedor = catalogo.actualizar_proveedor(proveedor["id"], {
        "razon_social": "Distribuidora Centro SA",
        "cuit": "30-87654321-0",
        "nombre": "Distribuidora Centro",
    })
    producto = catalogo.actualizar_producto(producto["id"], {
        "codigo": "BEB-002",
        "nombre": "Agua mineral",
        "categoria_id": categoria["id"],
        "precio_costo": 450,
        "precio_venta": 750,
        "stock_minimo": 12,
        "proveedor_id": proveedor["id"],
    })

    assert producto["nombre"] == "Agua mineral"
    assert categoria["descripcion"] == "Agua envasada"
    assert proveedor["cuit"] == "30-87654321-0"

    catalogo.eliminar_producto(producto["id"])
    catalogo.eliminar_categoria(categoria["id"])
    catalogo.eliminar_proveedor(proveedor["id"])
    assert catalogo.listar_productos() == []
    assert catalogo.listar_categorias() == []
    assert catalogo.listar_proveedores() == []


def test_catalogo_convierte_duplicados_en_errores_de_negocio(catalogo):
    categoria = catalogo.crear_categoria({"nombre": "Bebidas"})
    datos_producto = {
        "codigo": "BEB-001",
        "nombre": "Agua",
        "categoria_id": categoria["id"],
        "precio_costo": 400,
        "precio_venta": 700,
        "stock_minimo": 10,
    }
    catalogo.crear_producto(datos_producto)

    with pytest.raises(ReglaNegocioError, match="Ya existe un producto"):
        catalogo.crear_producto(datos_producto)
