"""Correr desde backend/:   python -m pytest -v"""
import sqlite3
import threading
import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.excepciones import NoEncontradoError, ReglaNegocioError
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


def armar_y_despachar(svc, cantidad=10):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": cantidad}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": cantidad}])
    bulto = svc.precintar(bulto["id"])
    svc.despachar(bulto["id"])
    return orden, bulto


def test_flujo_feliz_suma_stock_solo_al_verificar(svc):
    stock = StockService()
    orden, bulto = armar_y_despachar(svc)
    assert stock.disponible(CD, AGUA) == 490          # salió del CD
    assert stock.disponible(LOCAL, AGUA) == 0         # en tránsito: no vendible

    recibido = svc.recibir(bulto["id"])
    assert recibido["estado"] == "RECIBIDO"
    assert stock.disponible(LOCAL, AGUA) == 0
    svc.verificar_recepcion(
        bulto["id"], f"R-{orden['id']:06d}", bulto["precinto"], precinto_intacto=True)
    assert stock.disponible(LOCAL, AGUA) == 10
    estados = [h["estado"] for h in svc.historial(bulto["id"])]
    assert estados == ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]


def test_precinto_roto_rechaza_y_no_habilita_venta(svc):
    _, bulto = armar_y_despachar(svc)
    svc.recibir(bulto["id"])
    r = svc.verificar_recepcion(
        bulto["id"], f"R-{bulto['remito_id']:06d}", bulto["precinto"],
        precinto_intacto=False)
    assert r["estado"] == "RECHAZADO"
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_precinto_que_no_coincide_rechaza(svc):
    _, bulto = armar_y_despachar(svc)
    svc.recibir(bulto["id"])
    assert svc.verificar_recepcion(
        bulto["id"], f"R-{bulto['remito_id']:06d}", "OTRO",
        precinto_intacto=True)["estado"] == "RECHAZADO"


def test_remito_con_dos_bultos_espera_a_ambos(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 5},
                                    {"producto_id": YERBA, "cantidad": 3}])
    b1 = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 5}])
    b2 = svc.crear_bulto(orden["id"], [{"producto_id": YERBA, "cantidad": 3}])
    b1 = svc.precintar(b1["id"])
    b2 = svc.precintar(b2["id"])
    for b in (b1, b2):
        svc.despachar(b["id"])

    svc.recibir(b1["id"])
    svc.verificar_recepcion(b1["id"], f"R-{orden['id']:06d}", b1["precinto"], True)
    assert StockService().disponible(LOCAL, AGUA) == 0   # remito todavía no verificado
    svc.recibir(b2["id"])
    svc.verificar_recepcion(b2["id"], f"R-{orden['id']:06d}", b2["precinto"], False)
    assert StockService().disponible(LOCAL, AGUA) == 5    # entra solo lo verificado
    assert StockService().disponible(LOCAL, YERBA) == 0


def test_no_se_puede_saltear_estados(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.despachar(bulto["id"])          # sin precintar


def test_no_se_puede_verificar_antes_de_recibir(svc):
    _, bulto = armar_y_despachar(svc)
    with pytest.raises(ReglaNegocioError):
        svc.verificar_recepcion(
            bulto["id"], f"R-{bulto['remito_id']:06d}", bulto["precinto"], True)
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_no_empaquetar_mas_de_lo_pedido(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 3}])
    with pytest.raises(ReglaNegocioError):
        svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 4}])


def test_precintos_generados_son_unicos(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 2}])
    primero = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    segundo = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    precinto_primero = svc.precintar(primero["id"])["precinto"]
    precinto_segundo = svc.precintar(segundo["id"])["precinto"]
    assert precinto_primero.startswith("P-")
    assert precinto_segundo.startswith("P-")
    assert precinto_primero != precinto_segundo


def test_precintar_bulto_inexistente(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    b = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    svc.precintar(b["id"])
    with pytest.raises(ReglaNegocioError):
        svc.precintar(b["id"])
    with pytest.raises(NoEncontradoError):
        svc.precintar(999999)


def test_armar_bulto_reserva_stock_del_cd(svc):
    stock = StockService()
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 300}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 300}])
    assert stock.disponible(CD, AGUA) == 500      # físicamente sigue en el CD
    assert stock.reservado(CD, AGUA) == 300       # pero ya está comprometido
    assert stock.libre(CD, AGUA) == 200

    svc.precintar(bulto["id"])
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


def test_orden_acepta_origen_cd_seleccionado_y_rechaza_origen_local(svc):
    segundo_cd = BaseDeDatos().ejecutar(
        "INSERT INTO sucursal (nombre, tipo) VALUES ('CD Secundario', 'CD')")
    orden = svc.crear_orden(
        LOCAL, [{"producto_id": AGUA, "cantidad": 1}], origen_id=segundo_cd)
    assert orden["origen_id"] == segundo_cd
    assert orden["origen"] == "CD Secundario"

    with pytest.raises(ReglaNegocioError, match="origen.*CD"):
        svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}], origen_id=LOCAL)


def test_anular_bulto_libera_la_reserva(svc):
    stock = StockService()
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 300}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 300}])
    svc.precintar(bulto["id"])
    assert stock.reservado(CD, AGUA) == 300

    r = svc.anular_bulto(bulto["id"], "Se rompió una caja")
    assert r["estado"] == "ANULADO"
    assert stock.reservado(CD, AGUA) == 0         # la reserva vuelve a estar libre
    assert stock.disponible(CD, AGUA) == 500      # y nunca salió del CD
    # lo anulado no cuenta como empaquetado: se puede volver a armar el bulto
    assert svc.obtener_orden(orden["id"])["items"][0]["empaquetado"] == 0
    svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 300}])
    assert stock.reservado(CD, AGUA) == 300


def test_no_se_puede_anular_un_bulto_despachado(svc):
    _, bulto = armar_y_despachar(svc)
    with pytest.raises(ReglaNegocioError):
        svc.anular_bulto(bulto["id"], "Tarde")
    assert svc.obtener_bulto(bulto["id"]).estado == "EN_TRANSITO"
    assert StockService().disponible(CD, AGUA) == 490   # el stock no se tocó


def test_anular_sin_motivo(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.anular_bulto(bulto["id"], "  ")
    assert StockService().reservado(CD, AGUA) == 1
