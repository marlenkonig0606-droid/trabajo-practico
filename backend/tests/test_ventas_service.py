import threading
from datetime import datetime, timedelta

import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from models.medio_pago import (
    Efectivo,
    IMedioDePago,
    TarjetaCredito,
    TarjetaDebito,
    Transferencia,
)
from services.excepciones import NoEncontradoError, ReglaNegocioError
from services.medio_pago_service import (
    ICreadorMedioDePago,
    CREADORES_MEDIO_DE_PAGO,
    obtener_creador_medio_de_pago,
)
from services.stock_service import StockService
from services.ventas_service import VentasService
from services.catalogo_service import CatalogoService


CD, LOCAL = 1, 2
AGUA = 1


@pytest.fixture
def svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "ventas_service.db"))
    cargar(incluir_demo=False)
    stock = StockService()
    ventas = VentasService(stock)
    yield ventas, stock
    BaseDeDatos.reiniciar()


def test_creadores_concretos_construyen_productos_contrato_comun():
    productos = {
        tipo: creador.crear_medio_de_pago()
        for tipo, creador in CREADORES_MEDIO_DE_PAGO.items()
    }

    assert isinstance(productos["EFECTIVO"], Efectivo)
    assert isinstance(productos["TARJETA_CREDITO"], TarjetaCredito)
    assert isinstance(productos["TARJETA_DEBITO"], TarjetaDebito)
    assert isinstance(productos["TRANSFERENCIA"], Transferencia)
    assert {tipo: producto.nombre for tipo, producto in productos.items()} == {
        "EFECTIVO": "EFECTIVO",
        "TARJETA_CREDITO": "TARJETA_CREDITO",
        "TARJETA_DEBITO": "TARJETA_DEBITO",
        "TRANSFERENCIA": "TRANSFERENCIA",
    }
    assert all(isinstance(producto, IMedioDePago) for producto in productos.values())
    assert all(isinstance(creador, ICreadorMedioDePago)
               for creador in CREADORES_MEDIO_DE_PAGO.values())


def test_tarjeta_credito_aplica_recargo_de_cinco_por_cuota():
    medio = obtener_creador_medio_de_pago("TARJETA_CREDITO").crear_medio_de_pago(
        cuotas=3,
    )
    assert medio.calcular_total(1000) == 1150


def test_creador_rechaza_tipo_desconocido():
    with pytest.raises(ReglaNegocioError, match="Medio de pago desconocido"):
        obtener_creador_medio_de_pago("CRIPTO")


def test_venta_usa_el_creador_y_registra_el_pago_y_comprobante(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 5, "TEST")

    venta = ventas.registrar_venta(
        LOCAL,
        [{"producto_id": AGUA, "cantidad": 2}],
        "TARJETA_CREDITO",
        cuotas=2,
    )

    assert venta["subtotal"] == 1400
    assert venta["total"] == 1540
    assert venta["medio_pago"] == "TARJETA_CREDITO"
    assert venta["comprobante_numero"] == 1
    assert stock.disponible(LOCAL, AGUA) == 3
    assert ventas.db.consultar_uno(
        "SELECT importe, cuotas FROM pago WHERE id=?", (venta["pago_id"],)
    ) == {"importe": 1540.0, "cuotas": 2}


def test_venta_en_cd_se_rechaza(svc):
    ventas, _ = svc
    with pytest.raises(ReglaNegocioError, match="Solo se pueden registrar ventas"):
        ventas.registrar_venta(CD, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")


def test_sucursal_inactiva_no_puede_vender(svc):
    ventas, _ = svc
    CatalogoService().cambiar_estado_sucursal(LOCAL, False)

    with pytest.raises(ReglaNegocioError, match="sucursal inactiva"):
        ventas.registrar_venta(
            LOCAL, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")


def test_venta_sin_stock_hace_rollback(svc):
    ventas, stock = svc
    with pytest.raises(ReglaNegocioError, match="Stock insuficiente"):
        ventas.registrar_venta(
            LOCAL, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")

    assert ventas.db.consultar_uno("SELECT COUNT(*) AS total FROM venta")["total"] == 0
    assert ventas.db.consultar_uno(
        "SELECT COUNT(*) AS total FROM comprobante")["total"] == 0
    assert stock.disponible(LOCAL, AGUA) == 0


def test_stock_inconsistente_se_bloquea_hasta_una_conciliacion_auditada(svc):
    ventas, stock = svc
    with stock.db.transaccion():
        stock.db.ejecutar(
            "INSERT INTO stock (sucursal_id, producto_id, disponible) VALUES (?, ?, ?)",
            (LOCAL, AGUA, 3))
    with pytest.raises(ReglaNegocioError, match="Stock bloqueado"):
        stock.sumar(LOCAL, AGUA, 1, "TEST")

    stock.ajustar_disponible(LOCAL, AGUA, 3, "Conteo físico validado")
    assert stock.disponible(LOCAL, AGUA) == 3
    assert stock.dao.cantidad_registrada_en_movimientos(LOCAL, AGUA) == 3
    assert ventas.db.consultar_uno(
        "SELECT motivo, referencia FROM movimiento_stock ORDER BY id DESC LIMIT 1"
    ) == {
        "motivo": "CONCILIACION",
        "referencia": "Conteo físico validado",
    }


def test_venta_rechaza_producto_no_habilitado_o_sin_precio_valido(svc):
    ventas, _ = svc
    CatalogoService().cambiar_habilitacion_producto(LOCAL, AGUA, False)
    with pytest.raises(ReglaNegocioError, match="no está habilitado"):
        ventas.registrar_venta(
            LOCAL, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")


def test_devolucion_conserva_costo_historico_y_vence_a_los_30_dias(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 5, "APERTURA")
    venta = ventas.registrar_venta(
        LOCAL, [{"producto_id": AGUA, "cantidad": 2}], "EFECTIVO")
    ventas.db.ejecutar("UPDATE producto SET precio_costo=900 WHERE id=?", (AGUA,))

    ventas.registrar_devolucion(
        venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Devolución parcial")
    assert ventas.db.consultar_uno(
        "SELECT costo_unitario FROM detalle_devolucion WHERE devolucion_id=1"
    )["costo_unitario"] == 400
    assert ventas.db.consultar_uno(
        """SELECT costo_unitario FROM movimiento_stock
           WHERE motivo='DEVOLUCION' ORDER BY id DESC LIMIT 1"""
    )["costo_unitario"] == 400

    fecha_antigua = (datetime.now().astimezone() - timedelta(days=31)).isoformat()
    ventas.db.ejecutar("UPDATE venta SET fecha=? WHERE id=?", (fecha_antigua, venta["id"]))
    with pytest.raises(ReglaNegocioError, match="30 días"):
        ventas.registrar_devolucion(
            venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Fuera de plazo")


def test_ventas_simultaneas_no_pueden_vender_el_mismo_stock_dos_veces(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 5, "APERTURA")
    barrera = threading.Barrier(2)
    resultados = []

    def vender():
        barrera.wait()
        try:
            ventas.registrar_venta(
                LOCAL, [{"producto_id": AGUA, "cantidad": 4}], "EFECTIVO")
            resultados.append("ok")
        except ReglaNegocioError:
            resultados.append("rechazada")

    hilos = [threading.Thread(target=vender) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == ["ok", "rechazada"]
    assert stock.disponible(LOCAL, AGUA) == 1


def test_devoluciones_simultaneas_no_superan_lo_vendido(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 1, "APERTURA")
    venta = ventas.registrar_venta(
        LOCAL, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")
    barrera = threading.Barrier(2)
    resultados = []

    def devolver():
        barrera.wait()
        try:
            ventas.registrar_devolucion(
                venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Concurrente")
            resultados.append("ok")
        except ReglaNegocioError:
            resultados.append("rechazada")

    hilos = [threading.Thread(target=devolver) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join()

    assert sorted(resultados) == ["ok", "rechazada"]
    assert ventas.db.consultar_uno(
        "SELECT COUNT(*) AS cantidad FROM devolucion WHERE venta_id=?",
        (venta["id"],),
    )["cantidad"] == 1
    assert stock.disponible(LOCAL, AGUA) == 1


def test_devolucion_de_venta_inexistente_se_rechaza(svc):
    ventas, _ = svc

    with pytest.raises(NoEncontradoError, match="No existe la venta"):
        ventas.registrar_devolucion(
            999, [{"producto_id": AGUA, "cantidad": 1}], "Producto defectuoso")


def test_devolucion_parcial_reintegra_proporcionalmente_y_repone_stock(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 5, "TEST")
    venta = ventas.registrar_venta(
        LOCAL, [{"producto_id": AGUA, "cantidad": 2}], "EFECTIVO")
    assert venta["total"] == 1260

    devolucion = ventas.registrar_devolucion(
        venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Producto defectuoso")

    assert devolucion["total"] == 630
    assert stock.disponible(LOCAL, AGUA) == 4
    assert ventas.db.consultar_uno(
        """SELECT tipo, importe FROM movimiento_caja
           WHERE devolucion_id=?""",
        (devolucion["id"],),
    ) == {"tipo": "EGRESO", "importe": 630.0}


def test_devoluciones_parciales_acumuladas_no_permiten_devolver_mas_de_lo_vendido(svc):
    ventas, stock = svc
    stock.sumar(LOCAL, AGUA, 5, "TEST")
    venta = ventas.registrar_venta(
        LOCAL, [{"producto_id": AGUA, "cantidad": 2}], "EFECTIVO")

    primera = ventas.registrar_devolucion(
        venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Primer artículo")
    segunda = ventas.registrar_devolucion(
        venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Segundo artículo")

    assert primera["total"] + segunda["total"] == venta["total"]
    assert ventas.db.consultar_uno(
        "SELECT COUNT(*) AS cantidad FROM movimiento_caja WHERE tipo='EGRESO'"
    )["cantidad"] == 2
    with pytest.raises(ReglaNegocioError, match="quedan 0 por devolver"):
        ventas.registrar_devolucion(
            venta["id"], [{"producto_id": AGUA, "cantidad": 1}], "Devolución excesiva")
    assert stock.disponible(LOCAL, AGUA) == 5
