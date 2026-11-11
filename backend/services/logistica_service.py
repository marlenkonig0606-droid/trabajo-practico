
from database.conexion import BaseDeDatos
from dao.logistica_dao import LogisticaDAO
from models.bulto import Bulto, EstadoBulto
from models.sucursal import Sucursal
from models.observer import Sujeto, Eventos
from services.excepciones import ReglaNegocioError, NoEncontradoError
from services.stock_service import StockService
from services.bloqueos import GestorBloqueos


class LogisticaService(Sujeto):          # es el SUJETO del patrón Observer
    def __init__(self, stock: StockService| None = None):
        super().__init__()
        self.db = BaseDeDatos()
        self.dao = LogisticaDAO(self.db)
        # Se recibe el MISMO StockService que usa el resto de la app, así sus
        # observadores (alertas) se enteran también de las reservas que hace logística.
        self.stock = stock or StockService()
        self.bloqueos = GestorBloqueos()

    # ================================================================
    # 3. ORDEN DE REPOSICIÓN
    # ================================================================
    def crear_orden(self, destino_id, items, origen_id=None, solicitado_por_usuario_id=None):
        """items: [{"producto_id": 1, "cantidad": 10}, ...]"""
        destino = self._obtener_sucursal(destino_id)
        if destino.tipo != "LOCAL":
            raise ReglaNegocioError("El destino de una orden de reposición debe ser un local")
        if not items:
            raise ReglaNegocioError("La orden debe tener al menos un producto")
        self._validar_items(items)

        if origen_id is None:
            cd = self.dao.primer_cd()
            origen_id = cd["id"] if cd else None
        origen = self._obtener_sucursal(origen_id) if origen_id is not None else None
        if origen is None:
            raise ReglaNegocioError("No hay un Centro de Distribución cargado")
        if origen.tipo != "CD":
            raise ReglaNegocioError("El origen de una orden de reposición debe ser un CD")

        orden_id = self.dao.crear_orden(
            origen_id, destino_id, solicitado_por_usuario_id, items)
        return self.obtener_orden(orden_id)

    def obtener_orden(self, orden_id):
        orden = self.dao.obtener_orden(orden_id)
        if orden is None:
            raise NoEncontradoError(f"No existe la orden {orden_id}")
        orden["items"] = self.dao.items_orden(orden_id)
        orden["bultos"] = [b.to_dict() for b in self._bultos_de_orden(orden_id)]
        return orden

    def listar_ordenes(self, destino_id=None, solicitante_id=None):
        ids = self.dao.listar_orden_ids(destino_id, solicitante_id)
        return [self.obtener_orden(f["id"]) for f in ids]

    def sugerir_orden(self, local_id):
        """Devuelve los ítems que le faltan al local para llegar a su stock mínimo."""
        local = self._obtener_sucursal(local_id)
        if local.tipo !=  'LOCAL':
            raise ReglaNegocioError("Solo se puede sugerir una orden para un local")

        filas = StockService().listar( local_id )
        sugerencia = []
        for fila in filas:
            if fila["disponible"] < fila["stock_minimo"]:
                faltante =  fila["stock_minimo"]  - fila["disponible"]
                sugerencia.append({"producto_id": fila["producto_id"],
                                   "nombre": fila["nombre"],
                                   "cantidad": faltante})
        return sugerencia


    def crear_bulto(self, orden_id, items):
        """Al hacer clic en "Empaquetar" el stock del CD queda RESERVADO para este bulto.
        Si dos usuarios empaquetan el mismo producto a la vez, el bloqueo hace que
        pasen de a uno: el segundo ve lo que dejó el primero."""
        orden = self.obtener_orden(orden_id)   # solo para saber el CD (no cambia)
        claves = [(orden["origen_id"], it["producto_id"]) for it in items or []]
        with self.bloqueos.bloquear(claves):     # 1) candados de producto
            return self._crear_bulto(orden_id, items)

    def _crear_bulto(self, orden_id, items):
        # Se vuelve a leer la orden ADENTRO del bloqueo: lo de afuera puede estar viejo
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

        with self.dao.transaccion():                # 2) recién ahora la transacción
            remito_id = orden["remito_id"] or self.dao.crear_remito(
                f"R-{orden_id:06d}", orden_id)
            bulto_id = self.dao.crear_bulto(remito_id)
            for it in items:
                self.dao.agregar_item_bulto(
                    bulto_id, it["producto_id"], it["cantidad"])
                # Si no alcanza, lanza error y la transacción deshace TODO el bulto
                self.stock.reservar(orden["origen_id"], it["producto_id"], it["cantidad"],
                                    f"bulto {bulto_id}")
            self._registrar_historial(bulto_id, EstadoBulto.PREPARADO, "Bulto armado en CD")
            self.dao.marcar_orden_en_preparacion(orden_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def precintar(self, bulto_id):
        bulto = self.obtener_bulto(bulto_id)
        with self.dao.transaccion():
            siguiente = bulto.id
            while True:
                precinto = f"P-{siguiente:06d}"
                existente = self.dao.precinto_existente(precinto)
                if existente is None:
                    break
                siguiente += 1
            self._transicionar(bulto, EstadoBulto.PRECINTADO, f"Precinto {precinto}")
            self.dao.asignar_precinto(bulto_id, precinto)
        return self.obtener_bulto(bulto_id).to_dict()


    def anular_bulto(self, bulto_id, motivo):
        """Solo antes de despachar: el bulto se cancela y su stock vuelve a estar libre en el CD."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la anulación")

        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        claves = [(orden["origen_id"], it["producto_id"]) for it in bulto.items]

        with self.bloqueos.bloquear(claves):
            with self.dao.transaccion():
                self._transicionar(bulto, EstadoBulto.ANULADO, f"Anulado: {motivo}")
                for item in bulto.items:
                    self.stock.liberar_reserva(orden["origen_id"], item["producto_id"], item["cantidad"])
        return self.obtener_bulto(bulto_id).to_dict()

    def despachar(self, bulto_id):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)

        with self.dao.transaccion():
            self._transicionar(bulto, EstadoBulto.EN_TRANSITO, "Despachado desde CD")
            self.dao.fijar_fecha_despacho(bulto_id)
            self.dao.marcar_remito_despachado(bulto.remito_id)
            self.dao.marcar_orden_despachada(orden["id"])
            # Observer: StockObserver descuenta del CD (y si no alcanza, lanza error -> rollback)
            self.notificar(Eventos.BULTO_DESPACHADO, {
                "bulto_id": bulto_id, "origen_id": orden["origen_id"], "items": bulto.items})
        return self.obtener_bulto(bulto_id).to_dict()

    def recibir(self, bulto_id):
        """Registra que el local recibió físicamente el bulto, sin habilitar el stock."""
        bulto = self.obtener_bulto(bulto_id)
        with self.dao.transaccion():
            self._transicionar(bulto, EstadoBulto.RECIBIDO, "Bulto recibido en el local")
            self.dao.fijar_fecha_recepcion(bulto_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def verificar_recepcion(self, bulto_id, aprobado):
        """Registra la decisión del local tras revisar físicamente el remito y precinto."""
        bulto = self.obtener_bulto(bulto_id)
        if not isinstance(aprobado, bool):
            raise ReglaNegocioError("aprobado debe ser verdadero o falso")
        with self.dao.transaccion():
            if aprobado:
                self._transicionar(
                    bulto, EstadoBulto.VERIFICADO, "Remito y precinto verificados")
            else:
                motivo = "Remito o precinto rechazado por el local destinatario"
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
        self.dao.cerrar_remito(remito_id, estado_remito)
        orden = self._orden_de_remito(remito_id)
        self.dao.cerrar_orden(orden["id"])

        if verificados:
            self.notificar(Eventos.REMITO_VERIFICADO, {
                "remito_numero": orden["remito_numero"],
                "destino_id": orden["destino_id"],
                "items_verificados": [it for b in verificados for it in b.items],
            })

    def obtener_bulto(self, bulto_id):
        fila = self.dao.obtener_bulto(bulto_id)
        if fila is None:
            raise NoEncontradoError(f"No existe el bulto {bulto_id}")
        items = self.dao.items_bulto(bulto_id)
        return Bulto.desde_fila(fila, items)

    def obtener_orden_de_bulto(self, bulto_id):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        if orden is None:
            raise NoEncontradoError(f"No existe una orden para el bulto {bulto_id}")
        return orden

    def historial(self, bulto_id):
        self.obtener_bulto(bulto_id)   # valida que exista
        return self.dao.listar_historial(bulto_id)

    def _transicionar(self, bulto: Bulto, nuevo_estado, observacion):
        try:
            bulto.cambiar_estado(nuevo_estado)    # el modelo valida la transición
        except ValueError as e:
            raise ReglaNegocioError(str(e))
        self.dao.actualizar_estado_bulto(bulto.id, nuevo_estado)
        self._registrar_historial(bulto.id, nuevo_estado, observacion)

    def _registrar_historial(self, bulto_id, estado, observacion):
        self.dao.registrar_historial(bulto_id, estado, observacion)

    def _bultos_de_remito(self, remito_id):
        ids = self.dao.listar_bulto_ids_remito(remito_id)
        return [self.obtener_bulto(f["id"]) for f in ids]

    def _bultos_de_orden(self, orden_id):
        remito = self.dao.remito_de_orden(orden_id)
        return self._bultos_de_remito(remito["id"]) if remito else []

    def _orden_de_remito(self, remito_id):
        return self.dao.orden_de_remito(remito_id)

    def _obtener_sucursal(self, sucursal_id):
        fila = self.dao.obtener_sucursal(sucursal_id)
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
            if not self.dao.existe_producto(it["producto_id"]):
                raise NoEncontradoError(f"No existe el producto {it['producto_id']}")
