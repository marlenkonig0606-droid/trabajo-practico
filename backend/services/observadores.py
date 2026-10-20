"""
Observadores concretos del patrón Observer (el tercero, StockObserver, está en
stock_service.py). Ninguno de estos conoce a LogisticaService ni a StockService:
solo reciben (evento, datos) y deciden qué hacer.
"""
from database.conexion import BaseDeDatos
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

    def actualizar(self, evento, datos):
        if evento != Eventos.STOCK_MODIFICADO:
            return      # un observador puede ignorar los eventos que no le interesan

        sucursal_id, producto_id, libre = datos["sucursal_id"], datos["producto_id"], datos["libre"]
        producto = self.db.consultar_uno(
            "SELECT stock_minimo FROM producto WHERE id=?", (producto_id,))
        minimo = producto["stock_minimo"]
        abierta = self.db.consultar_uno(
            """SELECT id FROM alerta_stock
               WHERE sucursal_id=? AND producto_id=? AND resuelta=0""",
            (sucursal_id, producto_id))

        if libre < minimo:
            if abierta:
                self.db.ejecutar("UPDATE alerta_stock SET libre=? WHERE id=?",
                                 (libre, abierta["id"]))
            else:
                self.db.ejecutar(
                    """INSERT INTO alerta_stock (sucursal_id, producto_id, libre, minimo)
                       VALUES (?, ?, ?, ?)""", (sucursal_id, producto_id, libre, minimo))
        elif abierta:
            self.db.ejecutar(
                """UPDATE alerta_stock
                   SET resuelta=1, fecha_resolucion=datetime('now','localtime') WHERE id=?""",
                (abierta["id"],))


class AuditoriaObserver(Observador):
    """Se suscribe a LogisticaService y deja registro de cada evento logístico.
    Sirve para responder "¿qué pasó con este bulto/remito y cuándo?"."""

    def __init__(self):
        self.db = BaseDeDatos()

    def actualizar(self, evento, datos):
        if evento == Eventos.BULTO_DESPACHADO:
            unidades = sum(i["cantidad"] for i in datos["items"])
            detalle = f"Bulto {datos['bulto_id']} despachado desde el CD ({unidades} unidades)"
        elif evento == Eventos.BULTO_RECHAZADO:
            detalle = f"Bulto {datos['bulto_id']} rechazado: {datos['motivo']}"
        elif evento == Eventos.REMITO_VERIFICADO:
            unidades = sum(i["cantidad"] for i in datos["items_verificados"])
            detalle = (f"Remito {datos['remito_numero']} verificado: "
                       f"{unidades} unidades disponibles en el local")
        else:
            detalle = str(datos)
        self.db.ejecutar("INSERT INTO evento_log (evento, detalle) VALUES (?, ?)",
                         (evento, detalle))


class AlertasService:
    """Consultas de lo que dejaron registrado los observadores (para la API)."""

    def __init__(self):
        self.db = BaseDeDatos()

    def alertas(self, solo_pendientes=True):
        filtro = "WHERE a.resuelta = 0" if solo_pendientes else ""
        return self.db.consultar(f"""
            SELECT a.id, s.nombre AS sucursal, p.codigo, p.nombre AS producto,
                   a.libre, a.minimo, a.fecha, a.resuelta, a.fecha_resolucion
            FROM alerta_stock a
            JOIN sucursal s ON s.id = a.sucursal_id
            JOIN producto p ON p.id = a.producto_id
            {filtro}
            ORDER BY a.id DESC""")

    def eventos(self, limite=50):
        return self.db.consultar(
            "SELECT evento, detalle, fecha FROM evento_log ORDER BY id DESC LIMIT ?", (limite,))
