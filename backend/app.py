"""
API REST (Flask).  Ejecutar:  python app.py   ->  http://localhost:5000

Capas (igual que el repo de referencia, pero separadas en carpetas):
  routes (este archivo)  ->  services (reglas de negocio)  ->  database (Singleton)
                                    │
                                 models (clases del dominio)
"""
import os
import hmac
import secrets
from functools import wraps

from flask import Flask, g, jsonify, request, session
from flask_cors import CORS

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar as cargar_datos_iniciales
from services.excepciones import (
    AccesoDenegadoError,
    NoEncontradoError,
    ReglaNegocioError,
)
from services.auth_service import AuthService
from services.logistica_service import LogisticaService
from services.stock_service import StockService, StockObserver
from services.reportes_service import ReportesService
from services.observadores import AlertaStockMinimoObserver, AuditoriaObserver, AlertasService
from services.ventas_service import VentasService
from services.catalogo_service import CatalogoService


def crear_app():
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE") == "1",
    )
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
    ventas = VentasService(stock)
    catalogo = CatalogoService()
    auth = AuthService()

    def cuerpo_json():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")
        return datos

    def entero_positivo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise ReglaNegocioError(f"{campo} debe ser un entero positivo")
        return valor

    def requiere_cd(fn):
        @wraps(fn)
        def protegido(*args, **kwargs):
            if g.usuario["tipo"] != "CD":
                raise AccesoDenegadoError("Esta función está disponible solo para el CD")
            return fn(*args, **kwargs)
        return protegido

    @app.before_request
    def autenticar_api():
        if not request.path.startswith("/api/"):
            return
        publicos = {
            "api_registrar",
            "api_iniciar_sesion",
            "api_sucursales",
            "api_sesion_actual",
        }
        if request.endpoint in publicos:
            return
        usuario_id = session.get("usuario_id")
        usuario = auth.obtener_usuario(usuario_id) if usuario_id else None
        if usuario is None:
            session.clear()
            return jsonify({"error": "Iniciá sesión para continuar"}), 401
        g.usuario = usuario

    # ---------- manejo de errores centralizado ----------
    @app.errorhandler(ReglaNegocioError)
    def regla_negocio(e):
        return jsonify({"error": str(e)}), 400

    @app.errorhandler(NoEncontradoError)
    def no_encontrado(e):
        return jsonify({"error": str(e)}), 404

    @app.errorhandler(AccesoDenegadoError)
    def acceso_denegado(e):
        return jsonify({"error": str(e)}), 403

    @app.errorhandler(NotImplementedError)
    def no_implementado(e):
        return jsonify({"error": f"Pendiente: {e}"}), 501

    # ---------- autenticación ----------
    @app.get("/api/auth/me")
    def api_sesion_actual():
        usuario_id = session.get("usuario_id")
        usuario = auth.obtener_usuario(usuario_id) if usuario_id else None
        if usuario is None:
            return jsonify({"error": "No hay una sesión iniciada"}), 401
        return jsonify(usuario)

    @app.post("/api/auth/register")
    def api_registrar():
        datos = cuerpo_json()
        sucursal_id = entero_positivo(datos.get("sucursal_id"), "sucursal_id")
        sucursal = db.consultar_uno(
            "SELECT tipo FROM sucursal WHERE id=?", (sucursal_id,))
        if sucursal is None:
            raise ReglaNegocioError("La sucursal seleccionada no existe")
        if sucursal["tipo"] == "CD":
            codigo_configurado = os.environ.get("CD_REGISTRATION_CODE", "")
            codigo_ingresado = datos.get("codigo_cd")
            if not codigo_configurado:
                raise ReglaNegocioError(
                    "El registro CD no está habilitado. Configurá "
                    "CD_REGISTRATION_CODE y reiniciá el backend.")
            if (not isinstance(codigo_ingresado, str)
                    or not hmac.compare_digest(codigo_ingresado, codigo_configurado)):
                raise ReglaNegocioError("El código de invitación del CD es incorrecto")
            usuario = auth.registrar_cd(
                datos.get("email"), datos.get("password"), sucursal_id)
        else:
            usuario = auth.registrar_local(
                datos.get("email"), datos.get("password"), sucursal_id)
        session.clear()
        session["usuario_id"] = usuario["id"]
        return jsonify(usuario), 201

    @app.post("/api/auth/login")
    def api_iniciar_sesion():
        datos = cuerpo_json()
        usuario = auth.autenticar(datos.get("email"), datos.get("password"))
        if usuario is None:
            return jsonify({"error": "Correo o contraseña incorrectos"}), 401
        session.clear()
        session["usuario_id"] = usuario["id"]
        return jsonify(usuario)

    @app.post("/api/auth/logout")
    def api_cerrar_sesion():
        session.clear()
        return "", 204

    @app.get("/api/sucursales")
    def api_sucursales():
        return jsonify(catalogo.listar_sucursales())

    # ---------- catálogo (procesos 1 y 2) ----------

    @app.get("/api/sucursales/<int:id_sucursal>")
    @requiere_cd
    def obtener_sucursal(id_sucursal):
        return jsonify(catalogo.obtener_sucursal(id_sucursal))

    @app.post("/api/sucursales")
    @requiere_cd
    def crear_sucursal():
        return jsonify(catalogo.crear_sucursal(cuerpo_json())), 201

    @app.put("/api/sucursales/<int:id_sucursal>")
    @requiere_cd
    def actualizar_sucursal(id_sucursal):
        return jsonify(catalogo.actualizar_sucursal(id_sucursal, cuerpo_json()))

    @app.delete("/api/sucursales/<int:id_sucursal>")
    @requiere_cd
    def eliminar_sucursal(id_sucursal):
        catalogo.eliminar_sucursal(id_sucursal)
        return "", 204

    # Productos
    @app.get("/api/productos")
    def listar_productos():
        productos = catalogo.listar_productos()
        if g.usuario["tipo"] != "CD":
            productos_publicos = []
            for producto in productos:
                productos_publicos.append({
                    "id": producto["id"],
                    "codigo": producto["codigo"],
                    "nombre": producto["nombre"],
                    "precio_venta": producto["precio_venta"],
                })
            return jsonify(productos_publicos)
        return jsonify(productos)

    @app.get("/api/productos/<int:id_producto>")
    @requiere_cd
    def obtener_producto(id_producto):
        return jsonify(catalogo.obtener_producto(id_producto))

    @app.post("/api/productos")
    @requiere_cd
    def crear_producto():
        return jsonify(catalogo.crear_producto(cuerpo_json())), 201

    @app.put("/api/productos/<int:id_producto>")
    @requiere_cd
    def actualizar_producto(id_producto):
        return jsonify(catalogo.actualizar_producto(id_producto, cuerpo_json()))

    @app.delete("/api/productos/<int:id_producto>")
    @requiere_cd
    def eliminar_producto(id_producto):
        catalogo.eliminar_producto(id_producto)
        return "", 204

    # Categorías
    @app.get("/api/categorias")
    @requiere_cd
    def listar_categorias():
        return jsonify(catalogo.listar_categorias())

    @app.post("/api/categorias")
    @requiere_cd
    def crear_categoria():
        return jsonify(catalogo.crear_categoria(cuerpo_json())), 201

    @app.put("/api/categorias/<int:id_categoria>")
    @requiere_cd
    def actualizar_categoria(id_categoria):
        return jsonify(catalogo.actualizar_categoria(id_categoria, cuerpo_json()))

    @app.delete("/api/categorias/<int:id_categoria>")
    @requiere_cd
    def eliminar_categoria(id_categoria):
        catalogo.eliminar_categoria(id_categoria)
        return "", 204

    # Proveedores
    @app.get("/api/proveedores")
    @requiere_cd
    def listar_proveedores():
        return jsonify(catalogo.listar_proveedores())

    @app.post("/api/proveedores")
    @requiere_cd
    def crear_proveedor():
        return jsonify(catalogo.crear_proveedor(cuerpo_json())), 201

    @app.put("/api/proveedores/<int:id_proveedor>")
    @requiere_cd
    def actualizar_proveedor(id_proveedor):
        return jsonify(catalogo.actualizar_proveedor(id_proveedor, cuerpo_json()))

    @app.delete("/api/proveedores/<int:id_proveedor>")
    @requiere_cd
    def eliminar_proveedor(id_proveedor):
        catalogo.eliminar_proveedor(id_proveedor)
        return "", 204

    @app.get("/api/stock/<int:sucursal_id>")
    def ver_stock(sucursal_id):
        if (g.usuario["tipo"] != "CD"
                and sucursal_id != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError("Solo podés consultar el stock de tu sucursal")
        return jsonify(stock.listar(sucursal_id))

    @app.put("/api/stock/<int:sucursal_id>/<int:producto_id>")
    def ajustar_stock_cd(sucursal_id, producto_id):
        if g.usuario["tipo"] != "CD" or sucursal_id != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError(
                "Solo podés ajustar el stock de tu propio Centro de Distribución")
        datos = cuerpo_json()
        disponible = datos.get("disponible")
        if (isinstance(disponible, bool) or not isinstance(disponible, int)
                or disponible < 0):
            raise ReglaNegocioError("disponible debe ser un entero mayor o igual a cero")
        stock.ajustar_disponible(
            sucursal_id, producto_id, disponible, f"ajuste manual por usuario {g.usuario['id']}")
        return jsonify(stock.listar(sucursal_id))

    # ---------- logística ----------
    @app.get("/api/ordenes")
    def listar_ordenes():
        if g.usuario["tipo"] == "CD":
            return jsonify(logistica.listar_ordenes())
        return jsonify(logistica.listar_ordenes(
            g.usuario["sucursal_id"], solicitante_id=g.usuario["id"]))

    @app.get("/api/sucursales/<int:local_id>/sugerencia")
    def sugerir_orden(local_id):
        if (g.usuario["tipo"] != "CD"
                and local_id != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError("Solo podés solicitar una sugerencia para tu sucursal")
        return jsonify(logistica.sugerir_orden(local_id))

    @app.post("/api/ordenes")
    def crear_orden():
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError("Solo los locales pueden crear solicitudes de reposición")
        datos = cuerpo_json()
        destino_id = entero_positivo(datos.get("destino_id"), "destino_id")
        if destino_id != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError("Solo podés crear órdenes para tu propio local")
        origen_id = entero_positivo(datos.get("origen_id"), "origen_id")
        if not isinstance(datos.get("items"), list):
            raise ReglaNegocioError("items debe ser una lista")
        return jsonify(
            logistica.crear_orden(
                destino_id, datos["items"], origen_id,
                solicitado_por_usuario_id=g.usuario["id"])), 201

    @app.post("/api/ordenes/<int:orden_id>/bultos")
    @requiere_cd
    def crear_bulto(orden_id):
        return jsonify(logistica.crear_bulto(orden_id, request.get_json()["items"])), 201

    @app.post("/api/bultos/<int:bulto_id>/precintar")
    @requiere_cd
    def precintar(bulto_id):
        return jsonify(logistica.precintar(bulto_id))

    @app.post("/api/bultos/<int:bulto_id>/despachar")
    @requiere_cd
    def despachar(bulto_id):
        return jsonify(logistica.despachar(bulto_id))

    @app.post("/api/bultos/<int:bulto_id>/anular")
    @requiere_cd
    def anular(bulto_id):
        motivo = request.get_json().get("motivo")
        return jsonify(logistica.anular_bulto(bulto_id, motivo))

    @app.post("/api/bultos/<int:bulto_id>/recibir")
    def recibir(bulto_id):
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError(
                "La recepción física corresponde al local destinatario")
        orden = logistica.obtener_orden_de_bulto(bulto_id)
        if orden["destino_id"] != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError("Solo podés recibir bultos enviados a tu sucursal")
        return jsonify(logistica.recibir(bulto_id))

    @app.post("/api/bultos/<int:bulto_id>/verificar")
    def verificar_recepcion(bulto_id):
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError(
                "La verificación del remito y precinto corresponde al local destinatario")
        orden = logistica.obtener_orden_de_bulto(bulto_id)
        if orden["destino_id"] != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError(
                "Solo podés verificar bultos enviados a tu sucursal")
        datos = cuerpo_json()
        aprobado = datos.get("aprobado")
        if not isinstance(aprobado, bool):
            raise ReglaNegocioError("aprobado debe ser verdadero o falso")
        return jsonify(logistica.verificar_recepcion(bulto_id, aprobado))

    @app.get("/api/bultos/<int:bulto_id>/historial")
    def historial(bulto_id):
        if g.usuario["tipo"] != "CD":
            orden = logistica.obtener_orden_de_bulto(bulto_id)
            if orden["destino_id"] != g.usuario["sucursal_id"]:
                raise AccesoDenegadoError("Solo podés ver el historial de bultos de tu sucursal")
        return jsonify(logistica.historial(bulto_id))

    # ---------- lo que registran los observadores ----------
    @app.get("/api/alertas")
    def listar_alertas():
        if g.usuario["tipo"] == "CD":
            sucursal_id = None
        else:
            sucursal_id = g.usuario["sucursal_id"]
        return jsonify(alertas.alertas(
            solo_pendientes=request.args.get("todas") is None,
            sucursal_id=sucursal_id,
        ))

    @app.get("/api/eventos")
    @requiere_cd
    def listar_eventos():
        return jsonify(alertas.eventos())

    # ---------- ventas y devoluciones ----------
    @app.get("/api/ventas")
    def listar_ventas():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(ventas.listar_ventas(sucursal_id))

    @app.get("/api/ventas/<int:venta_id>")
    def obtener_venta(venta_id):
        venta = ventas.obtener_venta(venta_id)
        if (g.usuario["tipo"] != "CD"
                and venta["sucursal_id"] != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError("Solo podés consultar las ventas de tu sucursal")
        return jsonify(venta)

    @app.post("/api/ventas")
    def registrar_venta():
        datos = cuerpo_json()
        sucursal_id = entero_positivo(datos.get("sucursal_id"), "sucursal_id")
        if (g.usuario["tipo"] != "CD"
                and sucursal_id != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError("Solo podés registrar ventas en tu sucursal")
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
        if g.usuario["tipo"] != "CD":
            venta = db.consultar_uno(
                "SELECT sucursal_id FROM venta WHERE id=?", (venta_id,))
            if venta is None:
                raise NoEncontradoError(f"No existe la venta {venta_id}")
            if venta["sucursal_id"] != g.usuario["sucursal_id"]:
                raise AccesoDenegadoError(
                    "Solo podés registrar devoluciones de ventas de tu sucursal")
        items = datos.get("items")
        if not isinstance(items, list):
            raise ReglaNegocioError("items debe ser una lista")
        return jsonify(
            ventas.registrar_devolucion(venta_id, items, datos.get("motivo"))
        ), 201

    # ---------- reportes ----------
    @app.get("/api/reportes/bultos-rechazados")
    @requiere_cd
    def rep_rechazados():
        return jsonify(reportes.bultos_rechazados(request.args.get("desde"),
                                                  request.args.get("hasta")))

    @app.get("/api/reportes/transito")
    @requiere_cd
    def rep_transito():
        return jsonify(reportes.tiempo_promedio_transito())

    @app.get("/api/reportes/existencias")
    def rep_existencias():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(reportes.existencias(sucursal_id))

    @app.get("/api/reportes/movimientos")
    def rep_movimientos():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        permitidos = {"VENTA", "DEVOLUCION", "RECEPCION"}
        tipos = request.args.getlist("tipo")
        if not tipos:
            tipos = list(permitidos)
        if any(tipo not in permitidos for tipo in tipos):
            raise ReglaNegocioError("El tipo de movimiento solicitado no es válido")
        return jsonify(reportes.movimientos(sucursal_id, tipos))

    @app.get("/api/reportes/ventas")
    def rep_ventas():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(reportes.ventas(
            request.args.get("desde"), request.args.get("hasta"), sucursal_id))

    @app.get("/api/reportes/mas-vendidos")
    def rep_mas_vendidos():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(reportes.mas_vendidos(
            request.args.get("desde"), request.args.get("hasta"), sucursal_id))

    return app


if __name__ == "__main__":
    crear_app().run(debug=True, port=5000)
