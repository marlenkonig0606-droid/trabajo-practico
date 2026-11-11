
from database.conexion import BaseDeDatos
from dao.observadores_dao import ObservadoresDAO
from models.observer import Observador, Eventos


class AlertaStockMinimoObserver(Observador):
    """Se suscribe a StockService.

    Cada vez que cambia el stock de un producto en una sucursal:
      - si el stock LIBRE quedó por debajo del mínimo  -> abre una alerta
        (o actualiza la que ya estaba abierta, para no duplicarla)
      - si volvió a llegar al mínimo                     -> resuelve la alerta abierta
    """

    def __init__(self):
        self.db = BaseDeDatos()
        self.dao = ObservadoresDAO(self.db)

    def actualizar(self, evento, datos):
        if evento != Eventos.STOCK_MODIFICADO:
            return      # un observador puede ignorar los eventos que no le interesan

        sucursal_id, producto_id, libre = datos["sucursal_id"], datos["producto_id"], datos["libre"]
        producto = self.dao.stock_minimo(producto_id)
        minimo = producto["stock_minimo"]
        abierta = self.dao.alerta_pendiente(sucursal_id, producto_id)

        if libre < minimo:
            if abierta:
                self.dao.actualizar_alerta(abierta["id"], libre)
            else:
                self.dao.crear_alerta(sucursal_id, producto_id, libre, minimo)
        elif abierta:
            self.dao.resolver_alerta(abierta["id"])


class AuditoriaObserver(Observador):
    """Se suscribe a LogisticaService y deja registro de cada evento logístico.
    Sirve para responder "¿qué pasó con este bulto/remito y cuándo?"."""

    def __init__(self):
        self.db = BaseDeDatos()
        self.dao = ObservadoresDAO(self.db)

    def actualizar(self, evento, datos):
        if evento == Eventos.BULTO_DESPACHADO:
            unidades = sum(i["cantidad"] for i in datos["items"])
            detalle = f"Bulto {datos['bulto_id']} despachado desde el CD ({unidades} unidades)"
        elif evento == Eventos.BULTO_RECHAZADO:
            detalle = f"Bulto {datos['bulto_id']} rechazado: {datos['motivo']}"
        elif evento == Eventos.BULTO_PERDIDO:
            detalle = f"Bulto {datos['bulto_id']} declarado perdido: {datos['motivo']}"
        elif evento == Eventos.REMITO_VERIFICADO:
            unidades = sum(i["cantidad"] for i in datos["items_verificados"])
            detalle = (f"Remito {datos['remito_numero']} verificado: "
                       f"{unidades} unidades disponibles en el local")
        else:
            detalle = str(datos)
        self.dao.registrar_evento(evento, detalle)


class AlertasService:
    """Consultas de lo que dejaron registrado los observadores (para la API)."""

    def __init__(self):
        self.db = BaseDeDatos()
        self.dao = ObservadoresDAO(self.db)

    def alertas(self, solo_pendientes=True, sucursal_id=None):
        filtros = []
        params = []
        if solo_pendientes:
            filtros.append("a.resuelta = 0")
        if sucursal_id is not None:
            filtros.append("a.sucursal_id = ?")
            params.append(sucursal_id)
        filtro = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        return self.dao.listar_alertas(filtro, tuple(params))

    def eventos(self, limite=50):
        return self.dao.listar_eventos(limite)
