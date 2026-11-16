"""Reporte gerencial del local: cálculos con datos conocidos."""
import statistics

import pytest

from app import crear_app
from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.analisis import estadistica_tickets, periodos_con_stock, resumen_permanencia
from services.logistica_service import LogisticaService
from services.observadores import StockObserver
from services.reportes_service import ReportesService
from services.stock_service import StockService
from services.ventas_service import VentasService
from tests.ayudas import registrar_local_aprobado


def fechar_venta(venta_id, fecha):
    db = BaseDeDatos()
    with db.transaccion():
        db.ejecutar("UPDATE venta SET fecha=? WHERE id=?", (fecha, venta_id))


@pytest.fixture
def local_con_ventas(tmp_path):
    """Local Centro (id 2) con 4 ventas en 2025 y 1 en 2024."""
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "reportes_local.db"))
    cargar(incluir_demo=False)
    stock = StockService()
    for producto in (1, 2, 3):
        stock.sumar(2, producto, 100, "APERTURA_TEST")
    ventas = VentasService(stock)
    # (fecha, items, medio)  precios: 1=Agua 700, 2=Gaseosa 1900, 3=Yerba 3800
    datos = [
        ("2025-03-10 10:00:00", [(1, 2)], "TARJETA_DEBITO"),           # 1400
        ("2025-03-20 11:00:00", [(3, 1)], "TRANSFERENCIA"),            # 3800
        ("2025-07-05 12:00:00", [(1, 1), (2, 2)], "TARJETA_DEBITO"),   # 4500
        ("2025-07-06 12:00:00", [(1, 5)], "TRANSFERENCIA"),            # 3500
        ("2024-12-31 18:00:00", [(3, 3)], "TARJETA_DEBITO"),           # 11400 (otro año)
    ]
    for fecha, items, medio in datos:
        venta = ventas.registrar_venta(
            2, [{"producto_id": p, "cantidad": c} for p, c in items], medio)
        fechar_venta(venta["id"], fecha)
    yield ReportesService()
    BaseDeDatos.reiniciar()


def test_resumen_por_anio_y_ticket_promedio(local_con_ventas):
    r = local_con_ventas.reporte_local(2, anio=2025)
    resumen = r["resumen"]
    assert resumen["ventas"] == 4                       # la de 2024 no entra
    assert resumen["facturado"] == 1400 + 3800 + 4500 + 3500
    assert resumen["ticket_promedio"] == round(13200 / 4, 2)
    assert resumen["unidades"] == 2 + 1 + 3 + 5
    assert len(resumen["mensual"]) == 12                # los 12 meses, aunque estén en 0
    marzo = next(m for m in resumen["mensual"] if m["mes"] == "2025-03")
    assert (marzo["ventas"], marzo["facturado"], marzo["ticket_promedio"]) == (2, 5200, 2600)
    enero = next(m for m in resumen["mensual"] if m["mes"] == "2025-01")
    assert enero["ticket_promedio"] is None             # sin ventas no hay ticket
    assert resumen["mes_mayor_facturacion"]["mes"] == "2025-07"
    assert r["periodo"]["desde"] == "2025-01-01" and r["periodo"]["hasta"] == "2025-12-31"


def test_medios_de_pago_coinciden_con_los_registros(local_con_ventas):
    r = local_con_ventas.reporte_local(2, anio=2025)
    medios = {m["medio_pago"]: m for m in r["medios_pago"]}
    assert medios["TARJETA_DEBITO"]["ingresos"] == 1400 + 4500
    assert medios["TRANSFERENCIA"]["ingresos"] == 3800 + 3500
    assert sum(m["ingresos"] for m in r["medios_pago"]) == r["resumen"]["facturado"]
    assert round(sum(m["porcentaje"] for m in r["medios_pago"])) == 100


def test_ranking_de_productos_y_periodo_personalizado(local_con_ventas):
    r = local_con_ventas.reporte_local(2, anio=2025)
    assert [p["producto"] for p in r["productos"]["ranking"]] == [
        "Agua 1.5L", "Gaseosa cola 2L", "Yerba 1kg"]
    assert r["productos"]["ranking"][0]["unidades"] == 8
    solo_marzo = local_con_ventas.reporte_local(2, "2025-03-01", "2025-03-31")
    assert solo_marzo["resumen"]["ventas"] == 2
    assert solo_marzo["periodo"]["meses"] == ["2025-03"]


def test_sin_bultos_la_relacion_ventas_por_bulto_no_esta_disponible(local_con_ventas):
    r = local_con_ventas.reporte_local(2, anio=2025)
    assert r["logistica"]["bultos"] == 0
    assert r["logistica"]["ventas_por_bulto"] is None


def test_logistica_cuenta_pedidos_bultos_y_relacion(local_con_ventas):
    stock = StockService()
    logistica = LogisticaService(stock)
    logistica.suscribir(StockObserver(stock))
    orden = logistica.crear_orden(2, [{"producto_id": 1, "cantidad": 10}], 1)
    bulto = logistica.crear_bulto(orden["id"], [{"producto_id": 1, "cantidad": 10}])
    logistica.precintar(bulto["id"])
    logistica.despachar(bulto["id"])
    logistica.recibir(bulto["id"])
    logistica.verificar_recepcion(bulto["id"], True)

    hoy = local_con_ventas.reporte_local(2)               # todo el historial
    assert hoy["logistica"]["pedidos"] == 1
    assert hoy["logistica"]["bultos"] == 1
    assert hoy["logistica"]["ventas_por_bulto"] == 5.0    # 5 ventas / 1 bulto
    assert hoy["logistica"]["por_cd"][0]["cd"] == "CD Central"
    assert hoy["ordenes"]["entregadas"] == 1
    assert hoy["ordenes"]["transito_horas_promedio"] is not None


def test_estadistica_detecta_atipicos_y_no_asume_normalidad():
    importes = [1000, 1100, 1200, 1300, 1250, 1150, 1050, 1180, 1220, 9000]
    e = estadistica_tickets(importes)
    assert e["media"] == round(statistics.fmean(importes), 2)
    assert e["mediana"] == statistics.median(importes)
    assert e["atipicos_altos"] == 1                      # el ticket de 9000
    assert e["aproximacion_normal"] is False
    assert e["curva_normal"] == []
    assert sum(c["cantidad"] for c in e["histograma"]) == len(importes)


def test_estadistica_superpone_la_normal_cuando_corresponde():
    distribucion = statistics.NormalDist(5000, 800)
    importes = [distribucion.inv_cdf((i + 0.5) / 60) for i in range(60)]
    e = estadistica_tickets(importes)
    assert e["aproximacion_normal"] is True
    assert len(e["curva_normal"]) > 0
    assert estadistica_tickets([500])["suficiente"] is False


def test_permanencia_se_reconstruye_con_los_movimientos():
    movimientos = [
        {"producto_id": 1, "producto": "Agua", "fecha": "2025-01-01 10:00:00", "cantidad": 10},
        {"producto_id": 1, "producto": "Agua", "fecha": "2025-01-04 10:00:00", "cantidad": -10},
        {"producto_id": 1, "producto": "Agua", "fecha": "2025-01-10 10:00:00", "cantidad": 5},
        {"producto_id": 2, "producto": "Yerba", "fecha": "2025-01-01 10:00:00", "cantidad": 3},
    ]
    from datetime import datetime
    periodos = periodos_con_stock(movimientos, ahora=datetime(2025, 1, 20, 10))
    agua = [p for p in periodos if p["producto"] == "Agua"]
    cerrado = next(p for p in agua if not p["sigue_en_stock"])
    assert cerrado["dias"] == 3.0 and cerrado["salida"] == "2025-01-04 10:00"
    assert any(p["sigue_en_stock"] and p["dias"] == 10.0 for p in agua)
    resumen = resumen_permanencia(periodos)
    assert resumen["se_agotan_rapido"][0]["producto"] == "Agua"
    assert resumen["por_producto"][0]["producto"] == "Yerba"   # 19 días seguidos
    # Filtrar por período deja afuera lo que terminó antes.
    assert not [p for p in periodos_con_stock(movimientos, desde="2025-01-05",
                                              ahora=datetime(2025, 1, 20, 10))
                if not p["sigue_en_stock"]]


def test_ruta_del_reporte_valida_rol_y_anio(local_con_ventas, monkeypatch):
    app = crear_app(cargar_demo=False)
    app.config.update(TESTING=True)
    admin = app.test_client()
    registrar_local_aprobado(admin, "gerente@example.com", 2)
    ok = admin.get("/api/reportes/local?anio=2025")
    assert ok.status_code == 200 and ok.get_json()["resumen"]["ventas"] == 4
    assert admin.get("/api/reportes/local?anio=1990").status_code == 400
    assert admin.get("/api/reportes/local?desde=2025-03-01&hasta=2025-03-31") \
        .get_json()["resumen"]["ventas"] == 2

    empleado = app.test_client()
    registrar_local_aprobado(empleado, "empleado@example.com", 2, rol="EMPLEADO")
    assert empleado.get("/api/reportes/local").status_code == 403

    monkeypatch.setenv("CD_REGISTRATION_CODE", "codigo")
    cd = app.test_client()
    cd.post("/api/auth/register", json={"email": "cd@example.com",
            "password": "contraseña-segura", "sucursal_id": 1, "codigo_cd": "codigo"})
    # El CD puede ver el reporte de cualquier local, pero tiene que elegir cuál.
    assert cd.get("/api/reportes/local").status_code == 400
    assert cd.get("/api/reportes/local?sucursal_id=1").status_code == 400   # es un CD
    visto_por_cd = cd.get("/api/reportes/local?anio=2025&sucursal_id=2")
    assert visto_por_cd.status_code == 200
    assert visto_por_cd.get_json()["resumen"]["ventas"] == 4
    # Un local no puede espiar a otro: el parámetro se ignora.
    assert admin.get("/api/reportes/local?anio=2025&sucursal_id=3").get_json()["resumen"]["ventas"] == 4
    # Y el reporte de la red es solo para el CD.
    assert admin.get("/api/reportes/cd").status_code == 403
    assert cd.get("/api/reportes/cd?anio=2025").status_code == 200


def test_campana_de_referencia_sin_atipicos():
    importes = [1000 + (i % 7) * 150 for i in range(40)] + [20000, 25000]
    e = estadistica_tickets(importes)
    central = e["central"]
    assert central["excluidos"] == 2                      # los atípicos quedan aparte
    assert central["n"] == 40
    assert len(central["curva_normal"]) > 0               # siempre se dibuja la referencia
    assert sum(c["cantidad"] for c in central["histograma"]) == 40
    assert all(p["x"] >= 0 for p in central["curva_normal"])
