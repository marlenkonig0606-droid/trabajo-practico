from datetime import datetime, timedelta

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
        if not destino.activo:
            raise ReglaNegocioError("No se pueden crear órdenes para una sucursal inactiva")
        if destino.tipo != "LOCAL":
            raise ReglaNegocioError("El destino de una orden de reposición debe ser un local")
        if not items:
            raise ReglaNegocioError("La orden debe tener al menos un producto")
        self._validar_items(items)
        for item in items:
            producto = self.dao.producto_para_sucursal(
                item["producto_id"], destino_id)
            if producto is None or not producto["habilitado"]:
                raise ReglaNegocioError(
                    f"El producto {item['producto_id']} no está habilitado "
                    "para el local destinatario")

        if origen_id is None:
            cd = self.dao.primer_cd()
            origen_id = cd["id"] if cd else None
        origen = self._obtener_sucursal(origen_id) if origen_id is not None else None
        if origen is None:
            raise ReglaNegocioError("No hay un Centro de Distribución cargado")
        if not origen.activo:
            raise ReglaNegocioError("El Centro de Distribución de origen está inactivo")
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
        self.procesar_vencimientos()
        ids = self.dao.listar_orden_ids(destino_id, solicitante_id)
        return [self.obtener_orden(f["id"]) for f in ids]

    def sugerir_orden(self, local_id):
        """Devuelve los ítems que le faltan al local para llegar a su stock mínimo."""
        local = self._obtener_sucursal(local_id)
        if not local.activo:
            raise ReglaNegocioError("No se puede solicitar stock para una sucursal inactiva")
        if local.tipo !=  'LOCAL':
            raise ReglaNegocioError("Solo se puede sugerir una orden para un local")

        filas = self.stock.listar(local_id)
        sugerencia = []
        for fila in filas:
            if not fila["activo"] or not fila["habilitado"]:
                continue
            disponible_vendible = fila["libre"]
            pendiente = self.dao.reposicion_pendiente(
                local_id, fila["producto_id"])
            faltante = max(
                0, fila["stock_minimo"] - disponible_vendible - pendiente)
            if faltante:
                sugerencia.append({"producto_id": fila["producto_id"],
                                   "nombre": fila["nombre"],
                                   "cantidad": faltante})
        return sugerencia


    def crear_bulto(self, orden_id, items, usuario_id=None):
        """Al hacer clic en "Empaquetar" el stock del CD queda RESERVADO para este bulto.
        Si dos usuarios empaquetan el mismo producto a la vez, el bloqueo hace que
        pasen de a uno: el segundo ve lo que dejó el primero."""
        orden = self.obtener_orden(orden_id)   # solo para saber el CD (no cambia)
        self.procesar_vencimientos()
        claves = [(orden["origen_id"], it["producto_id"]) for it in items or []]
        with self.bloqueos.bloquear(claves):     # 1) candados de producto
            return self._crear_bulto(orden_id, items, usuario_id)

    def _crear_bulto(self, orden_id, items, usuario_id=None):
        # Se vuelve a leer la orden ADENTRO del bloqueo: lo de afuera puede estar viejo
        orden = self.obtener_orden(orden_id)
        self._validar_sucursales_orden_activas(orden)
        reintentar_rechazo = (
            orden["estado"] == "CERRADA"
            and orden["remito_estado"] == "RECHAZADO"
            and orden["resolucion"] is None
        )
        if reintentar_rechazo:
            vencimiento = datetime.fromisoformat(orden["fecha_vencimiento"])
            ahora = datetime.now(vencimiento.tzinfo) if vencimiento.tzinfo else datetime.now()
            if ahora >= vencimiento:
                raise ReglaNegocioError(
                    "La solicitud venció; creá una nueva para reponer las unidades faltantes")
        if orden["estado"] not in ("PENDIENTE", "EN_PREPARACION") and not reintentar_rechazo:
            raise ReglaNegocioError("Solo se pueden armar bultos de órdenes pendientes")
        if orden["remito_estado"] not in (None, "ABIERTO") and not reintentar_rechazo:
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
            producto = self.dao.producto_para_sucursal(
                it["producto_id"], orden["destino_id"])
            if producto is None or not producto["activo"] or not producto["habilitado"]:
                raise ReglaNegocioError(
                    f"El producto {it['producto_id']} está inactivo o deshabilitado "
                    "para el local y no se puede preparar")
            anteriores = self.dao.ordenes_anteriores_pendientes(
                orden["origen_id"], orden_id, it["producto_id"])
            if anteriores:
                raise ReglaNegocioError(
                    f"El producto {it['producto_id']} debe prepararse primero para "
                    f"la orden más antigua pendiente ({anteriores[0]['id']})")

        with self.dao.transaccion():                # 2) recién ahora la transacción
            if reintentar_rechazo:
                remito_id = orden["remito_id"]
                self.dao.reabrir_orden(orden_id)
                self.dao.reabrir_remito(remito_id)
                self.dao.registrar_evento(
                    "REMITO_REABIERTO",
                    f"Orden {orden_id}: se prepara un nuevo intento tras un rechazo")
            else:
                remito_id = orden["remito_id"] or self.dao.crear_remito(
                    f"R-{orden_id:06d}", orden_id)
            bulto_id = self.dao.crear_bulto(remito_id)
            for it in items:
                self.dao.agregar_item_bulto(
                    bulto_id, it["producto_id"], it["cantidad"])
                # Si no alcanza, lanza error y la transacción deshace TODO el bulto
                self.stock.reservar(orden["origen_id"], it["producto_id"], it["cantidad"],
                                    f"bulto {bulto_id}")
            self._registrar_historial(
                bulto_id, EstadoBulto.PREPARADO, "Bulto armado en CD",
                usuario_id=usuario_id)
            self.dao.marcar_orden_en_preparacion(orden_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def precintar(self, bulto_id, usuario_id=None):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        self._validar_sucursales_orden_activas(orden)
        with self.dao.transaccion():
            siguiente = bulto.id
            while True:
                precinto = f"P-{siguiente:06d}"
                existente = self.dao.precinto_existente(precinto)
                if existente is None:
                    break
                siguiente += 1
            self._transicionar(
                bulto, EstadoBulto.PRECINTADO, f"Precinto {precinto}", usuario_id)
            self.dao.asignar_precinto(bulto_id, precinto)
        return self.obtener_bulto(bulto_id).to_dict()

    def reabrir_bulto(self, bulto_id, motivo, usuario_id=None):
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de reapertura")
        bulto = self.obtener_bulto(bulto_id)
        if bulto.estado != EstadoBulto.PRECINTADO:
            raise ReglaNegocioError("Solo se puede reabrir un bulto precintado y no despachado")
        precinto_anterior = bulto.precinto
        with self.dao.transaccion():
            self._transicionar(
                bulto, EstadoBulto.PREPARADO,
                f"Reabierto: {motivo}. Precinto anterior anulado: {precinto_anterior}",
                usuario_id)
            self.dao.reabrir_bulto(bulto_id, precinto_anterior, motivo)
        return self.obtener_bulto(bulto_id).to_dict()

    def anular_bulto(self, bulto_id, motivo, usuario_id=None):
        """Solo antes de despachar: el bulto se cancela y su stock vuelve a estar libre en el CD."""
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la anulación")

        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        claves = [(orden["origen_id"], it["producto_id"]) for it in bulto.items]

        with self.bloqueos.bloquear(claves):
            with self.dao.transaccion():
                self._transicionar(
                    bulto, EstadoBulto.ANULADO, f"Anulado: {motivo}", usuario_id)
                for item in bulto.items:
                    self.stock.liberar_reserva(orden["origen_id"], item["producto_id"], item["cantidad"])
        return self.obtener_bulto(bulto_id).to_dict()

    def despachar(self, bulto_id, usuario_id=None):
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        self._validar_sucursales_orden_activas(orden)

        with self.dao.transaccion():
            self._transicionar(
                bulto, EstadoBulto.EN_TRANSITO, "Despachado desde CD", usuario_id)
            self.dao.fijar_costos_bulto(bulto_id)
            bulto.items = self.dao.items_bulto(bulto_id)
            self.dao.fijar_fecha_despacho(bulto_id)
            self.dao.registrar_usuario_despacho(bulto_id, usuario_id)
            self.dao.marcar_remito_despachado(bulto.remito_id)
            self.dao.marcar_orden_despachada(orden["id"])
            # Observer: StockObserver descuenta del CD (y si no alcanza, lanza error -> rollback)
            self.notificar(Eventos.BULTO_DESPACHADO, {
                "bulto_id": bulto_id, "origen_id": orden["origen_id"], "items": bulto.items})
        return self.obtener_bulto(bulto_id).to_dict()

    def recibir(self, bulto_id, usuario_id=None):
        """Registra que el local recibió físicamente el bulto, sin habilitar el stock."""
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        self._validar_sucursal_activa(orden["destino_id"])
        with self.dao.transaccion():
            self._transicionar(
                bulto, EstadoBulto.RECIBIDO, "Bulto recibido en el local", usuario_id)
            self.dao.fijar_fecha_recepcion(bulto_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def verificar_recepcion(self, bulto_id, aprobado, motivo=None, usuario_id=None):
        """Registra la decisión del local tras revisar físicamente el remito y precinto."""
        bulto = self.obtener_bulto(bulto_id)
        orden = self._orden_de_remito(bulto.remito_id)
        self._validar_sucursal_activa(orden["destino_id"])
        if not isinstance(aprobado, bool):
            raise ReglaNegocioError("aprobado debe ser verdadero o falso")
        with self.dao.transaccion():
            if aprobado:
                self._transicionar(
                    bulto, EstadoBulto.VERIFICADO,
                    "Remito y precinto verificados", usuario_id)
            else:
                motivo = (motivo or "").strip()
                if not motivo:
                    raise ReglaNegocioError(
                        "Debe indicar el motivo del rechazo del bulto")
                self._transicionar(
                    bulto, EstadoBulto.RECHAZADO, motivo, usuario_id)
                self.dao.guardar_motivo_rechazo(bulto_id, motivo)
                self.dao.registrar_notificacion(
                    orden["destino_id"], "BULTO_RECHAZADO", str(bulto_id),
                    f"El bulto {bulto_id} fue rechazado: {motivo}")
                self.dao.registrar_notificacion(
                    orden["origen_id"], "BULTO_RECHAZADO", str(bulto_id),
                    f"El local {orden['destino']} rechazó el bulto {bulto_id}: {motivo}")
                self.notificar(Eventos.BULTO_RECHAZADO, {
                    "bulto_id": bulto_id, "motivo": motivo,
                    "origen_id": orden["origen_id"], "items": bulto.items})

            self._cerrar_remito_si_corresponde(bulto.remito_id)
        return self.obtener_bulto(bulto_id).to_dict()

    def marcar_perdido(self, bulto_id, motivo, usuario_id=None):
        motivo = (motivo or "").strip()
        if not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la pérdida")
        bulto = self.obtener_bulto(bulto_id)
        if bulto.estado != EstadoBulto.EN_TRANSITO:
            raise ReglaNegocioError("Solo se puede marcar perdido un bulto en tránsito")
        fecha = self.dao.fecha_despacho_bulto(bulto_id)["fecha_despacho"]
        fecha_despacho = datetime.fromisoformat(fecha)
        ahora = datetime.now(fecha_despacho.tzinfo) if fecha_despacho.tzinfo else datetime.now()
        if ahora < fecha_despacho + timedelta(hours=48):
            raise ReglaNegocioError(
                "Un bulto solo puede declararse perdido tras 48 horas sin recepción")
        orden = self._orden_de_remito(bulto.remito_id)
        with self.dao.transaccion():
            self._transicionar(
                bulto, EstadoBulto.PERDIDO, f"Declarado perdido: {motivo}", usuario_id)
            self.dao.guardar_motivo_rechazo(bulto_id, motivo)
            self.dao.registrar_notificacion(
                orden["destino_id"], "BULTO_PERDIDO", str(bulto_id),
                f"El bulto {bulto_id} fue declarado perdido: {motivo}")
            self._cerrar_remito_si_corresponde(bulto.remito_id)
            self.notificar(Eventos.BULTO_PERDIDO, {
                "bulto_id": bulto_id, "origen_id": orden["origen_id"],
                "destino_id": orden["destino_id"], "motivo": motivo})
        return self.obtener_bulto(bulto_id).to_dict()

    def _cerrar_remito_si_corresponde(self, remito_id):
        """El stock NO entra al local hasta que el remito completo quede verificado:
        o sea, hasta que todos sus bultos estén en un estado final."""
        bultos = self._bultos_de_remito(remito_id)
        if not all(b.esta_finalizado() for b in bultos):
            return

        verificados = [b for b in bultos if b.estado == EstadoBulto.VERIFICADO]
        perdidos = [b for b in bultos if b.estado == EstadoBulto.PERDIDO]
        rechazados = [b for b in bultos if b.estado == EstadoBulto.RECHAZADO]
        if rechazados:
            self.dao.cerrar_remito(remito_id, "RECHAZADO")
        elif not perdidos:
            self.dao.cerrar_remito(remito_id, "VERIFICADO")
        orden = self._orden_de_remito(remito_id)
        self.dao.cerrar_orden(orden["id"])

        if verificados:
            self.notificar(Eventos.REMITO_VERIFICADO, {
                "remito_numero": orden["remito_numero"],
                "destino_id": orden["destino_id"],
                "items_verificados": [it for b in verificados for it in b.items],
            })

    def resolver_orden(self, orden_id, accion, motivo=None, usuario_id=None):
        accion = (accion or "").strip().upper()
        motivo = (motivo or "").strip()
        if accion not in ("ESPERAR", "RECHAZAR", "CANCELAR"):
            raise ReglaNegocioError("La acción debe ser ESPERAR, RECHAZAR o CANCELAR")
        if accion != "ESPERAR" and not motivo:
            raise ReglaNegocioError("Debe indicar el motivo de la resolución")
        orden = self.obtener_orden(orden_id)
        if accion == "ESPERAR":
            with self.dao.transaccion():
                self.dao.registrar_evento(
                    "ORDEN_EN_ESPERA",
                    f"Orden {orden_id} mantenida pendiente: "
                    f"{motivo or 'sin cambio de estado'}")
            return self.obtener_orden(orden_id)
        if orden["estado"] not in ("PENDIENTE", "EN_PREPARACION"):
            raise ReglaNegocioError("Solo se pueden resolver órdenes pendientes")
        bultos = self._bultos_de_orden(orden_id)
        if any(b.estado not in (EstadoBulto.PREPARADO, EstadoBulto.PRECINTADO,
                                EstadoBulto.ANULADO)
               for b in bultos):
            raise ReglaNegocioError(
                "No se puede resolver una orden con bultos ya despachados")
        claves = [(orden["origen_id"], item["producto_id"])
                  for b in bultos for item in b.items]
        resolucion = "RECHAZADA" if accion == "RECHAZAR" else "CANCELADA"
        with self.bloqueos.bloquear(claves):
            with self.dao.transaccion():
                if not self.dao.cerrar_orden_con_resolucion(
                        orden_id, resolucion, motivo):
                    raise ReglaNegocioError(
                        "Conflicto: la orden cambió mientras intentabas resolverla")
                for bulto in bultos:
                    if bulto.estado in (EstadoBulto.PREPARADO, EstadoBulto.PRECINTADO):
                        self._transicionar(
                            bulto, EstadoBulto.ANULADO,
                            f"Orden {resolucion.lower()}: {motivo}", usuario_id)
                        for item in bulto.items:
                            self.stock.liberar_reserva(
                                orden["origen_id"], item["producto_id"], item["cantidad"])
                self.dao.registrar_evento(
                    f"ORDEN_{resolucion}",
                    f"Orden {orden_id} {resolucion.lower()}: {motivo}")
                self.dao.registrar_notificacion(
                    orden["destino_id"], f"ORDEN_{resolucion}", str(orden_id),
                    f"La orden {orden_id} fue {resolucion.lower()}: {motivo}")
        return self.obtener_orden(orden_id)

    def procesar_vencimientos(self):
        with self.dao.transaccion():
            for orden in self.dao.ordenes_proximas_a_vencer():
                if self.dao.marcar_aviso_vencimiento(orden["id"]):
                    self.dao.registrar_evento(
                        "ORDEN_POR_VENCER",
                        f"Orden {orden['id']} vence dentro de las próximas 24 horas")
                    self.dao.registrar_notificacion(
                        orden["destino_id"], "ORDEN_POR_VENCER", str(orden["id"]),
                        f"La solicitud {orden['id']} vence dentro de las próximas 24 horas.")
        for fila in self.dao.ordenes_vencidas():
            orden = self.obtener_orden(fila["id"])
            bultos = self._bultos_de_orden(fila["id"])
            if any(b.estado not in (EstadoBulto.PREPARADO, EstadoBulto.PRECINTADO,
                                    EstadoBulto.ANULADO)
                   for b in bultos):
                continue
            claves = [(orden["origen_id"], item["producto_id"])
                      for b in bultos for item in b.items]
            with self.bloqueos.bloquear(claves):
                with self.dao.transaccion():
                    if not self.dao.cerrar_orden_con_resolucion(
                            fila["id"], "VENCIDA", "Vencimiento a los 30 días"):
                        continue
                    for bulto in bultos:
                        if bulto.estado in (EstadoBulto.PREPARADO, EstadoBulto.PRECINTADO):
                            self._transicionar(
                                bulto, EstadoBulto.ANULADO,
                                "Orden vencida a los 30 días")
                            for item in bulto.items:
                                self.stock.liberar_reserva(
                                    orden["origen_id"], item["producto_id"], item["cantidad"])
                    self.dao.registrar_evento(
                        "ORDEN_VENCIDA",
                        f"Orden {fila['id']} vencida; reservas liberadas")
                    self.dao.registrar_notificacion(
                        orden["destino_id"], "ORDEN_VENCIDA", str(fila["id"]),
                        f"La solicitud {fila['id']} venció; las reservas fueron liberadas.")

    def notificaciones(self, sucursal_id):
        self.procesar_vencimientos()
        with self.dao.transaccion():
            notificaciones = self.dao.listar_notificaciones(sucursal_id)
            self.dao.marcar_notificaciones_leidas(sucursal_id)
        return notificaciones

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

    def _transicionar(self, bulto: Bulto, nuevo_estado, observacion, usuario_id=None):
        desde_estado = bulto.estado
        try:
            bulto.cambiar_estado(nuevo_estado)    # el modelo valida la transición
        except ValueError as e:
            raise ReglaNegocioError(str(e))
        actualizadas = self.dao.actualizar_estado_bulto_desde(
            bulto.id, desde_estado, nuevo_estado)
        if not actualizadas:
            estado_actual = self.dao.obtener_bulto(bulto.id)["estado"]
            raise ReglaNegocioError(
                f"Conflicto: el bulto {bulto.id} ya cambió de estado; "
                f"estado actual: {estado_actual}")
        self._registrar_historial(
            bulto.id, nuevo_estado, observacion, desde_estado, usuario_id)

    def _registrar_historial(self, bulto_id, estado, observacion, desde_estado=None,
                             usuario_id=None):
        bulto = self.dao.obtener_bulto(bulto_id)
        self.dao.registrar_historial(
            bulto_id, estado, observacion, desde_estado, usuario_id, bulto["intento"])

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

    def _validar_sucursal_activa(self, sucursal_id):
        sucursal = self.dao.obtener_sucursal(sucursal_id)
        if sucursal is None:
            raise NoEncontradoError(f"No existe la sucursal {sucursal_id}")
        if not sucursal["activo"]:
            raise ReglaNegocioError("No se puede operar con una sucursal inactiva")

    def _validar_sucursales_orden_activas(self, orden):
        self._validar_sucursal_activa(orden["origen_id"])
        self._validar_sucursal_activa(orden["destino_id"])

    def _validar_items(self, items):
        vistos = set()
        for it in items:
            if not isinstance(it, dict):
                raise ReglaNegocioError("Cada línea debe incluir producto_id y cantidad")
            producto_id = it.get("producto_id")
            cantidad = it.get("cantidad")
            if isinstance(cantidad, bool) or not isinstance(cantidad, int) or cantidad <= 0:
                raise ReglaNegocioError(
                    f"La cantidad del producto {producto_id} debe ser un entero positivo")
            if isinstance(producto_id, bool) or not isinstance(producto_id, int):
                raise ReglaNegocioError("El producto_id debe ser un entero")
            if producto_id in vistos:
                raise ReglaNegocioError(f"Producto {producto_id} repetido")
            vistos.add(producto_id)
            producto = self.dao.existe_producto(producto_id)
            if not producto:
                raise NoEncontradoError(f"No existe el producto {producto_id}")
            if not producto["activo"]:
                raise ReglaNegocioError(f"El producto {producto_id} está inactivo")
