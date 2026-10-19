"""Correr desde backend/:   python -m pytest -v"""
import sqlite3
import threading
import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.excepciones import ReglaNegocioError
from services.observadores import AlertaStockMinimoObserver, AuditoriaObserver

CD, LOCAL = 1, 2
AGUA, YERBA = 1, 3


@pytest.fixture
def svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "test.db"))
    cargar()
    stock = StockService()
    stock.suscribir(AlertaStockMinimoObserver())
    logistica = LogisticaService(stock)
    logistica.suscribir(StockObserver(stock))
    logistica.suscribir(AuditoriaObserver())
    yield logistica
    BaseDeDatos.reiniciar()


def armar_y_despachar(svc, cantidad=10, precinto="P-1"):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": cantidad}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": cantidad}])
    svc.precintar(bulto["id"], precinto)
    svc.despachar(bulto["id"])
    return orden, bulto


def test_flujo_feliz_suma_stock_solo_al_verificar(svc):
    stock = StockService()
    orden, bulto = armar_y_despachar(svc)
    assert stock.disponible(CD, AGUA) == 490          # salió del CD
    assert stock.disponible(LOCAL, AGUA) == 0         # en tránsito: no vendible

    svc.recibir(bulto["id"], "P-1", precinto_intacto=True)
    assert stock.disponible(LOCAL, AGUA) == 10
    estados = [h["estado"] for h in svc.historial(bulto["id"])]
    assert estados == ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]


def test_precinto_roto_rechaza_y_no_habilita_venta(svc):
    _, bulto = armar_y_despachar(svc)
    r = svc.recibir(bulto["id"], "P-1", precinto_intacto=False)
    assert r["estado"] == "RECHAZADO"
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_precinto_que_no_coincide_rechaza(svc):
    _, bulto = armar_y_despachar(svc)
    assert svc.recibir(bulto["id"], "OTRO", precinto_intacto=True)["estado"] == "RECHAZADO"


def test_remito_con_dos_bultos_espera_a_ambos(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 5},
                                    {"producto_id": YERBA, "cantidad": 3}])
    b1 = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 5}])
    b2 = svc.crear_bulto(orden["id"], [{"producto_id": YERBA, "cantidad": 3}])
    for b, p in ((b1, "A"), (b2, "B")):
        svc.precintar(b["id"], p); svc.despachar(b["id"])

    svc.recibir(b1["id"], "A", True)
    assert StockService().disponible(LOCAL, AGUA) == 0   # remito todavía no verificado
    svc.recibir(b2["id"], "B", False)                     # el segundo llega roto
    assert StockService().disponible(LOCAL, AGUA) == 5    # entra solo lo verificado
    assert StockService().disponible(LOCAL, YERBA) == 0


def test_no_se_puede_saltear_estados(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.despachar(bulto["id"])          # sin precintar


def test_no_empaquetar_mas_de_lo_pedido(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 3}])
    with pytest.raises(ReglaNegocioError):
        svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 4}])


def test_precinto_duplicado(svc):
    armar_y_despachar(svc, precinto="X")
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    b = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.precintar(b["id"], "X")


def test_armar_bulto_reserva_stock_del_cd(svc):
    stock = StockService()
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 300}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 300}])
    assert stock.disponible(CD, AGUA) == 500      # físicamente sigue en el CD
    assert stock.reservado(CD, AGUA) == 300       # pero ya está comprometido
    assert stock.libre(CD, AGUA) == 200

    svc.precintar(bulto["id"], "R1")
    svc.despachar(bulto["id"])
    assert stock.disponible(CD, AGUA) == 200      # al despachar sale y se libera la reserva
    assert stock.reservado(CD, AGUA) == 0


def test_sin_stock_libre_no_se_arma_el_bulto(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 999}])
    with pytest.raises(ReglaNegocioError):
        svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 999}])
    assert svc.obtener_orden(orden["id"])["bultos"] == []    # rollback: no quedó nada
    assert StockService().reservado(CD, AGUA) == 0


def test_dos_usuarios_a_la_vez_por_el_mismo_stock(svc):
    """Hay 500 en el CD. Dos usuarios piden 300 cada uno EXACTAMENTE al mismo tiempo.
    Solo uno puede quedarse con el stock; el otro recibe un error claro."""
    o1 = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 300}])
    o2 = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 300}])
    largada = threading.Barrier(2)        # hace que los dos hilos arranquen juntos
    resultados = []

    def usuario(orden_id):
        largada.wait()
        try:
            svc.crear_bulto(orden_id, [{"producto_id": AGUA, "cantidad": 300}])
            resultados.append("ok")
        except ReglaNegocioError:
            resultados.append("rechazado")

    hilos = [threading.Thread(target=usuario, args=(o["id"],)) for o in (o1, o2)]
    for h in hilos: h.start()
    for h in hilos: h.join()

    assert sorted(resultados) == ["ok", "rechazado"]
    assert StockService().reservado(CD, AGUA) == 300     # nunca 600


def test_muchos_usuarios_nunca_sobrevenden(svc):
    """20 usuarios piden 40 unidades a la vez (800 en total) sobre 500 -> entran 12."""
    ordenes = [svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 40}]) for _ in range(20)]
    largada = threading.Barrier(len(ordenes))
    exitos = []

    def usuario(orden_id):
        largada.wait()
        try:
            svc.crear_bulto(orden_id, [{"producto_id": AGUA, "cantidad": 40}])
            exitos.append(orden_id)
        except ReglaNegocioError:
            pass

    hilos = [threading.Thread(target=usuario, args=(o["id"],)) for o in ordenes]
    for h in hilos: h.start()
    for h in hilos: h.join()

    assert len(exitos) == 12                              # 12 * 40 = 480 <= 500
    assert StockService().reservado(CD, AGUA) == 480


def test_historial_es_inmutable(svc):
    _, bulto = armar_y_despachar(svc)
    with pytest.raises(sqlite3.DatabaseError):
        BaseDeDatos().ejecutar("DELETE FROM historial_bulto WHERE bulto_id=?", (bulto["id"],))


def test_orden_a_cd_no_permitida(svc):
    with pytest.raises(ReglaNegocioError):
        svc.crear_orden(CD, [{"producto_id": AGUA, "cantidad": 1}])
