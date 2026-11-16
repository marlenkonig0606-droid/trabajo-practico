"""Reporte del centro de distribución: resultado, ventas por local y producto,
pedidos completos/incompletos y estacionalidad, con datos conocidos."""
import pytest

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.logistica_service import LogisticaService
from services.observadores import StockObserver
from services.reportes_service import ReportesService
from services.stock_service import StockService
from services.ventas_service import VentasService
from tests.test_reportes_local import fechar_venta

CENTRO, NUEVA_CBA = 2, 3


@pytest.fixture
def red(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "reportes_cd.db"))
    cargar(incluir_demo=False)
    stock = StockService()
    for local in (CENTRO, NUEVA_CBA):
        for producto in (1, 2, 3):
            stock.sumar(local, producto, 100, "APERTURA_TEST")
    for producto in (1, 2, 3):
        stock.sumar(1, producto, 500, "APERTURA_TEST")
    ventas = VentasService(stock)
    # precios: 1=Agua 700, 2=Gaseosa 1900, 3=Yerba 3800
    datos = [
        (CENTRO, "2025-01-10 10:00:00", [(1, 10)]),
        (CENTRO, "2025-07-10 10:00:00", [(3, 2)]),
        (NUEVA_CBA, "2025-01-15 10:00:00", [(1, 4), (2, 1)]),
        (NUEVA_CBA, "2024-05-01 10:00:00", [(3, 9)]),          # otro año
    ]
    for local, fecha, items in datos:
        venta = ventas.registrar_venta(
            local, [{"producto_id": p, "cantidad": c} for p, c in items], "EFECTIVO")
        fechar_venta(venta["id"], fecha)
    logistica = LogisticaService(stock)
    logistica.suscribir(StockObserver(stock))
    yield ReportesService(), stock, logistica
    BaseDeDatos.reiniciar()


def _costos():
    db = BaseDeDatos()
    return {p["id"]: p["precio_costo"] for p in db.consultar("SELECT id, precio_costo FROM producto")}


def test_resultado_es_ventas_menos_costo(red):
    reportes, _, _ = red
    costo = _costos()
    r = reportes.reporte_cd(anio=2025)["resultado"]
    ingresos = 10 * 700 + 2 * 3800 + 4 * 700 + 1900
    costo_vendido = 14 * costo[1] + 2 * costo[3] + 1 * costo[2]
    assert r["ingresos_netos"] == ingresos
    assert r["costo_vendido"] == round(costo_vendido, 2)
    assert r["resultado"] == round(ingresos - costo_vendido, 2)
    assert r["es_ganancia"] is True
    assert len(r["mensual"]) == 12
    assert sum(m["resultado"] for m in r["mensual"]) == pytest.approx(r["resultado"])


def test_bulto_perdido_puede_dejar_perdida(red):
    reportes, _, logistica = red
    orden = logistica.crear_orden(CENTRO, [{"producto_id": 3, "cantidad": 300}], 1)
    bulto = logistica.crear_bulto(orden["id"], [{"producto_id": 3, "cantidad": 300}])
    logistica.precintar(bulto["id"])
    logistica.despachar(bulto["id"])
    db = BaseDeDatos()
    with db.transaccion():          # pasaron más de 48 h sin que llegue
        db.ejecutar("UPDATE bulto SET fecha_despacho='2025-03-01 10:00:00' WHERE id=?",
                    (bulto["id"],))
    logistica.marcar_perdido(bulto["id"], "Robo en ruta")
    r = reportes.reporte_cd()["resultado"]              # todo el historial
    assert r["bultos_perdidos"] == 1
    assert r["perdidas_transito"] == 300 * _costos()[3]
    assert r["es_ganancia"] is False and r["resultado"] < 0


def test_ventas_por_local_y_top(red):
    reportes, _, _ = red
    r = reportes.reporte_cd(anio=2025)
    locales = {f["local"]: f for f in r["ventas_por_local"]}
    assert locales["Local Centro"]["facturado"] == 7000 + 7600
    assert locales["Local Centro"]["ventas"] == 2
    assert locales["Local Nueva Córdoba"]["facturado"] == 2800 + 1900
    assert round(sum(f["participacion"] for f in r["ventas_por_local"])) == 100
    top = r["productos"]["top"]
    assert top[0]["producto"] == "Agua 1.5L" and top[0]["unidades"] == 14
    agua = {x["local"]: x["unidades"] for x in top[0]["por_local"]}
    assert agua == {"Local Centro": 10, "Local Nueva Córdoba": 4}


def test_estacionalidad_marca_el_mes_pico(red):
    reportes, _, _ = red
    e = reportes.reporte_cd(anio=2025)["estacionalidad"]
    agua = next(p for p in e["productos"] if p["producto"] == "Agua 1.5L")
    assert agua["valores"][0] == 14 and sum(agua["valores"]) == 14
    assert agua["mes_pico"] == "2025-01"


def test_pedidos_completos_incompletos_y_en_curso(red):
    reportes, _, logistica = red
    # 1) completo
    o1 = logistica.crear_orden(CENTRO, [{"producto_id": 1, "cantidad": 10}], 1)
    b1 = logistica.crear_bulto(o1["id"], [{"producto_id": 1, "cantidad": 10}])
    for paso in (logistica.precintar, logistica.despachar, logistica.recibir):
        paso(b1["id"])
    logistica.verificar_recepcion(b1["id"], True)
    # 2) incompleto: el local rechazó el bulto
    o2 = logistica.crear_orden(NUEVA_CBA, [{"producto_id": 2, "cantidad": 5}], 1)
    b2 = logistica.crear_bulto(o2["id"], [{"producto_id": 2, "cantidad": 5}])
    for paso in (logistica.precintar, logistica.despachar, logistica.recibir):
        paso(b2["id"])
    logistica.verificar_recepcion(b2["id"], False, "Precinto dañado")
    # 3) incompleto: rechazada por el CD
    o3 = logistica.crear_orden(NUEVA_CBA, [{"producto_id": 1, "cantidad": 3}], 1)
    logistica.resolver_orden(o3["id"], "RECHAZAR", "Sin capacidad")
    # 4) en curso
    logistica.crear_orden(CENTRO, [{"producto_id": 3, "cantidad": 2}], 1)

    p = reportes.reporte_cd()["pedidos"]
    assert (p["total"], p["completos"], p["incompletos"], p["en_curso"]) == (4, 1, 2, 1)
    assert p["cumplimiento_pct"] == round(100 / 3, 1)
    assert p["unidades_faltantes"] == 5 + 3
    causas = {c["causa"]: c["pedidos"] for c in p["causas"]}
    assert causas["Rechazada por el CD"] == 1
    por_local = {f["local"]: f for f in p["por_local"]}
    assert por_local["Local Centro"]["pedidos"] == 2
    assert por_local["Local Nueva Córdoba"]["incompletos"] == 2
    # Filtrar por un CD que no atendió nada deja la sección vacía.
    assert reportes.reporte_cd(cd_id=999)["pedidos"]["total"] == 0
