"""
Procesos obligatorios 3, 4, 5 y 6:
  3. Orden de reposición CD -> local
  4. Empaquetar en bultos con remito y precinto
  5. Despachar
  6. Recibir y verificar precinto

Este módulo está COMPLETO: usalo como modelo para escribir ventas.
"""
from database.conexion import BaseDeDatos
from models.bulto import Bulto, EstadoBulto
from models.sucursal import Sucursal
from patrones.observer import Sujeto, Eventos
from services.excepciones import ReglaNegocioError, NoEncontradoError


class LogisticaService(Sujeto):          # es el SUJETO del patrón Observer
    def __init__(self):
        super().__init__()
        self.db = BaseDeDatos()

    # ================================================================
    # 3. ORDEN DE REPOSICIÓN
    # ================================================================
    def crear_orden(self, destino_id, items):
        """items: [{"producto_id": 1, "cantidad": 10}, ...]"""
        destino = self._obtener_sucursal(destino_id)
        if destino.tipo != "LOCAL":
            raise ReglaNegocioError("El destino de una orden de reposición debe ser un local")
        if not items:
            raise ReglaNegocioError("La orden debe tener al menos un producto")
        self._validar_items(items)

        cd = self.db.consultar_uno("SELECT id FROM sucursal WHERE tipo='CD' LIMIT 1")
        if cd is None:
            raise ReglaNegocioError("No hay un Centro de Distribución cargado")

        with self.db.transaccion():
            orden_id = self.db.ejecutar(
                "INSERT INTO orden_reposicion (origen_id, destino_id) VALUES (?, ?)",
                (cd["id"], destino_id))
            for it in items:
                self.db.ejecutar(
                    "INSERT INTO detalle_orden (orden_id, producto_id, cantidad) VALUES (?, ?, ?)",
                    (orden_id, it["producto_id"], it["cantidad"]))
        return self.obtener_orden(orden_id)

    def obtener_orden(self, orden_id):
        orden = self.db.consultar_uno(
            """SELECT o.*, so.nombre AS origen, sd.nombre AS destino,
                      r.id AS remito_id, r.numero AS remito_numero, r.estado AS remito_estado
               FROM orden_reposicion o
               JOIN sucursal so ON so.id = o.origen_id
               JOIN sucursal sd ON sd.id = o.destino_id
               LEFT JOIN remito r ON r.orden_id = o.id
               WHERE o.id = ?""", (orden_id,))
        if orden is None:
            raise NoEncontradoError(f"No existe la orden {orden_id}")
        orden["items"] = self.db.consultar(
            """SELECT d.producto_id, p.nombre, d.cantidad,
                      COALESCE((SELECT SUM(db.cantidad) FROM detalle_bulto db
                                JOIN bulto b ON b.id = db.bulto_id
                                JOIN remito r ON r.id = b.remito_id
                                WHERE r.orden_id = d.orden_id AND db.producto_id = d.producto_id), 0)
                      AS empaquetado
               FROM detalle_orden d JOIN producto p ON p.id = d.producto_id
               WHERE d.orden_id = ?""", (orden_id,))
        orden["bultos"] = [b.to_dict() for b in self._bultos_de_orden(orden_id)]
        return orden

    def listar_ordenes(self):
        ids = self.db.consultar("SELECT id FROM orden_reposicion ORDER BY id DESC")
        return [self.obtener_orden(f["id"]) for f in ids]

    # ================================================================
    # 4. EMPAQUETAR (crear bulto) + asignar remito y precinto
    # ================================================================
    def crear_bulto(self, orden_id, items):
        orden = self.obtener_orden(orden_id)
        if orden["estado"] not in ("PENDIENTE", "EN_PREPARACION"):
            raise ReglaNegocioError("Solo se pueden armar bultos de órdenes pendientes")
        if orden["remito_estado"] not in (None, "ABIERTO"):
            raise ReglaNegocioError("El remito ya fue despachado: no se le pueden agregar bultos")
        if not items:
            raise ReglaNegocioError("El bulto no puede estar vacío")
        self._validar_items(items)

        # No empaquetar más de lo pedido en la orden
        pendientes = {i["producto_id"]: i["cantidad"] - i["empaquetado"] for i in orden["items"]}
        for it in items:
            if it["producto_id"] not in pendientes:
                raise ReglaNegocioError(f"El producto {it['producto_id']} no está en la orden")
            if it["cantidad"] > pendientes[it["producto_id"]]:
                raise ReglaNegocioError(
                    f"Producto {it['producto_id']}: quedan {pendientes[it['producto_id']]} "
                    f"por empaquetar y se intentó empaquetar {it['cantidad']}")

        with self.db.transaccion():
            remito_id = orden["remito_id"] or self.db.ejecutar(
                "INSERT INTO remito (numero, orden_id) VALUES (?, ?)",
                (f"R-{orden_id:06d}", orden_id))
            bulto_id = self.db.ejecutar("INSERT INTO bulto (remito_id) VALUES (?)", (remito_id,))
            for it in items:
                self.db.ejecutar(
                    "INSERT INTO detalle_bulto (bulto_id, producto_id, cantidad) VALUES (?, ?, ?)",
                    (bulto_id, it["producto_id"], it["cantidad"]))
            self._registrar_historial(bulto_id, EstadoBulto.PREPARADO, "Bulto armado en CD")
            self.db.ejecutar("UPDATE orden_reposicion SET estado='EN_PREPARACION' WHERE id=?",
                             (orden_id,))
        return self.obtener_bulto(bulto_id).to_dict()

    def precintar(self, bulto_id, precinto):
        precinto = (precinto or "").strip()
        if not precinto:
            raise ReglaNegocioError("Debe indicar el número de precinto")
        if self.db.consultar_uno("SELECT id FROM bulto WHERE precinto=?", (precinto,)):
            raise ReglaNegocioError(f"El precinto {precinto} ya fue usado en otro bulto")

        bulto = self.obtener_bulto(bulto_id)
        with self.db.transaccion():
            self._transicionar(bulto, EstadoBulto.PRECINTADO, f"Precinto {precinto}")
            self.db.ejecutar("UPDATE bulto SET precinto=? WHERE id=?", (precinto, bulto_id))
        return self.obtener_bulto(bulto_id).to_dict()

    # ================================================================
    # 5. DESPACHO
    # ================================================================
    def despachar(self, bulto_id):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)

        with self.db.transaccion():
            self._transicionar(bulto, EstadoBulto.EN_TRANSITO, "Despachado desde CD")
            self.db.ejecutar(
                "UPDATE bulto SET fecha_despacho=datetime('now','localtime') WHERE id=?",
                (bulto_id,))
            self.db.ejecutar("UPDATE remito SET estado='DESPACHADO' WHERE id=?", (bulto.remito_id,))
            self.db.ejecutar("UPDATE orden_reposicion SET estado='DESPACHADA' WHERE id=?",
                             (orden["id"],))
            # Observer: StockObserver descuenta del CD (y si no alcanza, lanza error -> rollback)
            self.notificar(Eventos.BULTO_DESPACHADO, {
                "bulto_id": bulto_id, "origen_id": orden["origen_id"], "items": bulto.items})
        return self.obtener_bulto(bulto_id).to_dict()

    # ================================================================
    # 6. RECEPCIÓN + VERIFICACIÓN DE PRECINTO
    # ================================================================
    def recibir(self, bulto_id, precinto_leido, precinto_intacto):
        """El local recibe el bulto, lee el número de precinto y declara si está sano.
        - Coincide y está intacto  -> VERIFICADO
        - No coincide o está roto  -> RECHAZADO (rechazo logístico, no habilita venta)"""
        bulto = self.obtener_bulto(bulto_id)

        with self.db.transaccion():
            self._transicionar(bulto, EstadoBulto.RECIBIDO, "Recibido en local")
            self.db.ejecutar(
                "UPDATE bulto SET fecha_recepcion=datetime('now','localtime') WHERE id=?",
                (bulto_id,))

            coincide = (precinto_leido or "").strip() == bulto.precinto
            if coincide and precinto_intacto:
                self._transicionar(bulto, EstadoBulto.VERIFICADO, "Precinto OK")
            else:
                motivo = "Precinto roto" if not precinto_intacto else \
                         f"Precinto no coincide (leído {precinto_leido})"
                self._transicionar(bulto, EstadoBulto.RECHAZADO, motivo)
                self.notificar(Eventos.BULTO_RECHAZADO, {"bulto_id": bulto_id, "motivo": motivo})

            self._cerrar_remito_si_corresponde(bulto.remito_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def _cerrar_remito_si_corresponde(self, remito_id):
        """El stock NO entra al local hasta que el remito completo quede verificado:
        o sea, hasta que todos sus bultos estén en un estado final."""
        bultos = self._bultos_de_remito(remito_id)
        if not all(b.esta_finalizado() for b in bultos):
            return

        verificados = [b for b in bultos if b.estado == EstadoBulto.VERIFICADO]
        estado_remito = "VERIFICADO" if verificados else "RECHAZADO"
        self.db.ejecutar("UPDATE remito SET estado=? WHERE id=?", (estado_remito, remito_id))
        orden = self._orden_de_remito(remito_id)
        self.db.ejecutar("UPDATE orden_reposicion SET estado='CERRADA' WHERE id=?", (orden["id"],))

        if verificados:
            self.notificar(Eventos.REMITO_VERIFICADO, {
                "remito_numero": orden["remito_numero"],
                "destino_id": orden["destino_id"],
                "items_verificados": [it for b in verificados for it in b.items],
            })

    # ================================================================
    # Consultas y helpers
    # ================================================================
    def obtener_bulto(self, bulto_id):
        fila = self.db.consultar_uno("SELECT * FROM bulto WHERE id=?", (bulto_id,))
        if fila is None:
            raise NoEncontradoError(f"No existe el bulto {bulto_id}")
        items = self.db.consultar(
            "SELECT producto_id, cantidad FROM detalle_bulto WHERE bulto_id=?", (bulto_id,))
        return Bulto.desde_fila(fila, items)

    def historial(self, bulto_id):
        self.obtener_bulto(bulto_id)   # valida que exista
        return self.db.consultar(
            "SELECT estado, fecha, observacion FROM historial_bulto WHERE bulto_id=? ORDER BY id",
            (bulto_id,))

    def _transicionar(self, bulto: Bulto, nuevo_estado, observacion):
        try:
            bulto.cambiar_estado(nuevo_estado)    # el modelo valida la transición
        except ValueError as e:
            raise ReglaNegocioError(str(e))
        self.db.ejecutar("UPDATE bulto SET estado=? WHERE id=?", (nuevo_estado, bulto.id))
        self._registrar_historial(bulto.id, nuevo_estado, observacion)

    def _registrar_historial(self, bulto_id, estado, observacion):
        self.db.ejecutar(
            "INSERT INTO historial_bulto (bulto_id, estado, observacion) VALUES (?, ?, ?)",
            (bulto_id, estado, observacion))

    def _bultos_de_remito(self, remito_id):
        ids = self.db.consultar("SELECT id FROM bulto WHERE remito_id=? ORDER BY id", (remito_id,))
        return [self.obtener_bulto(f["id"]) for f in ids]

    def _bultos_de_orden(self, orden_id):
        remito = self.db.consultar_uno("SELECT id FROM remito WHERE orden_id=?", (orden_id,))
        return self._bultos_de_remito(remito["id"]) if remito else []

    def _orden_de_remito(self, remito_id):
        return self.db.consultar_uno(
            """SELECT o.*, r.numero AS remito_numero FROM remito r
               JOIN orden_reposicion o ON o.id = r.orden_id WHERE r.id=?""", (remito_id,))

    def _obtener_sucursal(self, sucursal_id):
        fila = self.db.consultar_uno("SELECT * FROM sucursal WHERE id=?", (sucursal_id,))
        if fila is None:
            raise NoEncontradoError(f"No existe la sucursal {sucursal_id}")
        return Sucursal.desde_fila(fila)

    def _validar_items(self, items):
        vistos = set()
        for it in items:
            if it.get("cantidad", 0) <= 0:
                raise ReglaNegocioError("Las cantidades deben ser mayores a cero")
            if it["producto_id"] in vistos:
                raise ReglaNegocioError(f"Producto {it['producto_id']} repetido")
            vistos.add(it["producto_id"])
            if not self.db.consultar_uno("SELECT id FROM producto WHERE id=?", (it["producto_id"],)):
                raise NoEncontradoError(f"No existe el producto {it['producto_id']}")
