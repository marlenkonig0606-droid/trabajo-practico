"""Tests del patrón Observer.   Correr desde backend/:  python -m pytest -v"""
import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from models.observer import Observador, Sujeto, Eventos
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.observadores import AlertaStockMinimoObserver, AuditoriaObserver, AlertasService

CD, LOCAL = 1, 2
AGUA = 1            # stock_minimo = 20 en los datos iniciales


@pytest.fixture
def app_svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "test.db"))
    cargar()
    stock = StockService()
    stock.suscribir(AlertaStockMinimoObserver())
    logistica = LogisticaService(stock)
    logistica.suscribir(StockObserver(stock))
    logistica.suscribir(AuditoriaObserver())
    yield logistica, stock, AlertasService()
    BaseDeDatos.reiniciar()


def enviar_y_recibir(logistica, cantidad, precinto, intacto=True):
    orden = logistica.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": cantidad}])
    bulto = logistica.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": cantidad}])
    logistica.precintar(bulto["id"], precinto)
    logistica.despachar(bulto["id"])
    logistica.recibir(bulto["id"], precinto, intacto)
    return bulto


# ---------- el mecanismo en sí ----------
class Espia(Observador):
    def __init__(self):
        self.recibidos = []

    def actualizar(self, evento, datos):
        self.recibidos.append(evento)


def test_sujeto_avisa_a_todos_los_suscriptos_y_no_a_los_desuscriptos():
    sujeto, a, b = Sujeto(), Espia(), Espia()
    sujeto.suscribir(a)
    sujeto.suscribir(b)
    sujeto.suscribir(a)                 # suscribir dos veces no duplica
    sujeto.notificar("X", {})
    sujeto.desuscribir(b)
    sujeto.notificar("Y", {})
    assert a.recibidos == ["X", "Y"]
    assert b.recibidos == ["X"]


def test_stock_service_notifica_cada_cambio(app_svc):
    _, stock, _ = app_svc
    espia = Espia()
    stock.suscribir(espia)
    stock.sumar(LOCAL, AGUA, 5, "AJUSTE")
    stock.restar(LOCAL, AGUA, 2, "AJUSTE")
    assert espia.recibidos == [Eventos.STOCK_MODIFICADO, Eventos.STOCK_MODIFICADO]


# ---------- AlertaStockMinimoObserver ----------
def test_alerta_cuando_el_local_queda_bajo_el_minimo(app_svc):
    logistica, _, alertas = app_svc
    enviar_y_recibir(logistica, 10, "A1")          # llegan 10, mínimo 20
    pendientes = alertas.alertas()
    assert len(pendientes) == 1
    assert pendientes[0]["sucursal"] == "Local Centro"
    assert pendientes[0]["libre"] == 10 and pendientes[0]["minimo"] == 20


def test_no_duplica_alertas_y_se_resuelve_sola(app_svc):
    logistica, _, alertas = app_svc
    enviar_y_recibir(logistica, 10, "A1")          # 10 < 20 -> alerta
    enviar_y_recibir(logistica, 5, "A2")           # 15 < 20 -> misma alerta, actualizada
    pendientes = alertas.alertas()
    assert len(pendientes) == 1 and pendientes[0]["libre"] == 15

    enviar_y_recibir(logistica, 10, "A3")          # 25 >= 20 -> se resuelve
    assert alertas.alertas() == []
    assert alertas.alertas(solo_pendientes=False)[0]["resuelta"] == 1


def test_reserva_en_el_cd_tambien_puede_alertar(app_svc):
    logistica, stock, alertas = app_svc
    orden = logistica.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 490}])
    logistica.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 490}])
    assert stock.libre(CD, AGUA) == 10
    assert [a["sucursal"] for a in alertas.alertas()] == ["CD Central"]


def test_si_la_operacion_falla_no_queda_alerta_colgada(app_svc):
    """El observador corre dentro de la misma transacción: si algo falla, se deshace todo."""
    logistica, _, alertas = app_svc
    orden = logistica.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 999}])
    with pytest.raises(Exception):
        logistica.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 999}])
    assert alertas.alertas(solo_pendientes=False) == []


# ---------- AuditoriaObserver ----------
def test_auditoria_registra_el_recorrido_del_bulto(app_svc):
    logistica, _, alertas = app_svc
    enviar_y_recibir(logistica, 10, "A1")
    eventos = [e["evento"] for e in reversed(alertas.eventos())]
    assert eventos == [Eventos.BULTO_DESPACHADO, Eventos.REMITO_VERIFICADO]


def test_auditoria_registra_rechazos_con_motivo(app_svc):
    logistica, _, alertas = app_svc
    enviar_y_recibir(logistica, 10, "A1", intacto=False)
    ultimo = alertas.eventos()[0]
    assert ultimo["evento"] == Eventos.BULTO_RECHAZADO
    assert "Precinto roto" in ultimo["detalle"]
