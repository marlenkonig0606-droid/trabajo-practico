"""
API REST (Flask).  Ejecutar:  python app.py   ->  http://localhost:5000

Capas (igual que el repo de referencia, pero separadas en carpetas):
  routes (este archivo)  ->  services (reglas de negocio)  ->  database (Singleton)
                                    │
                                 models (clases del dominio)
"""
from flask import Flask, jsonify, request
from flask_cors import CORS

from database.datos_iniciales import cargar as cargar_datos_iniciales
from services.excepciones import ReglaNegocioError, NoEncontradoError
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.reportes_service import ReportesService
from services.observadores import AlertaStockMinimoObserver, AuditoriaObserver, AlertasService
from services.ventas_service import VentasService
from services.catalogo_service import CatalogoService


def crear_app():
    app = Flask(__name__)
    CORS(app)

    cargar_datos_iniciales()

    # ---------- Patrón Observer: acá se conectan sujetos y observadores ----------
    stock = StockService()                            # sujeto 1
    stock.suscribir(AlertaStockMinimoObserver())

    logistica = LogisticaService(stock)               # sujeto 2 (comparte el mismo stock)
    logistica.suscribir(StockObserver(stock))
    logistica.suscribir(AuditoriaObserver())

    reportes = ReportesService()
    alertas = AlertasService()
    ventas = VentasService(stock)
    catalogo = CatalogoService()

    def cuerpo_json():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")
        return datos

    def entero_positivo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise ReglaNegocioError(f"{campo} debe ser un entero positivo")
        return valor

    # ---------- manejo de errores centralizado ----------
    @app.errorhandler(ReglaNegocioError)
    def regla_negocio(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(NoEncontradoError)
    def no_encontrado(e):
        return jsonify({"error": str(e)}), 404

    @app.errorhandler(NotImplementedError)
    def no_implementado(e):
        return jsonify({"error": f"Pendiente: {e}"}), 501

    # ---------- catálogo (procesos 1 y 2) ----------
    # Sucursales
    @app.get("/api/sucursales")
    def listar_sucursales():
        return jsonify(catalogo.listar_sucursales())

    @app.get("/api/sucursales/<int:id_sucursal>")
    def obtener_sucursal(id_sucursal):
        return jsonify(catalogo.obtener_sucursal(id_sucursal))

    @app.post("/api/sucursales")
    def crear_sucursal():
        return jsonify(catalogo.crear_sucursal(request.get_json())), 201

    @app.put("/api/sucursales/<int:id_sucursal>")
    def actualizar_sucursal(id_sucursal):
        return jsonify(catalogo.actualizar_sucursal(id_sucursal, request.get_json()))

    @app.delete("/api/sucursales/<int:id_sucursal>")
    def eliminar_sucursal(id_sucursal):
        catalogo.eliminar_sucursal(id_sucursal)
        return "", 204

    # Productos
    @app.get("/api/productos")
    def listar_productos():
        return jsonify(catalogo.listar_productos())

    @app.get("/api/productos/<int:id_producto>")
    def obtener_producto(id_producto):
        return jsonify(catalogo.obtener_producto(id_producto))

    @app.post("/api/productos")
    def crear_producto():
        return jsonify(catalogo.crear_producto(request.get_json())), 201

    @app.put("/api/productos/<int:id_producto>")
    def actualizar_producto(id_producto):
        return jsonify(catalogo.actualizar_producto(id_producto, request.get_json()))

    @app.delete("/api/productos/<int:id_producto>")
    def eliminar_producto(id_producto):
        catalogo.eliminar_producto(id_producto)
        return "", 204

    # Categorías
    @app.get("/api/categorias")
    def listar_categorias():
        return jsonify(catalogo.listar_categorias())

    @app.post("/api/categorias")
    def crear_categoria():
        return jsonify(catalogo.crear_categoria(request.get_json())), 201

    @app.put("/api/categorias/<int:id_categoria>")
    def actualizar_categoria(id_categoria):
        return jsonify(catalogo.actualizar_categoria(id_categoria, request.get_json()))

    @app.delete("/api/categorias/<int:id_categoria>")
    def eliminar_categoria(id_categoria):
        catalogo.eliminar_categoria(id_categoria)
        return "", 204

    # Proveedores
    @app.get("/api/proveedores")
    def listar_proveedores():
        return jsonify(catalogo.listar_proveedores())

    @app.post("/api/proveedores")
    def crear_proveedor():
        return jsonify(catalogo.crear_proveedor(request.get_json())), 201

    @app.put("/api/proveedores/<int:id_proveedor>")
    def actualizar_proveedor(id_proveedor):
        return jsonify(catalogo.actualizar_proveedor(id_proveedor, request.get_json()))

    @app.delete("/api/proveedores/<int:id_proveedor>")
    def eliminar_proveedor(id_proveedor):
        catalogo.eliminar_proveedor(id_proveedor)
        return "", 204

    @app.get("/api/stock/<int:sucursal_id>")
    def ver_stock(sucursal_id):
        return jsonify(stock.listar(sucursal_id))

    # ---------- logística ----------
    @app.get("/api/ordenes")
    def listar_ordenes():
        return jsonify(logistica.listar_ordenes())

    @app.get("/api/sucursales/<int:local_id>/sugerencia")
    def sugerir_orden(local_id):
        return jsonify(logistica.sugerir_orden(local_id))


    @app.post("/api/ordenes")
    def crear_orden():
        d = request.get_json()
        return jsonify(logistica.crear_orden(d["destino_id"], d["items"])), 201

    @app.post("/api/ordenes/<int:orden_id>/bultos")
    def crear_bulto(orden_id):
        return jsonify(logistica.crear_bulto(orden_id, request.get_json()["items"])), 201

    @app.post("/api/bultos/<int:bulto_id>/precintar")
    def precintar(bulto_id):
        return jsonify(logistica.precintar(bulto_id, request.get_json().get("precinto")))

    @app.post("/api/bultos/<int:bulto_id>/despachar")
    def despachar(bulto_id):
        return jsonify(logistica.despachar(bulto_id))

    @app.post("/api/bultos/<int:bulto_id>/anular")
    def anular(bulto_id):
        motivo = request.get_json().get("motivo")
        return jsonify(logistica.anular_bulto(bulto_id, motivo))

    @app.post("/api/bultos/<int:bulto_id>/recibir")
    def recibir(bulto_id):
        d = request.get_json()
        return jsonify(logistica.recibir(bulto_id, d.get("precinto"), bool(d.get("intacto"))))

    @app.get("/api/bultos/<int:bulto_id>/historial")
    def historial(bulto_id):
        return jsonify(logistica.historial(bulto_id))

    # ---------- lo que registran los observadores ----------
    @app.get("/api/alertas")
    def listar_alertas():
        return jsonify(alertas.alertas(solo_pendientes=request.args.get("todas") is None))

    @app.get("/api/eventos")
    def listar_eventos():
        return jsonify(alertas.eventos())

    # ---------- ventas y devoluciones ----------
    @app.get("/api/ventas")
    def listar_ventas():
        return jsonify(ventas.listar_ventas())

    @app.get("/api/ventas/<int:venta_id>")
    def obtener_venta(venta_id):
        return jsonify(ventas.obtener_venta(venta_id))

    @app.post("/api/ventas")
    def registrar_venta():
        datos = cuerpo_json()
        sucursal_id = entero_positivo(datos.get("sucursal_id"), "sucursal_id")
        items = datos.get("items")
        if not isinstance(items, list):
            raise ReglaNegocioError("items debe ser una lista")
        medio_pago = datos.get("medio_pago")
        if not isinstance(medio_pago, str) or not medio_pago.strip():
            raise ReglaNegocioError("medio_pago es obligatorio")
        datos_pago = {
            clave: datos[clave]
            for clave in ("cuotas", "referencia")
            if clave in datos
        }
        return jsonify(
            ventas.registrar_venta(sucursal_id, items, medio_pago, **datos_pago)
        ), 201

    @app.post("/api/devoluciones")
    def registrar_devolucion():
        datos = cuerpo_json()
        venta_id = entero_positivo(datos.get("venta_id"), "venta_id")
        items = datos.get("items")
        if not isinstance(items, list):
            raise ReglaNegocioError("items debe ser una lista")
        return jsonify(
            ventas.registrar_devolucion(venta_id, items, datos.get("motivo"))
        ), 201

    # ---------- reportes ----------
    @app.get("/api/reportes/bultos-rechazados")
    def rep_rechazados():
        return jsonify(reportes.bultos_rechazados(request.args.get("desde"),
                                                  request.args.get("hasta")))

    @app.get("/api/reportes/transito")
    def rep_transito():
        return jsonify(reportes.tiempo_promedio_transito())

    @app.get("/api/reportes/existencias")
    def rep_existencias():
        return jsonify(reportes.existencias())

    @app.get("/api/reportes/movimientos")
    def rep_movimientos():
        return jsonify(reportes.movimientos())

    @app.get("/api/reportes/ventas")
    def rep_ventas():
        return jsonify(reportes.ventas(request.args.get("desde"), request.args.get("hasta")))

    @app.get("/api/reportes/mas-vendidos")
    def rep_mas_vendidos():
        return jsonify(reportes.mas_vendidos(request.args.get("desde"), request.args.get("hasta")))

    return app


if __name__ == "__main__":
    crear_app().run(debug=True, port=5000)
