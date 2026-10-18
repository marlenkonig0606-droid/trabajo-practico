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
from models.orm import SucursalORM
from services.catalogo_service import CatalogoService
from services.excepciones import ReglaNegocioError, NoEncontradoError
from services.logistica_service import LogisticaService
from services.productos_service import ProductosService
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
    productos_service = ProductosService()
    catalogo_service = CatalogoService()

    # ---------- manejo de errores centralizado ----------
    @app.errorhandler(NoEncontradoError)
    @app.errorhandler(ReglaNegocioError)
    def regla_negocio(e):
        return jsonify({"error": str(e), "solucion": e.mensaje_especial}), e.status_code


    @app.errorhandler(NotImplementedError)
    def no_implementado(e):
        return jsonify({"error": f"Pendiente: {e}"}), 501

    # ---------- catálogo ----------
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
        return jsonify(productos_service.listar())

    @app.get("/api/productos/<int:producto_id>")
    def obtener_producto(producto_id):
        return jsonify(productos_service.obtener(producto_id))

    @app.post("/api/productos")
    def crear_producto():
        return jsonify(productos_service.crear(request.get_json())), 201

    @app.put("/api/productos/<int:producto_id>")
    def actualizar_producto(producto_id):
        return jsonify(productos_service.actualizar(producto_id, request.get_json()))

    @app.patch("/api/productos/<int:producto_id>")
    def actualizar_parcial_producto(producto_id):
        return jsonify(productos_service.actualizar(
            producto_id, request.get_json(), parcial=True
        ))

    @app.delete("/api/productos/<int:producto_id>")
    def eliminar_producto(producto_id):
        return jsonify(productos_service.eliminar(producto_id))

    @app.get("/api/categorias")
    def listar_categorias():
        return jsonify(catalogo_service.listar_categorias())

    @app.get("/api/categorias/<int:categoria_id>")
    def obtener_categoria(categoria_id):
        return jsonify(catalogo_service.obtener_categoria(categoria_id))

    @app.post("/api/categorias")
    def crear_categoria():
        return jsonify(catalogo_service.crear_categoria(request.get_json())), 201

    @app.put("/api/categorias/<int:categoria_id>")
    def actualizar_categoria(categoria_id):
        return jsonify(catalogo_service.actualizar_categoria(
            categoria_id, request.get_json()
        ))

    @app.patch("/api/categorias/<int:categoria_id>")
    def actualizar_parcial_categoria(categoria_id):
        return jsonify(catalogo_service.actualizar_categoria(
            categoria_id, request.get_json(), parcial=True
        ))

    @app.delete("/api/categorias/<int:categoria_id>")
    def eliminar_categoria(categoria_id):
        return jsonify(catalogo_service.eliminar_categoria(categoria_id))

    @app.get("/api/proveedores")
    def listar_proveedores():
        return jsonify(catalogo_service.listar_proveedores())

    @app.get("/api/proveedores/<int:proveedor_id>")
    def obtener_proveedor(proveedor_id):
        return jsonify(catalogo_service.obtener_proveedor(proveedor_id))

    @app.post("/api/proveedores")
    def crear_proveedor():
        return jsonify(catalogo_service.crear_proveedor(request.get_json())), 201

    @app.put("/api/proveedores/<int:proveedor_id>")
    def actualizar_proveedor(proveedor_id):
        return jsonify(catalogo_service.actualizar_proveedor(
            proveedor_id, request.get_json()
        ))

    @app.patch("/api/proveedores/<int:proveedor_id>")
    def actualizar_parcial_proveedor(proveedor_id):
        return jsonify(catalogo_service.actualizar_proveedor(
            proveedor_id, request.get_json(), parcial=True
        ))

    @app.delete("/api/proveedores/<int:proveedor_id>")
    def eliminar_proveedor(proveedor_id):
        return jsonify(catalogo_service.eliminar_proveedor(proveedor_id))

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

    @app.post("/api/ordenes/<int:orden_id>/contenedores")
    def crear_contenedor(orden_id):
        return jsonify(logistica.crear_contenedor(orden_id, request.get_json()["items"])), 201

    @app.post("/api/contenedores/<int:contenedor_id>/precintar")
    def precintar(contenedor_id):
        return jsonify(logistica.precintar(contenedor_id, request.get_json().get("precinto")))

    @app.post("/api/contenedores/<int:contenedor_id>/despachar")
    def despachar(contenedor_id):
        return jsonify(logistica.despachar(contenedor_id))

    @app.post("/api/contenedores/<int:contenedor_id>/recibir")
    def recibir(contenedor_id):
        d = request.get_json()
        return jsonify(logistica.recibir(contenedor_id, d.get("precinto"), bool(d.get("intacto"))))

    @app.get("/api/contenedores/<int:contenedor_id>/historial")
    def historial(contenedor_id):
        return jsonify(logistica.historial(contenedor_id))

    # ---------- ventas (TODO) ----------
    # @app.post("/api/ventas") ...  usar VentasService

    # ---------- reportes ----------
    @app.get("/api/reportes/contenedores-rechazados")
    def rep_rechazados():
        return jsonify(reportes.contenedores_rechazados(request.args.get("desde"),
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
