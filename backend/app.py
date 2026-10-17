"""
API REST (Flask).  Ejecutar:  python app.py   ->  http://localhost:5000

Capas (igual que el repo de referencia, pero separadas en carpetas):
  routes (este archivo)  ->  services (reglas de negocio)  ->  database (Singleton)
                                    │
                                 models (clases del dominio)
"""
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import select

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar as cargar_datos_iniciales
from models.orm import ProductoORM, SucursalORM
from services.excepciones import ReglaNegocioError, NoEncontradoError
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.reportes_service import ReportesService


def crear_app():
    app = Flask(__name__)
    CORS(app)

    db = BaseDeDatos()
    cargar_datos_iniciales()

    stock = StockService()
    logistica = LogisticaService()
    logistica.suscribir(StockObserver(stock))      # <- Observer conectado acá
    reportes = ReportesService()

    # ---------- manejo de errores centralizado ----------
    @app.errorhandler(NoEncontradoError)
    @app.errorhandler(ReglaNegocioError)
    def regla_negocio(e):
        return jsonify({"error": str(e), "solucion": e.mensaje_especial}), e.status_code


    @app.errorhandler(NotImplementedError)
    def no_implementado(e):
        return jsonify({"error": f"Pendiente: {e}"}), 501

    # ---------- catálogo (solo lectura por ahora) ----------
    @app.get("/api/sucursales")
    def listar_sucursales():
        sucursales = db.sesion.scalars(
            select(SucursalORM).order_by(SucursalORM.tipo, SucursalORM.nombre)
        )
        return jsonify([
            {
                "id": sucursal.id,
                "nombre": sucursal.nombre,
                "direccion": sucursal.direccion,
                "tipo": sucursal.tipo,
            }
            for sucursal in sucursales
        ])

    @app.get("/api/productos")
    def listar_productos():
        productos = db.sesion.scalars(
            select(ProductoORM).order_by(ProductoORM.nombre)
        )
        return jsonify([
            {
                "id": producto.id,
                "codigo": producto.codigo,
                "nombre": producto.nombre,
                "categoria_id": producto.categoria_id,
                "proveedor_id": producto.proveedor_id,
                "precio_costo": producto.precio_costo,
                "precio_venta": producto.precio_venta,
                "stock_minimo": producto.stock_minimo,
            }
            for producto in productos
        ])

    # TODO (vos): POST/PUT/DELETE de sucursales, productos, categorías y proveedores
    #   (procesos 1 y 2). Validar duplicados por codigo / cuit -> ReglaNegocioError.

    @app.get("/api/stock/<int:sucursal_id>")
    def ver_stock(sucursal_id):
        return jsonify(stock.listar(sucursal_id))

    # ---------- logística ----------
    @app.get("/api/ordenes")
    def listar_ordenes():
        return jsonify(logistica.listar_ordenes())

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

    @app.teardown_appcontext
    def limpiar_sesion(_error=None):
        db.limpiar_sesion()

    return app


if __name__ == "__main__":
    crear_app().run(debug=True, port=5000)
