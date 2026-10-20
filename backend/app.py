"""
API REST (Flask).  Ejecutar:  python app.py   ->  http://localhost:5000

Capas (igual que el repo de referencia, pero separadas en carpetas):
  routes (este archivo)  ->  services (reglas de negocio)  ->  database (Singleton)
                                    │
                                 models (clases del dominio)
"""
from flask import Flask, jsonify, request
from flask_cors import CORS

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar as cargar_datos_iniciales
from services.excepciones import ReglaNegocioError, NoEncontradoError
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.reportes_service import ReportesService
from services.observadores import AlertaStockMinimoObserver, AuditoriaObserver, AlertasService
from services.catalogo_service import CatalogoService


def crear_app():
    app = Flask(__name__)
    CORS(app)

    db = BaseDeDatos()
    cargar_datos_iniciales()

    # ---------- Patrón Observer: acá se conectan sujetos y observadores ----------
    stock = StockService()                            # sujeto 1
    stock.suscribir(AlertaStockMinimoObserver())

    logistica = LogisticaService(stock)               # sujeto 2 (comparte el mismo stock)
    logistica.suscribir(StockObserver(stock))
    logistica.suscribir(AuditoriaObserver())

    reportes = ReportesService()
    alertas = AlertasService()

    catalogo = CatalogoService()
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

    # ---------- ventas (TODO) ----------
    # @app.post("/api/ventas") ...  usar VentasService

    # ---------- reportes ----------
    @app.get("/api/reportes/bultos-rechazados")
    def rep_rechazados():
        return jsonify(reportes.bultos_rechazados(request.args.get("desde"),
                                                  request.args.get("hasta")))

    @app.get("/api/reportes/transito")
    def rep_transito():
        return jsonify(reportes.tiempo_promedio_transito())

    return app


if __name__ == "__main__":
    crear_app().run(debug=True, port=5000)
