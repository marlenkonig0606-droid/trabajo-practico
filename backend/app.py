import os
import hmac
import secrets
from datetime import date
from functools import wraps

from flask import Flask, g, jsonify, request, session
from flask_cors import CORS

from database.datos_iniciales import cargar as cargar_datos_iniciales
from services.excepciones import (
    AccesoDenegadoError,
    CuentaNoHabilitadaError,
    NoEncontradoError,
    ReglaNegocioError,
)
from services.auth_service import AuthService
from services.logistica_service import LogisticaService
from services.stock_service import StockService
from services.reportes_service import ReportesService
from services.observadores import (
    AlertaStockMinimoObserver,
    AlertasService,
    AuditoriaObserver,
    StockObserver,
)
from services.ventas_service import VentasService
from services.catalogo_service import CatalogoService
from services.usuarios_service import UsuariosService
from services.paginacion import coincide, leer_paginacion, paginar


RUTA_CODIGO_CD = os.path.join(os.path.dirname(__file__), "cd_registration_code.txt")


def codigo_registro_cd():
    """Código de invitación para registrar cuentas del CD.
    Se toma de la variable de entorno CD_REGISTRATION_CODE o, si no está, del archivo
    local cd_registration_code.txt (no se sube al repositorio, ver .gitignore)."""
    codigo = os.environ.get("CD_REGISTRATION_CODE", "").strip()
    if not codigo and os.path.exists(RUTA_CODIGO_CD):
        with open(RUTA_CODIGO_CD, encoding="utf-8") as archivo:
            codigo = archivo.read().strip()
    return codigo


def crear_app(cargar_demo=True):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("FLASK_COOKIE_SECURE") == "1",
    )
    CORS(app)

    cargar_datos_iniciales(incluir_demo=cargar_demo)

    # ---------- Patrón Observer: acá se conectan sujetos y observadores ----------
    stock = StockService()                            # sujeto 1
    stock.suscribir(AlertaStockMinimoObserver())

    logistica = LogisticaService(stock)               # sujeto 2 (comparte el mismo stock)
    logistica.suscribir(StockObserver(stock))
    logistica.suscribir(AuditoriaObserver())

    reportes = ReportesService()
    alertas = AlertasService()
    ventas = VentasService(stock)
    catalogo = CatalogoService(stock_service=stock)
    auth = AuthService()
    usuarios = UsuariosService()
    # Bootstrap: todo local activo que no tenga administrador recibe uno.
    usuarios.asegurar_administradores()
    # Al iniciar se recalculan las alertas de stock mínimo con los valores actuales
    # (corrige alertas viejas que quedaron con datos desactualizados).
    stock.revisar_alertas()

    # ---------- listados: filtros y paginación en el backend ----------
    def estado_activo(fila, campo="activo"):
        """Filtro ?estado=activos|inactivos (vacío = todos)."""
        estado = request.args.get("estado", "")
        if estado == "activos":
            return bool(fila[campo])
        if estado == "inactivos":
            return not fila[campo]
        return True

    def listado(lista, *campos_busqueda, extra=lambda fila: True):
        """Aplica ?q= (búsqueda parcial en los campos indicados), ?estado= y el
        filtro extra; si viene ?pagina= devuelve solo esa página y el total."""
        q = request.args.get("q", "")
        filtrada = [f for f in lista
                    if coincide(q, *(f.get(c) for c in campos_busqueda))
                    and estado_activo(f) and extra(f)]
        return jsonify(paginar(filtrada, leer_paginacion(request.args)))

    def cuerpo_json():
        datos = request.get_json(silent=True)
        if not isinstance(datos, dict):
            raise ReglaNegocioError("El cuerpo de la solicitud debe ser un objeto JSON")
        return datos

    def entero_positivo(valor, campo):
        if isinstance(valor, bool) or not isinstance(valor, int) or valor <= 0:
            raise ReglaNegocioError(f"{campo} debe ser un entero positivo")
        return valor

    def fechas_de_reporte():
        desde = request.args.get("desde") or None
        hasta = request.args.get("hasta") or None
        try:
            fecha_desde = date.fromisoformat(desde) if desde else None
            fecha_hasta = date.fromisoformat(hasta) if hasta else None
        except ValueError as error:
            raise ReglaNegocioError("Las fechas deben tener el formato AAAA-MM-DD") from error
        hoy = date.today()
        if fecha_desde and fecha_desde > hoy:
            raise ReglaNegocioError("La fecha desde no puede ser posterior a hoy")
        if fecha_hasta and fecha_hasta > hoy:
            raise ReglaNegocioError("La fecha hasta no puede ser posterior a hoy")
        if fecha_desde and fecha_hasta and fecha_desde > fecha_hasta:
            raise ReglaNegocioError("La fecha desde no puede ser posterior a la fecha hasta")
        return desde, hasta

    def requiere_cd(fn):
        @wraps(fn)
        def protegido(*args, **kwargs):
            if g.usuario["tipo"] != "CD":
                raise AccesoDenegadoError("Esta función está disponible solo para el CD")
            return fn(*args, **kwargs)
        return protegido

    def es_empleado_de_local(usuario):
        return usuario["tipo"] == "LOCAL" and usuario["rol"] == "EMPLEADO"

    def requiere_admin_local(fn):
        """Solo el ADMINISTRADOR de un local (gestión de su equipo y panel)."""
        @wraps(fn)
        def protegido(*args, **kwargs):
            if g.usuario["tipo"] != "LOCAL" or g.usuario["rol"] != "ADMINISTRADOR":
                raise AccesoDenegadoError(
                    "Esta función está disponible solo para el administrador del local")
            return fn(*args, **kwargs)
        return protegido

    # Mientras la cuenta tenga una contraseña temporal, solo puede hacer esto:
    PERMITIDOS_CON_PASSWORD_TEMPORAL = {"api_cambiar_password", "api_cerrar_sesion"}
    # Secciones a las que un EMPLEADO de local no tiene acceso (RBAC).
    PREFIJOS_PROHIBIDOS_EMPLEADO = ("/api/reportes/", "/api/local/")

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

        # 1) Contraseña temporal: no puede operar hasta elegir la suya.
        if (usuario["debe_cambiar_password"]
                and request.endpoint not in PERMITIDOS_CON_PASSWORD_TEMPORAL):
            return jsonify({
                "error": "Tenés que cambiar tu contraseña temporal antes de continuar",
                "codigo": "CAMBIO_PASSWORD_OBLIGATORIO",
            }), 403
        # 2) RBAC: el empleado no accede a reportes ni a la administración del local.
        if (es_empleado_de_local(usuario)
                and request.path.startswith(PREFIJOS_PROHIBIDOS_EMPLEADO)):
            return jsonify({
                "error": "Tu rol de empleado no tiene acceso a esta sección",
            }), 403

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

    @app.errorhandler(CuentaNoHabilitadaError)
    def cuenta_no_habilitada(e):
        return jsonify({"error": str(e), "estado": e.estado, "motivo": e.motivo}), 403

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
        sucursal = auth.obtener_sucursal(sucursal_id)
        if sucursal is None:
            raise ReglaNegocioError("La sucursal seleccionada no existe")
        if sucursal["tipo"] == "CD":
            codigo_configurado = codigo_registro_cd()
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
            # El usuario de local queda PENDIENTE: no se inicia sesión hasta que
            # el administrador de su local lo apruebe.
            pendiente = auth.registrar_local(
                datos.get("email"), datos.get("password"), sucursal_id,
                datos.get("rol") or "EMPLEADO")
            session.clear()
            return jsonify({
                **pendiente,
                "pendiente": True,
                "mensaje": ("Tu cuenta quedó pendiente de validación. El administrador "
                            "de tu local tiene que aprobarla; cuando lo haga te va a dar "
                            "una contraseña temporal para entrar."),
            }), 201
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

    @app.post("/api/auth/cambiar-password")
    def api_cambiar_password():
        datos = cuerpo_json()
        usuario = auth.cambiar_password(
            g.usuario["id"], datos.get("actual"), datos.get("nueva"))
        return jsonify(usuario)

    @app.post("/api/auth/logout")
    def api_cerrar_sesion():
        session.clear()
        return "", 204

    @app.get("/api/sucursales")
    def api_sucursales():
        return jsonify(catalogo.listar_sucursales(solo_activas=True))

    # ---------- catálogo (procesos 1 y 2) ----------

    @app.get("/api/catalogo/sucursales")
    @requiere_cd
    def listar_sucursales_catalogo():
        tipo = request.args.get("tipo")
        return listado(catalogo.listar_sucursales(), "nombre", "direccion", "codigo",
                       extra=lambda f: not tipo or f["tipo"] == tipo)

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

    @app.patch("/api/sucursales/<int:id_sucursal>/estado")
    @requiere_cd
    def cambiar_estado_sucursal(id_sucursal):
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_estado_sucursal(
            id_sucursal, datos.get("activo")))

    # Productos
    @app.get("/api/productos")
    def listar_productos():
        if g.usuario["tipo"] != "CD":
            productos = catalogo.productos_habilitados_sucursal(
                g.usuario["sucursal_id"])
            return jsonify([{
                    "id": producto["id"],
                    "codigo": producto["codigo"],
                    "nombre": producto["nombre"],
                    "precio_venta": producto["precio_venta"],
                } for producto in productos])
        categoria = request.args.get("categoria_id")
        return listado(catalogo.listar_productos(), "nombre", "codigo",
                       extra=lambda f: not categoria or str(f["categoria_id"]) == categoria)

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

    @app.patch("/api/productos/<int:id_producto>/estado")
    @requiere_cd
    def cambiar_estado_producto(id_producto):
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_estado_producto(
            id_producto, datos.get("activo")))

    # Categorías
    @app.get("/api/categorias")
    @requiere_cd
    def listar_categorias():
        return listado(catalogo.listar_categorias(), "nombre", "descripcion")

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

    @app.patch("/api/categorias/<int:id_categoria>/estado")
    @requiere_cd
    def cambiar_estado_categoria(id_categoria):
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_estado_categoria(
            id_categoria, datos.get("activo")))

    # Proveedores
    @app.get("/api/proveedores")
    @requiere_cd
    def listar_proveedores():
        return listado(catalogo.listar_proveedores(), "nombre", "razon_social", "cuit")

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

    @app.patch("/api/proveedores/<int:id_proveedor>/estado")
    @requiere_cd
    def cambiar_estado_proveedor(id_proveedor):
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_estado_proveedor(
            id_proveedor, datos.get("activo")))

    @app.get("/api/sucursales/<int:id_sucursal>/productos")
    def productos_de_sucursal(id_sucursal):
        if (g.usuario["tipo"] != "LOCAL"
                or id_sucursal != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError(
                "Cada local solo puede consultar las habilitaciones de su sucursal")
        habilitado = request.args.get("habilitado", "")
        return listado(
            catalogo.productos_de_sucursal(id_sucursal), "nombre", "codigo", "categoria",
            extra=lambda f: (habilitado == "" or bool(f["habilitado"]) == (habilitado == "1")))

    @app.patch("/api/sucursales/<int:id_sucursal>/productos/<int:id_producto>")
    def cambiar_habilitacion_producto(id_sucursal, id_producto):
        if (g.usuario["tipo"] != "LOCAL"
                or id_sucursal != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError(
                "Cada local solo puede cambiar las habilitaciones de su sucursal")
        if es_empleado_de_local(g.usuario):
            raise AccesoDenegadoError(
                "Solo el administrador del local puede habilitar productos")
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_habilitacion_producto(
            id_sucursal, id_producto, datos.get("habilitado")))

    @app.patch("/api/sucursales/<int:id_sucursal>/productos/<int:id_producto>/minimo")
    def cambiar_minimo_local(id_sucursal, id_producto):
        """El administrador del local configura SU stock mínimo para un producto."""
        if (g.usuario["tipo"] != "LOCAL" or id_sucursal != g.usuario["sucursal_id"]
                or es_empleado_de_local(g.usuario)):
            raise AccesoDenegadoError(
                "Solo el administrador del local puede configurar su stock mínimo")
        datos = cuerpo_json()
        return jsonify(catalogo.cambiar_minimo_local(
            id_sucursal, id_producto, datos.get("stock_minimo")))

    @app.patch("/api/stock/<int:sucursal_id>/<int:producto_id>/minimo")
    def cambiar_minimo_cd(sucursal_id, producto_id):
        """Cada CD configura SU stock mínimo. Nadie más puede cambiarlo, y el CD
        no puede cambiar el de los locales (eso es de cada administrador de local)."""
        if g.usuario["tipo"] != "CD" or sucursal_id != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError(
                "Solo podés configurar el stock mínimo de tu propio Centro de Distribución")
        datos = cuerpo_json()
        return jsonify(stock.cambiar_minimo_cd(sucursal_id, producto_id, datos.get("stock_minimo")))

    @app.get("/api/stock/<int:sucursal_id>")
    def ver_stock(sucursal_id):
        if (g.usuario["tipo"] != "CD"
                and sucursal_id != g.usuario["sucursal_id"]):
            raise AccesoDenegadoError("Solo podés consultar el stock de tu sucursal")
        situacion = request.args.get("situacion", "")   # bajo | ok
        proveedor = request.args.get("proveedor_id", "")
        categoria = request.args.get("categoria_id", "")
        habilitado = request.args.get("habilitado", "")  # 1 | 0 (estado en el local)
        es_local = g.usuario["tipo"] == "LOCAL"
        def extra(f):
            if es_local and not f["activo"]:
                return False                     # el local no ve productos dados de baja
            if situacion == "bajo" and f["libre"] >= f["stock_minimo"]:
                return False
            if situacion == "ok" and f["libre"] < f["stock_minimo"]:
                return False
            if habilitado in ("0", "1") and str(f["habilitado"]) != habilitado:
                return False
            if categoria and str(f["categoria_id"]) != categoria:
                return False
            return not proveedor or str(f["proveedor_id"]) == proveedor
        return listado(stock.listar(sucursal_id), "nombre", "codigo", "proveedor", "categoria",
                       extra=extra)

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
            ordenes = logistica.listar_ordenes()
        else:
            # El administrador ve todas las solicitudes del local; el empleado, las suyas.
            ordenes = logistica.listar_ordenes(
                g.usuario["sucursal_id"],
                solicitante_id=None if g.usuario["rol"] == "ADMINISTRADOR" else g.usuario["id"])
        for o in ordenes:          # resumen para el listado compacto
            o["cantidad_productos"] = len(o["items"])
            o["unidades"] = sum(i["cantidad"] for i in o["items"])
        estado = request.args.get("estado_orden", "")
        local = request.args.get("destino_id", "")
        desde, hasta = request.args.get("desde", ""), request.args.get("hasta", "")
        numero = request.args.get("numero", "")
        def extra(o):
            fecha = (o.get("fecha") or "")[:10]
            return ((not estado or o["estado"] == estado)
                    and (not local or str(o["destino_id"]) == local)
                    and (not numero or str(o["id"]) == numero)
                    and (not desde or fecha >= desde) and (not hasta or fecha <= hasta))
        return jsonify(paginar([o for o in ordenes if extra(o)],
                               leer_paginacion(request.args)))

    @app.get("/api/recepciones")
    def listar_recepciones():
        """Bultos que el CD ya despachó hacia el local (lo que el local recibe y
        verifica). Filtros: ?estado_bulto=, ?numero= (n.º de bulto o solicitud)."""
        if g.usuario["tipo"] != "LOCAL":
            raise AccesoDenegadoError("Las recepciones corresponden a los locales")
        estado = request.args.get("estado_bulto", "")
        numero = request.args.get("numero", "")
        recepciones = []
        for o in logistica.listar_ordenes(g.usuario["sucursal_id"]):
            nombres = {i["producto_id"]: i["nombre"] for i in o["items"]}
            for b in o["bultos"]:
                if not b["fecha_despacho"]:          # todavía no salió del CD
                    continue
                if estado and b["estado"] != estado:
                    continue
                if numero and numero not in (str(b["id"]), str(o["id"])):
                    continue
                recepciones.append({
                    **b, "orden_id": o["id"], "origen": o["origen"],
                    "remito_numero": o["remito_numero"],
                    "unidades": sum(i["cantidad"] for i in b["items"]),
                    "items": [{**i, "nombre": nombres.get(i["producto_id"])} for i in b["items"]],
                })
        # Primero lo que falta recibir o verificar; dentro de cada grupo, lo más nuevo.
        recepciones.sort(key=lambda r: r["fecha_despacho"] or "", reverse=True)
        recepciones.sort(key=lambda r: r["estado"] not in ("EN_TRANSITO", "RECIBIDO"))
        return jsonify(paginar(recepciones, leer_paginacion(request.args)))

    @app.get("/api/notificaciones")
    def listar_notificaciones():
        return jsonify(logistica.notificaciones(g.usuario["sucursal_id"]))

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
        return jsonify(logistica.crear_bulto(
            orden_id, request.get_json()["items"], g.usuario["id"])), 201

    @app.post("/api/ordenes/<int:orden_id>/resolver")
    def resolver_orden(orden_id):
        datos = cuerpo_json()
        orden = logistica.obtener_orden(orden_id)
        accion = (datos.get("accion") or "").upper()
        if g.usuario["tipo"] != "CD":
            if orden["destino_id"] != g.usuario["sucursal_id"]:
                raise AccesoDenegadoError("Solo podés resolver órdenes de tu local")
            if accion != "CANCELAR":
                raise AccesoDenegadoError("El local solo puede cancelar su solicitud")
        return jsonify(logistica.resolver_orden(
            orden_id, accion, datos.get("motivo"), g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/precintar")
    @requiere_cd
    def precintar(bulto_id):
        return jsonify(logistica.precintar(bulto_id, g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/reabrir")
    @requiere_cd
    def reabrir_bulto(bulto_id):
        motivo = cuerpo_json().get("motivo")
        return jsonify(logistica.reabrir_bulto(
            bulto_id, motivo, g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/despachar")
    @requiere_cd
    def despachar(bulto_id):
        return jsonify(logistica.despachar(bulto_id, g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/anular")
    @requiere_cd
    def anular(bulto_id):
        motivo = request.get_json().get("motivo")
        return jsonify(logistica.anular_bulto(bulto_id, motivo, g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/recibir")
    def recibir(bulto_id):
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError(
                "La recepción física corresponde al local destinatario")
        orden = logistica.obtener_orden_de_bulto(bulto_id)
        if orden["destino_id"] != g.usuario["sucursal_id"]:
            raise AccesoDenegadoError("Solo podés recibir bultos enviados a tu sucursal")
        return jsonify(logistica.recibir(bulto_id, g.usuario["id"]))

    @app.post("/api/bultos/<int:bulto_id>/perdido")
    @requiere_cd
    def marcar_bulto_perdido(bulto_id):
        motivo = cuerpo_json().get("motivo")
        return jsonify(logistica.marcar_perdido(
            bulto_id, motivo, g.usuario["id"]))

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
        return jsonify(logistica.verificar_recepcion(
            bulto_id, aprobado, datos.get("motivo"), g.usuario["id"]))

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
        paginacion = leer_paginacion(request.args)
        if paginacion is None:                    # compatibilidad: lista completa
            return jsonify(ventas.listar_ventas(sucursal_id))
        filtros = {clave: request.args.get(clave, "").strip()
                   for clave in ("desde", "hasta", "numero", "medio_pago", "producto")}
        return jsonify(ventas.buscar_ventas(sucursal_id, filtros, *paginacion))

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
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError(
                "El CD solo distribuye: las ventas las registran los locales")
        if sucursal_id != g.usuario["sucursal_id"]:
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
        if g.usuario["tipo"] == "CD":
            raise AccesoDenegadoError(
                "El CD solo distribuye: las devoluciones las registran los locales")
        venta = ventas.sucursal_de_venta(venta_id)
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

    # ---------- administración del local (solo ADMINISTRADOR) ----------
    @app.get("/api/local/panel")
    @requiere_admin_local
    def panel_local():
        return jsonify(usuarios.panel(g.usuario))

    @app.get("/api/local/usuarios")
    @requiere_admin_local
    def equipo_local():
        return jsonify(usuarios.equipo(g.usuario))

    @app.post("/api/local/usuarios")
    @requiere_admin_local
    def alta_usuario_local():
        datos = cuerpo_json()
        return jsonify(usuarios.alta_directa(
            g.usuario, datos.get("email"), datos.get("rol"))), 201

    @app.post("/api/local/usuarios/<int:usuario_id>/aprobar")
    @requiere_admin_local
    def aprobar_usuario_local(usuario_id):
        datos = request.get_json(silent=True) or {}
        return jsonify(usuarios.aprobar(g.usuario, usuario_id, datos.get("rol")))

    @app.post("/api/local/usuarios/<int:usuario_id>/rechazar")
    @requiere_admin_local
    def rechazar_usuario_local(usuario_id):
        datos = request.get_json(silent=True) or {}
        return jsonify(usuarios.rechazar(g.usuario, usuario_id, datos.get("motivo")))

    # ---------- reportes ----------
    @app.get("/api/reportes/resumen")
    def rep_resumen():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.resumen(
            desde, hasta, sucursal_id))

    def anio_de_reporte():
        anio = request.args.get("anio")
        if not anio:
            return None
        if not anio.isdigit() or not 2000 <= int(anio) <= date.today().year:
            raise ReglaNegocioError("El año seleccionado no es válido")
        return int(anio)

    @app.get("/api/reportes/local")
    def rep_local():
        """Reporte gerencial del local: período (desde/hasta) o año completo (anio).
        Un local ve SOLO el suyo; el CD puede ver el de cualquier local (?sucursal_id=)."""
        if g.usuario["tipo"] == "LOCAL":
            sucursal_id = g.usuario["sucursal_id"]
        else:
            sucursal_id = request.args.get("sucursal_id", type=int)
            if sucursal_id is None or not reportes.dao.es_local_activo(sucursal_id):
                raise ReglaNegocioError("Elegí un local activo para ver su reporte")
        anio = anio_de_reporte()
        if anio:
            return jsonify(reportes.reporte_local(sucursal_id, anio=anio))
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.reporte_local(sucursal_id, desde, hasta))

    @app.get("/api/reportes/cd")
    @requiere_cd
    def rep_cd():
        """Reporte del centro de distribución. ?pedidos=propios limita los pedidos
        a los que atendió el CD del usuario (por defecto, todos los CD)."""
        cd_id = g.usuario["sucursal_id"] if request.args.get("pedidos") == "propios" else None
        anio = anio_de_reporte()
        if anio:
            return jsonify(reportes.reporte_cd(anio=anio, cd_id=cd_id))
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.reporte_cd(desde, hasta, cd_id=cd_id))

    @app.get("/api/reportes/bultos-rechazados")
    @requiere_cd
    def rep_rechazados():
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.bultos_rechazados(desde, hasta))

    @app.get("/api/reportes/transito")
    def rep_transito():
        return jsonify(reportes.tiempo_promedio_transito())
        
    @app.get("/api/reportes/estado-ordenes")
    @requiere_cd
    def rep_estado_ordenes():
        return jsonify(reportes.estado_ordenes())

    @app.get("/api/reportes/abastecimiento")
    @requiere_cd
    def rep_abastecimiento():
        return jsonify(reportes.abastecimiento())

    @app.get("/api/reportes/medios-pago")
    def rep_medios_pago():#no se pone lo del cd para que lo vean tanto los locales como el CD
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(reportes.ventas_por_medio_pago(sucursal_id))

    @app.get("/api/reportes/devoluciones")
    def rep_devoluciones():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        return jsonify(reportes.devoluciones_por_producto(sucursal_id))

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
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.ventas(desde, hasta, sucursal_id))

    @app.get("/api/reportes/mas-vendidos")
    def rep_mas_vendidos():
        sucursal_id = None if g.usuario["tipo"] == "CD" else g.usuario["sucursal_id"]
        desde, hasta = fechas_de_reporte()
        return jsonify(reportes.mas_vendidos(desde, hasta, sucursal_id))

    return app


if __name__ == "__main__":
    crear_app().run(debug=True, port=5000)
