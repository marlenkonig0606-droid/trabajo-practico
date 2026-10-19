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
from services.excepciones import ReglaNegocioError
from backend.services.medio_pago_service import (
    ICreadorMedioDePago,
    CREADORES_MEDIO_DE_PAGO,
    obtener_creador_medio_de_pago,
)
from services.stock_service import StockService
from services.ventas_service import VentasService


CD, LOCAL = 1, 2
AGUA = 1


@pytest.fixture
def svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "ventas_service.db"))
    cargar()
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


def test_venta_sin_stock_hace_rollback(svc):
    ventas, stock = svc
    with pytest.raises(ReglaNegocioError, match="Stock insuficiente"):
        ventas.registrar_venta(
            LOCAL, [{"producto_id": AGUA, "cantidad": 1}], "EFECTIVO")

    assert ventas.db.consultar_uno("SELECT COUNT(*) AS total FROM venta")["total"] == 0
    assert ventas.db.consultar_uno(
        "SELECT COUNT(*) AS total FROM comprobante")["total"] == 0
    assert stock.disponible(LOCAL, AGUA) == 0
