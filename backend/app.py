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

    # ---------- catálogo (solo lectura por ahora) ----------
    @app.get("/api/sucursales")
    def listar_sucursales():
        return jsonify(db.consultar("SELECT * FROM sucursal ORDER BY tipo, nombre"))

    @app.get("/api/productos")
    def listar_productos():
        return jsonify(db.consultar("SELECT * FROM producto ORDER BY nombre"))

    # TODO (vos): POST/PUT/DELETE de sucursales, productos, categorías y proveedores
    #   (procesos 1 y 2). Validar duplicados por codigo / cuit -> ReglaNegocioError.

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
