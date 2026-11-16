"""Stock mínimo de cada local, mínimo del CD (suma de locales como piso), alertas,
filtros/paginación de los listados y eliminación de "Mantener pendiente"."""
import pytest

from app import crear_app
from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from services.stock_service import StockService
from tests.ayudas import registrar_local_aprobado

CD, CENTRO, NUEVA_CBA = 1, 2, 3
AGUA = 1


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    BaseDeDatos.reiniciar()
    BaseDeDatos(str(tmp_path / "ux.db"))
    cargar(incluir_demo=False)
    app = crear_app(cargar_demo=False)
    app.config.update(TESTING=True)
    admin = app.test_client()
    registrar_local_aprobado(admin, "admin-centro@example.com", CENTRO)
    monkeypatch.setenv("CD_REGISTRATION_CODE", "codigo")
    cd = app.test_client()
    cd.post("/api/auth/register", json={"email": "cd@example.com", "password": "contraseña-segura",
                                         "sucursal_id": CD, "codigo_cd": "codigo"})
    yield app, admin, cd
    BaseDeDatos.reiniciar()


def minimo(sucursal_id, producto_id=AGUA):
    return BaseDeDatos().consultar_uno(
        "SELECT stock_minimo FROM minimo_vigente WHERE sucursal_id=? AND producto_id=?",
        (sucursal_id, producto_id))["stock_minimo"]


def alerta_abierta(sucursal_id, producto_id=AGUA):
    return BaseDeDatos().consultar_uno(
        "SELECT libre, minimo FROM alerta_stock WHERE sucursal_id=? AND producto_id=? AND resuelta=0",
        (sucursal_id, producto_id))


def cambiar_minimo(cliente, sucursal_id, valor, producto_id=AGUA):
    return cliente.patch(f"/api/sucursales/{sucursal_id}/productos/{producto_id}/minimo",
                         json={"stock_minimo": valor})


def cambiar_minimo_cd(cliente, cd_id, valor, producto_id=AGUA):
    return cliente.patch(f"/api/stock/{cd_id}/{producto_id}/minimo", json={"stock_minimo": valor})


def test_minimo_del_cd_es_la_suma_y_solo_puede_subirse(entorno):
    _, admin, cd = entorno
    otro = minimo(NUEVA_CBA)
    respuesta = cambiar_minimo(admin, CENTRO, 10)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["stock_minimo_local"] == 10
    assert minimo(NUEVA_CBA) == otro                 # el otro local no cambia
    assert minimo(CD) == 10 + otro                   # por defecto: suma de los locales

    suma = 10 + otro
    menor = cambiar_minimo_cd(cd, CD, suma - 1)      # no puede quedar por debajo
    assert menor.status_code == 400 and str(suma) in menor.get_json()["error"]
    r = cambiar_minimo_cd(cd, CD, suma + 30)         # sí puede subirlo
    assert r.status_code == 200 and r.get_json()["stock_minimo"] == suma + 30
    assert r.get_json()["minimo_locales"] == suma
    assert (minimo(CENTRO), minimo(NUEVA_CBA)) == (10, otro)   # los locales no cambian

    # Si los locales suben sus mínimos por encima del que puso el CD, manda la suma.
    cambiar_minimo(admin, CENTRO, 10 + 100)
    assert minimo(CD) == 110 + otro


def test_el_cd_no_toca_minimos_ajenos(entorno):
    _, admin, cd = entorno
    assert cambiar_minimo(cd, CENTRO, 5).status_code == 403          # mínimo de un local
    assert cambiar_minimo_cd(cd, 4, 5).status_code == 403            # otro CD (CD Norte)
    assert cambiar_minimo_cd(admin, CD, 5).status_code == 403        # un local no toca al CD
    assert cambiar_minimo_cd(cd, CD, -1).status_code == 400


def test_solo_el_administrador_configura_el_minimo(entorno):
    app, admin, cd = entorno
    empleado = app.test_client()
    registrar_local_aprobado(empleado, "empleado@example.com", CENTRO, rol="EMPLEADO")
    assert cambiar_minimo(empleado, CENTRO, 5).status_code == 403
    assert cambiar_minimo(cd, CENTRO, 5).status_code == 403
    assert cambiar_minimo(admin, NUEVA_CBA, 5).status_code == 403      # otro local
    assert cambiar_minimo(admin, CENTRO, -1).status_code == 400


def test_alertas_se_actualizan_con_minimo_venta_devolucion_y_habilitacion(entorno):
    _, admin, _ = entorno
    stock = StockService()
    stock.sumar(CENTRO, AGUA, 8, "APERTURA_TEST")
    cambiar_minimo(admin, CENTRO, 5)
    assert alerta_abierta(CENTRO) is None            # 8 libres >= 5

    cambiar_minimo(admin, CENTRO, 10)                # sube el mínimo -> alerta
    assert dict(alerta_abierta(CENTRO)) == {"libre": 8, "minimo": 10}

    venta = admin.post("/api/ventas", json={"sucursal_id": CENTRO, "medio_pago": "EFECTIVO",
                                            "items": [{"producto_id": AGUA, "cantidad": 3}]})
    assert venta.status_code == 201
    assert dict(alerta_abierta(CENTRO)) == {"libre": 5, "minimo": 10}   # venta actualiza

    devolucion = admin.post("/api/devoluciones", json={
        "venta_id": venta.get_json()["id"], "motivo": "fallado",
        "items": [{"producto_id": AGUA, "cantidad": 2}]})
    assert devolucion.status_code == 201
    assert dict(alerta_abierta(CENTRO)) == {"libre": 7, "minimo": 10}   # devolución actualiza

    cambiar_minimo(admin, CENTRO, 7)                 # baja el mínimo -> se resuelve
    assert alerta_abierta(CENTRO) is None


def test_alerta_del_cd_usa_la_suma_de_los_locales_o_su_minimo(entorno):
    _, admin, cd = entorno
    libre_cd = StockService().libre(CD, AGUA)
    otro = minimo(NUEVA_CBA)
    cambiar_minimo(admin, CENTRO, libre_cd - otro + 1)      # la suma supera el stock del CD
    alerta = alerta_abierta(CD)
    assert alerta is not None and alerta["minimo"] == libre_cd + 1
    alertas = cd.get("/api/alertas").get_json()
    assert any(a["sucursal"] == "CD Central" and a["minimo"] == libre_cd + 1 for a in alertas)
    cambiar_minimo(admin, CENTRO, 0)
    assert alerta_abierta(CD) is None
    cambiar_minimo_cd(cd, CD, libre_cd + 5)                 # el CD sube el suyo
    assert alerta_abierta(CD)["minimo"] == libre_cd + 5


def test_listado_de_ventas_paginado_filtrado_y_sin_repetidos(entorno):
    _, admin, _ = entorno
    StockService().sumar(CENTRO, AGUA, 50, "APERTURA_TEST")
    StockService().sumar(CENTRO, 2, 50, "APERTURA_TEST")
    ids = []
    for i in range(7):
        producto = AGUA if i % 2 == 0 else 2
        r = admin.post("/api/ventas", json={
            "sucursal_id": CENTRO, "medio_pago": "EFECTIVO" if i < 4 else "TRANSFERENCIA",
            "items": [{"producto_id": producto, "cantidad": 1}]})
        ids.append(r.get_json()["id"])

    pagina1 = admin.get("/api/ventas?pagina=1&por_pagina=3").get_json()
    pagina3 = admin.get("/api/ventas?pagina=3&por_pagina=3").get_json()
    assert pagina1["total"] == 7 and pagina1["paginas"] == 3
    assert pagina1["items"][0]["id"] == ids[-1]                   # la más nueva primero
    vistos = [v["id"] for p in (1, 2, 3)
              for v in admin.get(f"/api/ventas?pagina={p}&por_pagina=3").get_json()["items"]]
    assert sorted(vistos) == sorted(ids) and len(set(vistos)) == 7      # sin repetidos
    assert len(pagina3["items"]) == 1

    transferencias = admin.get("/api/ventas?pagina=1&medio_pago=TRANSFERENCIA").get_json()
    assert transferencias["total"] == 3
    combinado = admin.get("/api/ventas?pagina=1&medio_pago=TRANSFERENCIA&producto=AGU").get_json()
    assert combinado["total"] == 2                                # filtros combinados
    assert admin.get(f"/api/ventas?pagina=1&numero={ids[2]}").get_json()["items"][0]["id"] == ids[2]
    assert admin.get("/api/ventas").status_code == 200             # sin paginar: lista
    assert admin.get("/api/ventas?pagina=0").status_code == 400


def test_busqueda_parcial_de_productos_sin_mayusculas_ni_tildes(entorno):
    _, admin, cd = entorno
    resultado = admin.get(f"/api/sucursales/{CENTRO}/productos?pagina=1&q=YER").get_json()
    assert [p["nombre"] for p in resultado["items"]] == ["Yerba 1kg"]
    assert resultado["pagina"] == 1 and resultado["total"] == 1
    catalogo = cd.get("/api/productos?pagina=1&por_pagina=2").get_json()
    assert len(catalogo["items"]) == 2 and catalogo["total"] > 2
    assert cd.get("/api/productos?pagina=1&q=gaséosa").get_json()["total"] == 1


def test_stock_del_cd_muestra_proveedor_y_filtra(entorno):
    _, _, cd = entorno
    filas = cd.get(f"/api/stock/{CD}?pagina=1&por_pagina=50").get_json()["items"]
    assert all("proveedor" in f for f in filas)
    bajos = cd.get(f"/api/stock/{CD}?pagina=1&situacion=bajo").get_json()["items"]
    assert all(f["libre"] < f["stock_minimo"] for f in bajos)


def test_productos_y_stock_del_local_filtran_por_categoria_proveedor_y_estado(entorno):
    _, admin, _ = entorno
    todos = admin.get(f"/api/stock/{CENTRO}").get_json()
    assert all({"categoria", "proveedor", "stock_minimo_local", "habilitado"} <= f.keys()
               for f in todos)
    una = next(f for f in todos if f["categoria_id"] is not None)
    por_categoria = admin.get(
        f"/api/stock/{CENTRO}?pagina=1&categoria_id={una['categoria_id']}").get_json()["items"]
    assert por_categoria and all(f["categoria_id"] == una["categoria_id"] for f in por_categoria)
    con_proveedor = next(f for f in todos if f["proveedor_id"] is not None)
    por_proveedor = admin.get(
        f"/api/stock/{CENTRO}?pagina=1&proveedor_id={con_proveedor['proveedor_id']}").get_json()["items"]
    assert all(f["proveedor_id"] == con_proveedor["proveedor_id"] for f in por_proveedor)
    habilitados = admin.get(f"/api/stock/{CENTRO}?pagina=1&habilitado=1").get_json()["items"]
    assert all(f["habilitado"] == 1 for f in habilitados)
    assert all(f["activo"] for f in todos)          # el local no ve productos dados de baja


def test_ya_no_existe_mantener_pendiente(entorno):
    _, admin, cd = entorno
    orden = admin.post("/api/ordenes", json={"origen_id": CD, "destino_id": CENTRO,
                                             "items": [{"producto_id": AGUA, "cantidad": 2}]})
    assert orden.status_code == 201
    r = cd.post(f"/api/ordenes/{orden.get_json()['id']}/resolver", json={"accion": "ESPERAR"})
    assert r.status_code == 400
    listado = cd.get("/api/ordenes?pagina=1&estado_orden=PENDIENTE").get_json()
    assert listado["total"] == 1 and listado["items"][0]["unidades"] == 2


def test_recepciones_del_local(entorno):
    _, admin, cd = entorno
    orden = admin.post("/api/ordenes", json={"origen_id": CD, "destino_id": CENTRO,
                                             "items": [{"producto_id": AGUA, "cantidad": 2}]}).get_json()
    bulto = cd.post(f"/api/ordenes/{orden['id']}/bultos",
                    json={"items": [{"producto_id": AGUA, "cantidad": 2}]}).get_json()
    assert admin.get("/api/recepciones?pagina=1").get_json()["total"] == 0    # no despachado
    cd.post(f"/api/bultos/{bulto['id']}/precintar")
    cd.post(f"/api/bultos/{bulto['id']}/despachar")
    recepciones = admin.get("/api/recepciones?pagina=1").get_json()
    assert recepciones["total"] == 1
    assert recepciones["items"][0]["items"][0]["nombre"] == "Agua 1.5L"
    assert cd.get("/api/recepciones").status_code == 403
