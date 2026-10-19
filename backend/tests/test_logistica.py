"""Correr desde backend/:   python -m pytest -v"""
import pytest
from sqlalchemy import delete, inspect
from sqlalchemy.exc import IntegrityError

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from models.contenedor import Contenedor
from models.contenedor import HistorialContenedor
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.excepciones import ReglaNegocioError

CD, LOCAL = 1, 2
AGUA, YERBA = 1, 3


@pytest.fixture
def svc(tmp_path):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "test.db"))
    cargar()
    logistica = LogisticaService()
    logistica.suscribir(StockObserver(StockService()))
    yield logistica
    BaseDeDatos.reiniciar()


def armar_y_despachar(svc, cantidad=10, precinto="P-1"):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": cantidad}])
    contenedor = svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": cantidad}])
    svc.precintar(contenedor["id"], precinto)
    svc.despachar(contenedor["id"])
    return orden, contenedor


def test_flujo_feliz_suma_stock_solo_al_verificar(svc):
    stock = StockService()
    orden, contenedor = armar_y_despachar(svc)
    assert stock.disponible(CD, AGUA) == 490          # salió del CD
    assert stock.disponible(LOCAL, AGUA) == 0         # en tránsito: no vendible

    svc.recibir(contenedor["id"], "P-1", precinto_intacto=True)
    assert stock.disponible(LOCAL, AGUA) == 10
    historial = svc.historial(contenedor["id"])
    estados = [h["estado"] for h in historial]
    assert estados == ["PREPARADO", "PRECINTADO", "EN_TRANSITO", "RECIBIDO", "VERIFICADO"]
    assert all(h["fecha"] for h in historial)
    assert all(len(h["fecha"]) == 19 for h in historial)


def test_precinto_roto_rechaza_y_no_habilita_venta(svc):
    _, contenedor = armar_y_despachar(svc)
    r = svc.recibir(contenedor["id"], "P-1", precinto_intacto=False)
    assert r["estado"] == "RECHAZADO"
    assert StockService().disponible(LOCAL, AGUA) == 0


def test_precinto_que_no_coincide_rechaza(svc):
    _, contenedor = armar_y_despachar(svc)
    assert svc.recibir(contenedor["id"], "OTRO", precinto_intacto=True)["estado"] == "RECHAZADO"


def test_remito_con_dos_contenedores_espera_a_ambos(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 5},
                                    {"producto_id": YERBA, "cantidad": 3}])
    b1 = svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": 5}])
    b2 = svc.crear_contenedor(orden["id"], [{"producto_id": YERBA, "cantidad": 3}])
    for b, p in ((b1, "A"), (b2, "B")):
        svc.precintar(b["id"], p); svc.despachar(b["id"])

    svc.recibir(b1["id"], "A", True)
    assert StockService().disponible(LOCAL, AGUA) == 0   # remito todavía no verificado
    svc.recibir(b2["id"], "B", False)                     # el segundo llega roto
    assert StockService().disponible(LOCAL, AGUA) == 5    # entra solo lo verificado
    assert StockService().disponible(LOCAL, YERBA) == 0


def test_no_se_puede_saltear_estados(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    contenedor = svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.despachar(contenedor["id"])          # sin precintar


def test_no_empaquetar_mas_de_lo_pedido(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 3}])
    with pytest.raises(ReglaNegocioError):
        svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": 4}])


def test_precinto_duplicado(svc):
    armar_y_despachar(svc, precinto="X")
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    b = svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": 1}])
    with pytest.raises(ReglaNegocioError):
        svc.precintar(b["id"], "X")


def test_despacho_sin_stock_en_cd_hace_rollback(svc):
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 999}])
    b = svc.crear_contenedor(orden["id"], [{"producto_id": AGUA, "cantidad": 999}])
    svc.precintar(b["id"], "Z")
    with pytest.raises(ReglaNegocioError):
        svc.despachar(b["id"])
    assert svc.obtener_contenedor(b["id"]).estado == "PRECINTADO"   # no quedó a medias


def test_historial_es_inmutable(svc):
    _, contenedor = armar_y_despachar(svc)
    with pytest.raises(IntegrityError):
        BaseDeDatos().sesion.execute(
            delete(HistorialContenedor).where(HistorialContenedor.contenedor_id == contenedor["id"])
        )


def test_esquema_usa_nombres_de_contenedor(svc):
    db = BaseDeDatos()
    tablas = set(inspect(db.engine).get_table_names())
    assert {"contenedor", "detalle_contenedor", "historial_contenedor"} <= tablas
    assert not {"bulto", "detalle_bulto", "historial_bulto"} & tablas
    orden = svc.crear_orden(LOCAL, [{"producto_id": AGUA, "cantidad": 1}])
    datos = svc.crear_contenedor(
        orden["id"], [{"producto_id": AGUA, "cantidad": 1}]
    )
    assert isinstance(db.sesion.get(Contenedor, datos["id"]), Contenedor)
    assert inspect(Contenedor).local_table.name == "contenedor"


def test_orden_a_cd_no_permitida(svc):
    with pytest.raises(ReglaNegocioError):
        svc.crear_orden(CD, [{"producto_id": AGUA, "cantidad": 1}])
