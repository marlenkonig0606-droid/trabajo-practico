import pytest

from database.conexion import BaseDeDatos
from services.catalogo_service import CatalogoService
from services.excepciones import NoEncontradoError, ReglaNegocioError


@pytest.fixture
def catalogo(tmp_path):
    BaseDeDatos.reiniciar()
    db = BaseDeDatos(str(tmp_path / "catalogo.db"))
    servicio = CatalogoService()
    yield servicio, db
    BaseDeDatos.reiniciar()


def crear_categoria(servicio, nombre="Bebidas"):
    return servicio.crear_categoria({"nombre": nombre})


def crear_proveedor(servicio, cuit="30-12345678-9"):
    return servicio.crear_proveedor({
        "cuit": cuit,
        "razon_social": "Distribuidora Norte SA",
        "nombre": "Distribuidora Norte",
    })


def crear_producto(servicio, categoria_id, proveedor_id=None, codigo="BEB-001"):
    return servicio.crear_producto({
        "codigo": codigo,
        "nombre": "Agua 1.5L",
        "categoria_id": categoria_id,
        "precio_costo": 400,
        "precio_venta": 700,
        "stock_minimo": 5,
        "proveedor_id": proveedor_id,
    })


def crear_sucursal(servicio, nombre, tipo="LOCAL", direccion="Dirección"):
    return servicio.crear_sucursal({
        "nombre": nombre,
        "direccion": direccion,
        "tipo": tipo,
    })


def test_abm_sucursal(catalogo):
    servicio, _ = catalogo
    cd = crear_sucursal(servicio, "CD Central", tipo="CD")
    local = crear_sucursal(servicio, "Local Centro")

    assert servicio.obtener_sucursal(cd["id"]) == cd
    assert {sucursal["id"] for sucursal in servicio.listar_sucursales()} == {
        cd["id"], local["id"],
    }

    actualizada = servicio.actualizar_sucursal(local["id"], {
        "nombre": "Local Nueva Córdoba",
        "direccion": "Bv. Illia 500",
        "tipo": "LOCAL",
    })
    assert actualizada == {
        "id": local["id"],
        "nombre": "Local Nueva Córdoba",
        "direccion": "Bv. Illia 500",
        "tipo": "LOCAL",
    }

    servicio.eliminar_sucursal(local["id"])
    with pytest.raises(NoEncontradoError):
        servicio.obtener_sucursal(local["id"])


def test_sucursal_rechaza_datos_invalidos_y_nombres_duplicados(catalogo):
    servicio, _ = catalogo
    crear_sucursal(servicio, "CD Central", tipo="CD")

    with pytest.raises(ReglaNegocioError, match="nombre"):
        crear_sucursal(servicio, " ")
    with pytest.raises(ReglaNegocioError, match="tipo"):
        crear_sucursal(servicio, "Sucursal inválida", tipo="DEPÓSITO")
    with pytest.raises(ReglaNegocioError, match="único"):
        crear_sucursal(servicio, "CD Central", tipo="CD")


def test_no_se_puede_crear_local_si_no_existe_un_cd(catalogo):
    servicio, _ = catalogo

    with pytest.raises(ReglaNegocioError, match="Centro de Distribución"):
        crear_sucursal(servicio, "Local Centro")

    assert servicio.listar_sucursales() == []


def test_debe_quedar_un_cd_al_eliminar_o_cambiar_tipo(catalogo):
    servicio, _ = catalogo
    cd_central = crear_sucursal(servicio, "CD Central", tipo="CD")

    with pytest.raises(ReglaNegocioError, match="Centro de Distribución"):
        servicio.eliminar_sucursal(cd_central["id"])
    with pytest.raises(ReglaNegocioError, match="Centro de Distribución"):
        servicio.actualizar_sucursal(cd_central["id"], {
            "nombre": "CD Central",
            "direccion": "Dirección",
            "tipo": "LOCAL",
        })

    otro_cd = crear_sucursal(servicio, "CD Norte", tipo="CD")
    actualizada = servicio.actualizar_sucursal(cd_central["id"], {
        "nombre": "Local Centro",
        "direccion": "Dirección",
        "tipo": "LOCAL",
    })
    assert actualizada["tipo"] == "LOCAL"

    with pytest.raises(ReglaNegocioError, match="Centro de Distribución"):
        servicio.eliminar_sucursal(otro_cd["id"])
def test_abm_categoria(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)

    assert categoria["nombre"] == "Bebidas"
    assert servicio.listar_categorias()[0]["id"] == categoria["id"]

    actualizada = servicio.actualizar_categoria(
        categoria["id"], {"nombre": "Almacén"}
    )
    assert actualizada["nombre"] == "Almacén"

    servicio.eliminar_categoria(categoria["id"])
    with pytest.raises(NoEncontradoError):
        servicio.obtener_categoria(categoria["id"])


def test_categoria_duplicada_se_rechaza(catalogo):
    servicio, _ = catalogo
    crear_categoria(servicio)

    with pytest.raises(ReglaNegocioError, match="Ya existe"):
        crear_categoria(servicio)


def test_no_se_puede_borrar_categoria_usada_por_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    crear_producto(servicio, categoria["id"])

    with pytest.raises(ReglaNegocioError, match="productos asociados"):
        servicio.eliminar_categoria(categoria["id"])


def test_abm_proveedor(catalogo):
    servicio, _ = catalogo
    proveedor = crear_proveedor(servicio)

    assert proveedor["cuit"] == "30-12345678-9"
    assert servicio.listar_proveedores()[0]["id"] == proveedor["id"]

    datos_actualizados = {
        "cuit": "30-98765432-1",
        "razon_social": "Distribuidora Sur SA",
        "nombre": "Distribuidora Sur",
    }
    actualizada = servicio.actualizar_proveedor(proveedor["id"], datos_actualizados)
    assert actualizada["cuit"] == "30-98765432-1"

    servicio.eliminar_proveedor(proveedor["id"])
    with pytest.raises(NoEncontradoError):
        servicio.obtener_proveedor(proveedor["id"])


def test_cuit_duplicado_se_rechaza(catalogo):
    servicio, _ = catalogo
    crear_proveedor(servicio)

    with pytest.raises(ReglaNegocioError, match="CUIT"):
        crear_proveedor(servicio)


def test_no_se_puede_borrar_proveedor_usado_por_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    proveedor = crear_proveedor(servicio)
    crear_producto(servicio, categoria["id"], proveedor["id"])

    with pytest.raises(ReglaNegocioError, match="productos asociados"):
        servicio.eliminar_proveedor(proveedor["id"])


def test_abm_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])

    assert producto["codigo"] == "BEB-001"
    assert servicio.listar_productos()[0]["id"] == producto["id"]

    datos_actualizados = {
        "codigo": "BEB-002",
        "nombre": "Agua sin gas",
        "categoria_id": categoria["id"],
        "precio_costo": 450,
        "precio_venta": 750,
        "stock_minimo": 8,
    }
    actualizada = servicio.actualizar_producto(producto["id"], datos_actualizados)
    assert actualizada["codigo"] == "BEB-002"
    assert actualizada["nombre"] == "Agua sin gas"

    servicio.eliminar_producto(producto["id"])
    with pytest.raises(NoEncontradoError):
        servicio.obtener_producto(producto["id"])


def test_codigo_duplicado_se_rechaza(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    crear_producto(servicio, categoria["id"])

    with pytest.raises(ReglaNegocioError, match="código"):
        crear_producto(servicio, categoria["id"])


def test_producto_invalido_se_rechaza(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    datos = {
        "codigo": "BEB-001",
        "nombre": "Agua",
        "categoria_id": categoria["id"],
        "precio_costo": -1,
        "precio_venta": 700,
        "stock_minimo": 5,
    }

    with pytest.raises(ReglaNegocioError, match="costo"):
        servicio.crear_producto(datos)


def test_no_se_puede_borrar_producto_con_stock(catalogo):
    servicio, db = catalogo
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])
    with db.transaccion():
        sucursal_id = db.ejecutar(
            "INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?, ?, ?)",
            ("CD de prueba", "Dirección", "CD"),
        )
        db.ejecutar(
            "INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)",
            (sucursal_id, producto["id"], 10),
        )

    with pytest.raises(ReglaNegocioError, match="registros asociados"):
        servicio.eliminar_producto(producto["id"])
