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
        "codigo": local["codigo"],
        "nombre": "Local Nueva Córdoba",
        "direccion": "Bv. Illia 500",
        "tipo": "LOCAL",
        "activo": True,
    }

    servicio.eliminar_sucursal(local["id"])
    assert servicio.obtener_sucursal(local["id"])["activo"] == 0
    assert local["id"] not in {
        sucursal["id"] for sucursal in servicio.listar_sucursales(solo_activas=True)
    }


def test_sucursal_rechaza_datos_invalidos_y_nombres_duplicados(catalogo):
    servicio, _ = catalogo
    crear_sucursal(servicio, "CD Central", tipo="CD")

    with pytest.raises(ReglaNegocioError, match="nombre"):
        crear_sucursal(servicio, " ")
    with pytest.raises(ReglaNegocioError, match="tipo"):
        crear_sucursal(servicio, "Sucursal inválida", tipo="DEPÓSITO")
    with pytest.raises(ReglaNegocioError, match="sucursal"):
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
def test_categoria_se_desactiva_sin_borrar(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)

    assert categoria["nombre"] == "Bebidas"
    assert servicio.listar_categorias()[0]["id"] == categoria["id"]

    actualizada = servicio.actualizar_categoria(
        categoria["id"], {"nombre": "Almacén"}
    )
    assert actualizada["nombre"] == "Almacén"

    servicio.eliminar_categoria(categoria["id"])
    assert servicio.obtener_categoria(categoria["id"])["activo"] == 0


def test_categoria_duplicada_se_rechaza(catalogo):
    servicio, _ = catalogo
    crear_categoria(servicio)

    with pytest.raises(ReglaNegocioError, match="Ya existe"):
        crear_categoria(servicio)


def test_categoria_usada_se_puede_desactivar_y_conserva_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    crear_producto(servicio, categoria["id"])

    servicio.eliminar_categoria(categoria["id"])
    assert servicio.obtener_producto(1)["categoria_id"] == categoria["id"]


def test_abm_proveedor(catalogo):
    servicio, _ = catalogo
    proveedor = crear_proveedor(servicio)

    assert proveedor["cuit"] == "30123456789"
    assert servicio.listar_proveedores()[0]["id"] == proveedor["id"]

    datos_actualizados = {
        "cuit": "30 98765432-1",
        "razon_social": "Distribuidora Sur SA",
        "nombre": "Distribuidora Sur",
    }
    actualizada = servicio.actualizar_proveedor(proveedor["id"], datos_actualizados)
    assert actualizada["cuit"] == "30987654321"

    servicio.eliminar_proveedor(proveedor["id"])
    assert servicio.obtener_proveedor(proveedor["id"])["activo"] == 0


def test_cuit_duplicado_se_rechaza(catalogo):
    servicio, _ = catalogo
    crear_proveedor(servicio)

    with pytest.raises(ReglaNegocioError, match="CUIT"):
        crear_proveedor(servicio)


def test_proveedor_usado_se_desactiva_y_conserva_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    proveedor = crear_proveedor(servicio)
    crear_producto(servicio, categoria["id"], proveedor["id"])

    servicio.eliminar_proveedor(proveedor["id"])
    assert servicio.obtener_producto(1)["proveedor_id"] == proveedor["id"]


def test_proveedor_desactivado_no_se_asigna_a_productos_nuevos(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    proveedor = crear_proveedor(servicio)
    producto_existente = crear_producto(servicio, categoria["id"], proveedor["id"])
    servicio.cambiar_estado_proveedor(proveedor["id"], False)

    with pytest.raises(ReglaNegocioError, match="proveedores activos"):
        crear_producto(servicio, categoria["id"], proveedor["id"], codigo="BEB-002")

    datos_actualizados = {
        "codigo": producto_existente["codigo"],
        "nombre": "Agua actualizada",
        "categoria_id": categoria["id"],
        "precio_costo": 400,
        "precio_venta": 700,
        "stock_minimo": 5,
        "proveedor_id": proveedor["id"],
    }
    actualizado = servicio.actualizar_producto(producto_existente["id"], datos_actualizados)
    assert actualizado["proveedor_id"] == proveedor["id"]



def test_abm_producto(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])

    assert producto["codigo"] == "beb-001"
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
    assert actualizada["codigo"] == "beb-002"
    assert actualizada["nombre"] == "Agua sin gas"

    servicio.eliminar_producto(producto["id"])
    assert servicio.obtener_producto(producto["id"])["activo"] == 0


def test_codigo_duplicado_se_rechaza(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    crear_producto(servicio, categoria["id"])

    with pytest.raises(ReglaNegocioError, match="código"):
        crear_producto(servicio, categoria["id"], codigo=" beB - 001 ")


def test_codigo_se_guarda_en_minusculas_y_sin_espacios(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)

    producto = crear_producto(servicio, categoria["id"], codigo="  BeB \t- 001 ")

    assert producto["codigo"] == "beb-001"


def test_codigo_normalizado_unico_al_actualizar(catalogo):
    servicio, _ = catalogo
    categoria = crear_categoria(servicio)
    primero = crear_producto(servicio, categoria["id"], codigo="BEB-001")
    segundo = crear_producto(servicio, categoria["id"], codigo="ALM-001")

    datos = {
        "codigo": " beB - 001 ",
        "nombre": "Producto duplicado",
        "categoria_id": categoria["id"],
        "precio_costo": 400,
        "precio_venta": 700,
        "stock_minimo": 5,
    }
    with pytest.raises(ReglaNegocioError, match="Ya existe un producto"):
        servicio.actualizar_producto(segundo["id"], datos)


def test_codigo_normalizado_rechaza_variantes_legacy(catalogo):
    servicio, db = catalogo
    categoria = crear_categoria(servicio)
    with db.transaccion():
        db.ejecutar(
            """INSERT INTO producto
               (codigo, nombre, categoria_id, precio_costo, precio_venta, stock_minimo)
               VALUES (?, ?, ?, ?, ?, ?)""",
            ("Ab C-001", "Producto anterior", categoria["id"], 10, 20, 0),
        )

    with pytest.raises(ReglaNegocioError, match="Ya existe un producto"):
        crear_producto(servicio, categoria["id"], codigo="abc-001")


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


def test_alta_sucursal_exige_direccion(catalogo):
    servicio, _ = catalogo
    crear_sucursal(servicio, "CD Central", tipo="CD")

    with pytest.raises(ReglaNegocioError, match="dirección"):
        servicio.crear_sucursal({
            "nombre": "Local sin dirección",
            "direccion": " ",
            "tipo": "LOCAL",
        })


def test_sucursal_tiene_codigo_unico_y_nombre_no_distingue_mayusculas(catalogo):
    servicio, _ = catalogo
    cd = crear_sucursal(servicio, "CD Central", tipo="CD")
    local = crear_sucursal(servicio, "Local Centro")

    assert cd["codigo"] != local["codigo"]
    assert cd["codigo"].startswith("SUC-")
    with pytest.raises(ReglaNegocioError, match="sucursal"):
        crear_sucursal(servicio, "  cd central  ", tipo="CD")


def test_cuit_compara_solo_digitos(catalogo):
    servicio, _ = catalogo
    proveedor = crear_proveedor(servicio, "30-12345678-9")

    with pytest.raises(ReglaNegocioError, match="CUIT"):
        crear_proveedor(servicio, "30 12345678 9")

    actualizado = servicio.actualizar_proveedor(proveedor["id"], {
        "cuit": "30 12345678-9",
        "razon_social": "Otra razón social",
        "nombre": "Otro nombre",
    })
    assert actualizado["id"] == proveedor["id"]
    assert actualizado["razon_social"] == "Otra razón social"


def test_local_habilita_productos_y_no_puede_desactivar_con_stock(catalogo):
    servicio, db = catalogo
    crear_sucursal(servicio, "CD Central", tipo="CD")
    local = crear_sucursal(servicio, "Local Centro")
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])

    assert servicio.productos_habilitados_sucursal(local["id"])[0]["id"] == producto["id"]
    with db.transaccion():
        db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible)
               VALUES (?, ?, 2)""",
            (local["id"], producto["id"]),
        )
    with pytest.raises(ReglaNegocioError, match="stock"):
        servicio.cambiar_habilitacion_producto(local["id"], producto["id"], False)

    servicio.cambiar_habilitacion_producto(local["id"], producto["id"], True)
    assert servicio.producto_dao.esta_habilitado_en_sucursal(
        local["id"], producto["id"])


def test_baja_sucursal_conserva_stock_y_historial(catalogo):
    servicio, db = catalogo
    crear_sucursal(servicio, "CD Central", tipo="CD")
    local = crear_sucursal(servicio, "Local con stock")
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])
    with db.transaccion():
        db.ejecutar(
            "INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)",
            (local["id"], producto["id"], 7),
        )

    sucursal = servicio.cambiar_estado_sucursal(local["id"], False)

    assert sucursal["activo"] == 0
    assert db.consultar_uno(
        "SELECT disponible FROM stock WHERE sucursal_id=? AND producto_id=?",
        (local["id"], producto["id"]),
    )["disponible"] == 7


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

    with pytest.raises(ReglaNegocioError, match="stock disponible o reservado"):
        servicio.eliminar_producto(producto["id"])


def test_no_se_puede_borrar_producto_con_stock_reservado(catalogo):
    servicio, db = catalogo
    categoria = crear_categoria(servicio)
    producto = crear_producto(servicio, categoria["id"])
    with db.transaccion():
        sucursal_id = db.ejecutar(
            "INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?, ?, ?)",
            ("CD reservado", "Dirección", "CD"),
        )
        db.ejecutar(
            """INSERT INTO stock (sucursal_id, producto_id, disponible, reservado)
               VALUES (?, ?, 5, 5)""",
            (sucursal_id, producto["id"]),
        )

    with pytest.raises(ReglaNegocioError, match="stock disponible o reservado"):
        servicio.eliminar_producto(producto["id"])
