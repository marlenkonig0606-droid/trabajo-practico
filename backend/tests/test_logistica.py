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
from services.catalogo_service import CatalogoService

CD, LOCAL = 1, 2
AGUA, YERBA = 1, 3


@pytest.fixture
def svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "test.db"))
    cargar(incluir_demo=False)
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
    svc.verificar_recepcion(bulto["id"], True)
    assert stock.disponible(LOCAL, AGUA) == 10
    estados = [h["estado"] for h in svc.historial(bulto["id"])]
    assert estados == ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]


def test_local_puede_rechazar_bulto_y_no_habilita_venta(svc):
    orden, bulto = armar_y_despachar(svc)
    svc.recibir(bulto["id"])
    r = svc.verificar_recepcion(
        bulto["id"], False, "Precinto dañado al recibir")
    assert r["estado"] == "RECHAZADO"
    assert StockService().disponible(LOCAL, AGUA) == 0
    assert StockService().disponible(CD, AGUA) == 500
    assert svc.obtener_bulto(bulto["id"]).estado == "RECHAZADO"
    assert svc.dao.obtener_bulto(bulto["id"])["observacion_rechazo"] == (
        "Precinto dañado al recibir")
    nuevo = svc.crear_bulto(
        orden["id"], [{"producto_id": AGUA, "cantidad": 10}])
    assert nuevo["id"] != bulto["id"]
    assert StockService().reservado(CD, AGUA) == 10


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
    svc.verificar_recepcion(b1["id"], True)
    assert StockService().disponible(LOCAL, AGUA) == 0   # remito todavía no verificado
    svc.recibir(b2["id"])
    svc.verificar_recepcion(b2["id"], False, "Bulto incompleto")
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
            bulto["id"], True)
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_no_empaquetar_mas_de_lo_pedido(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 3}])
    with pytest.raises(ReglaNegocioError):
        svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 4}])


def test_solicitud_rechaza_cantidades_no_enteras_y_producto_no_habilitado(svc):
    with pytest.raises(ReglaNegocioError, match="entero positivo"):
        svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1.5}])
    CatalogoService().cambiar_habilitacion_producto(LOCAL, AGUA, False)
    with pytest.raises(ReglaNegocioError, match="no está habilitado"):
        svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])


def test_sugerencia_descuenta_ordenes_abiertas_sin_contarlas_como_stock(svc):
    svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 10}])
    sugerencias = svc.sugerir_orden(LOCAL)
    assert next(item for item in sugerencias if item["producto_id"] == AGUA) == {
        "producto_id": AGUA, "nombre": "Agua 1.5L", "cantidad": 10,
    }
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_cancelar_orden_libera_reservas_y_registra_resolucion(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 5}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 5}])
    svc.precintar(bulto["id"])
    resultado = svc.resolver_orden(orden["id"], "CANCELAR", "Solicitud duplicada")
    assert resultado["estado"] == "CERRADA"
    assert resultado["resolucion"] == "CANCELADA"
    assert StockService().reservado(CD, AGUA) == 0


def test_rechazo_del_cd_notifica_al_local_y_la_notificacion_se_marca_leida(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    svc.resolver_orden(orden["id"], "RECHAZAR", "Sin disponibilidad")

    primera_lectura = svc.notificaciones(LOCAL)
    segunda_lectura = svc.notificaciones(LOCAL)

    assert primera_lectura[0]["evento"] == "ORDEN_RECHAZADA"
    assert "Sin disponibilidad" in primera_lectura[0]["mensaje"]
    assert primera_lectura[0]["leida"] == 0
    assert segunda_lectura[0]["leida"] == 1


def test_orden_pendiente_vencida_cancela_bultos_y_libera_stock(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 5}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 5}])
    BaseDeDatos().ejecutar(
        "UPDATE orden_reposicion SET fecha_vencimiento='2000-01-01 00:00:00' WHERE id=?",
        (orden["id"],))
    svc.procesar_vencimientos()
    orden_vencida = svc.obtener_orden(orden["id"])
    assert orden_vencida["resolucion"] == "VENCIDA"
    assert svc.obtener_bulto(bulto["id"]).estado == "ANULADO"
    assert StockService().reservado(CD, AGUA) == 0


def test_orden_proxima_a_vencer_avisa_al_local(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    BaseDeDatos().ejecutar(
        """UPDATE orden_reposicion SET fecha_vencimiento=
           datetime('now', 'localtime', '+12 hours') WHERE id=?""",
        (orden["id"],))

    svc.listar_ordenes()

    notificacion = svc.notificaciones(LOCAL)[0]
    assert notificacion["evento"] == "ORDEN_POR_VENCER"
    assert "24 horas" in notificacion["mensaje"]

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


def test_no_se_desactiva_local_con_bultos_en_transito(svc):
    armar_y_despachar(svc)

    with pytest.raises(ReglaNegocioError, match="bultos en tránsito"):
        CatalogoService().cambiar_estado_sucursal(LOCAL, False)


def test_sucursal_inactiva_no_recibe_ordenes_ni_despachos(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    svc.precintar(bulto["id"])
    CatalogoService().cambiar_estado_sucursal(LOCAL, False)

    with pytest.raises(ReglaNegocioError, match="sucursal inactiva"):
        svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError, match="sucursal inactiva"):
        svc.despachar(bulto["id"])


def test_sucursal_inactiva_no_registra_recepcion(svc):
    _, bulto = armar_y_despachar(svc)
    BaseDeDatos().ejecutar("UPDATE sucursal SET activo=0 WHERE id=?", (LOCAL,))

    with pytest.raises(ReglaNegocioError, match="sucursal inactiva"):
        svc.recibir(bulto["id"])


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
    """Veinte órdenes se atienden en FIFO sin comprometer más de 500 unidades."""
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

    for orden in ordenes:
        if orden["id"] in exitos:
            continue
        try:
            svc.crear_bulto(
                orden["id"], [{"producto_id": AGUA, "cantidad": 40}])
            exitos.append(orden["id"])
        except ReglaNegocioError:
            pass

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


def test_reabrir_bulto_precintado_anula_el_precinto_y_registra_nuevo_intento(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 2}])
    bulto = svc.crear_bulto(orden["id"], [{"producto_id": AGUA, "cantidad": 2}])
    precinto_anterior = svc.precintar(bulto["id"])["precinto"]

    reabierto = svc.reabrir_bulto(bulto["id"], "Corregir el embalaje")
    assert reabierto["estado"] == "PREPARADO"
    assert reabierto["precinto"] is None

    precinto_nuevo = svc.precintar(bulto["id"])["precinto"]
    assert precinto_nuevo != precinto_anterior
    historial = svc.historial(bulto["id"])
    assert "Precinto anterior anulado" in historial[2]["observacion"]
    assert historial[-1]["intento"] == 2


def test_no_se_reabre_un_bulto_despachado(svc):
    _, bulto = armar_y_despachar(svc)
    with pytest.raises(ReglaNegocioError, match="reabrir"):
        svc.reabrir_bulto(bulto["id"], "Cambiar el contenido")


def test_bulto_perdido_requiere_48_horas_y_no_se_suma_al_local(svc):
    _, bulto = armar_y_despachar(svc, 2)
    with pytest.raises(ReglaNegocioError, match="48 horas"):
        svc.marcar_perdido(bulto["id"], "Sin novedades")

    BaseDeDatos().ejecutar(
        """UPDATE bulto SET fecha_despacho=datetime('now', 'localtime', '-49 hours')
           WHERE id=?""", (bulto["id"],))
    perdido = svc.marcar_perdido(bulto["id"], "Sin novedades")
    assert perdido["estado"] == "PERDIDO"
    assert StockService().disponible(LOCAL, AGUA) == 0
