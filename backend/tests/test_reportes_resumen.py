import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.reportes_service import ReportesService
from services.stock_service import StockService
from services.ventas_service import VentasService


@pytest.fixture
def reportes(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "reportes_resumen.db"))
    cargar()
    stock = StockService()
    ventas = VentasService(stock)
    stock.sumar(2, 1, 10, "TEST")
    stock.sumar(3, 1, 10, "TEST")

    ventas.registrar_venta(
        2, [{"producto_id": 1, "cantidad": 2}], "TARJETA_DEBITO")
    venta_local_tres = ventas.registrar_venta(
        3, [{"producto_id": 1, "cantidad": 4}], "TARJETA_DEBITO")
    ventas.registrar_devolucion(
        venta_local_tres["id"], [{"producto_id": 1, "cantidad": 1}], "Prueba")
    yield ReportesService()
    BaseDeDatos.reiniciar()


def test_resumen_compara_locales_y_calcula_ingresos_netos(reportes):
    resumen = reportes.resumen()

    assert resumen["ventas"] == 2
    assert resumen["ingresos"] == 4200
    assert resumen["importe_devuelto"] == 700
    assert resumen["ingresos_netos"] == 3500
    assert resumen["unidades_vendidas"] == 6
    assert resumen["local_mas_vendio"] == {
        "id": 3,
        "nombre": "Local Nueva Córdoba",
        "ingresos_netos": 2100,
        "cantidad_ventas": 1,
    }

    resumen_local = reportes.resumen(sucursal_id=2)
    assert resumen_local["ventas"] == 1
    assert resumen_local["ingresos_netos"] == 1400
    assert resumen_local["local_mas_vendio"] is None
