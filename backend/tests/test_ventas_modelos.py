import sqlite3

import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from models.comprobante import Comprobante
from models.devolucion import DetalleDevolucion, Devolucion
from models.pago import Pago
from models.venta import DetalleVenta, Venta


@pytest.fixture
def db(tmp_path):
    BaseDeDatos.reiniciar()
    database = BaseDeDatos(str(tmp_path / "ventas.db"))
    cargar()
    yield database
    BaseDeDatos.reiniciar()


def test_schema_crea_tablas_y_guarda_ventas_y_devoluciones(db):
    tablas = {
        fila["name"]
        for fila in db.consultar("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {
        "venta", "detalle_venta", "pago", "comprobante",
        "devolucion", "detalle_devolucion",
    } <= tablas

    with db.transaccion():
        venta_id = db.ejecutar(
            "INSERT INTO venta (sucursal_id, subtotal, total) VALUES (2, 100, 90)"
        )
        db.ejecutar(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario) VALUES (?, 1, 2, 50)""",
            (venta_id,),
        )
        db.ejecutar(
            """INSERT INTO pago (venta_id, medio_pago, importe)
               VALUES (?, 'EFECTIVO', 90)""",
            (venta_id,),
        )
        db.ejecutar(
            "INSERT INTO comprobante (venta_id, numero) VALUES (?, 1)",
            (venta_id,),
        )
        devolucion_id = db.ejecutar(
            "INSERT INTO devolucion (venta_id, motivo, total) VALUES (?, 'Cambio', 50)",
            (venta_id,),
        )
        db.ejecutar(
            """INSERT INTO detalle_devolucion
               (devolucion_id, producto_id, cantidad, precio_unitario)
               VALUES (?, 1, 1, 50)""",
            (devolucion_id,),
        )

    assert db.consultar_uno(
        "SELECT precio_unitario FROM detalle_venta WHERE venta_id=?", (venta_id,)
    )["precio_unitario"] == 50
    assert db.consultar_uno(
        "SELECT numero FROM comprobante WHERE venta_id=?", (venta_id,)
    )["numero"] == 1
    assert db.consultar_uno(
        "SELECT total FROM devolucion WHERE id=?", (devolucion_id,)
    )["total"] == 50

    with pytest.raises(sqlite3.IntegrityError):
        db.ejecutar(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario) VALUES (?, 2, 0, 50)""",
            (venta_id,),
        )


def test_modelos_se_serializan_a_diccionarios():
    venta = Venta.desde_fila({
        "id": 1, "sucursal_id": 2, "fecha": "2026-10-19",
        "subtotal": 100, "total": 90,
    })
    assert venta.to_dict()["total"] == 90

    detalle = DetalleVenta(1, 3, 2, 50)
    assert detalle.to_dict()["precio_unitario"] == 50

    pago = Pago.desde_fila({
        "id": 1, "venta_id": 1, "medio_pago": "EFECTIVO",
        "importe": 90, "cuotas": 1, "referencia": None,
    })
    assert pago.to_dict()["medio_pago"] == "EFECTIVO"

    comprobante = Comprobante.desde_fila({
        "id": 1, "venta_id": 1, "numero": 1, "fecha": "2026-10-19",
    })
    assert comprobante.to_dict()["numero"] == 1

    devolucion = Devolucion.desde_fila({
        "id": 1, "venta_id": 1, "fecha": "2026-10-19",
        "motivo": "Cambio", "total": 50,
    })
    assert devolucion.to_dict()["motivo"] == "Cambio"

    detalle_devolucion = DetalleDevolucion(1, 3, 1, 50)
    assert detalle_devolucion.to_dict()["cantidad"] == 1
