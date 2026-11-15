from dao.reportes_dao import ReportesDAO
from datetime import datetime, timedelta

from services.analisis import (
    estadistica_tickets,
    periodos_con_stock,
    resumen_permanencia,
)

class ReportesService:
    def __init__(self):
        self.dao = ReportesDAO()

    def resumen(self, desde=None, hasta=None, sucursal_id=None):
        where_ventas, params_ventas = self.dao.filtro_fechas("v.fecha", desde, hasta)
        ventas = self.dao.resumen_ventas(where_ventas, params_ventas, sucursal_id)

        where_devoluciones, params_devoluciones = self.dao.filtro_fechas(
            "d.fecha", desde, hasta)
        devoluciones = self.dao.resumen_devoluciones(
            where_devoluciones, params_devoluciones, sucursal_id)

        locales = []
        if sucursal_id is None:
            locales = self.dao.local_lider(
                where_devoluciones, params_devoluciones,
                where_ventas, params_ventas)
        producto_mas_vendido = next(
            (producto for producto in self.mas_vendidos(desde, hasta, sucursal_id)
             if producto["unidades"] > 0),
            None,
        )
        existencias_bajas = sum(
            fila["estado"] == "BAJO MÍNIMO"
            for fila in self.existencias(sucursal_id)
        )
        cantidad_ventas = ventas["cantidad"]
        importe_devuelto = devoluciones["importe"]
        ingresos_netos = round(ventas["ingresos"] - importe_devuelto, 2)
        return {
            "ventas": cantidad_ventas,
            "ingresos": ventas["ingresos"],
            "unidades_vendidas": ventas["unidades"],
            "ticket_promedio": round(ventas["ingresos"] / cantidad_ventas, 2)
                if cantidad_ventas else 0,
            "devoluciones": devoluciones["cantidad"],
            "importe_devuelto": importe_devuelto,
            "ingresos_netos": ingresos_netos,
            "local_mas_vendio": locales[0] if locales else None,
            "producto_mas_vendido": producto_mas_vendido,
            "productos_bajo_minimo": existencias_bajas,
        }

    def bultos_rechazados(self, desde=None, hasta=None):
        filtros, parametros = ["b.estado = 'RECHAZADO'"], []
        if desde:
            filtros.append("date(b.fecha_recepcion) >= date(?)")
            parametros.append(desde)
        if hasta:
            filtros.append("date(b.fecha_recepcion) <= date(?)")
            parametros.append(hasta)
        return self.dao.rechazados(filtros, parametros)

    def tiempo_promedio_transito(self, sucursal_id=None):
        return {
            "promedios_verificados": self.dao.tiempo_promedio_transito(sucursal_id),
            "estados": self.dao.estados_transito(sucursal_id),
            "alertas_verificacion": self.dao.alertas_verificacion(sucursal_id),
        }

    def existencias(self, sucursal_id=None):
        return self.dao.existencias(sucursal_id)

    def movimientos(self, sucursal_id=None, tipos=None):
        if tipos is None:
            tipos = ("VENTA", "DEVOLUCION", "RECEPCION")
        return self.dao.movimientos(sucursal_id, tipos)

    def ventas(self, desde=None, hasta=None, sucursal_id=None):
        where, parametros = self.dao.filtro_fechas("v.fecha", desde, hasta)
        if sucursal_id is not None:
            where += " AND v.sucursal_id = ?"
            parametros += (sucursal_id,)
        return self.dao.ventas(where, parametros)

    def mas_vendidos(self, desde=None, hasta=None, sucursal_id=None):
        where, parametros = self.dao.filtro_fechas("v.fecha", desde, hasta)
        where_vendido = where
        params_vendido = parametros
        if sucursal_id is not None:
            where_vendido += " AND v.sucursal_id = ?"
            params_vendido += (sucursal_id,)
        where_devuelto = where
        params_devuelto = parametros
        if sucursal_id is not None:
            where_devuelto += " AND v.sucursal_id = ?"
            params_devuelto += (sucursal_id,)
        return self.dao.mas_vendidos(
            where_vendido, params_vendido, where_devuelto, params_devuelto)

    #pase el estado_ordenes al service asi mantenemos las RN en el service y no en el dao
    def estado_ordenes(self):
        limite = datetime.now() - timedelta(days=2)        # hace 2 días
        resumen = {}                                        # una entrada por estado
        for orden in self.dao.ordenes():
            estado = orden["estado"]
            if estado not in resumen:                      #por si es la primera vez que aparece un estado
                resumen[estado] = {"estado": estado, "ordenes": 0, "demoradas": 0}
            resumen[estado]["ordenes"] += 1                 # contador

            fecha = datetime.strptime(orden["fecha"], "%Y-%m-%d %H:%M:%S") #%Y-%m-%d %H:%M:%S convierte el texto de la base en un objeto datetime(segun el agus)
            if estado in ("PENDIENTE", "EN_PREPARACION") and fecha < limite:
                resumen[estado]["demoradas"] += 1           # contador de demoradas
        return list(resumen.values())

    def abastecimiento(self): #aca le pedi los datos al DAO y los devuelve(creo que no hay que poner mas nada aca)
        return self.dao.abastecimiento()
    
    def ventas_por_medio_pago(self, sucursal_id=None): #idem a def abastecimiento, solo que puse el sucursal_id y se lo pasa al DAO
        return self.dao.ventas_por_medio_pago(sucursal_id)

    def devoluciones_por_producto(self, sucursal_id=None):
      return self.dao.devoluciones_por_producto(sucursal_id)
    # ================================================================
    #  REPORTE GERENCIAL DE UN LOCAL (pantalla "Reportes" del local)
    # ================================================================
    def reporte_local(self, sucursal_id, desde=None, hasta=None, anio=None):
        """Arma todas las secciones del reporte del local para un período
        (desde/hasta) o un año completo. Cada sección usa datos reales; cuando
        algo no se puede calcular se devuelve None y un mensaje."""
        if anio is not None:
            desde, hasta = f"{anio}-01-01", f"{anio}-12-31"
        where_v, params_v = self.dao.filtro_fechas("v.fecha", desde, hasta)

        tickets = self.dao.tickets(sucursal_id, where_v, params_v)
        meses = _meses_del_periodo(desde, hasta, anio, tickets)

        return {
            "periodo": {"desde": desde, "hasta": hasta, "anio": anio, "meses": meses},
            "anios_disponibles": self.dao.anios_con_datos(sucursal_id),
            "resumen": _resumen_ventas(tickets, meses),
            "medios_pago": self._medios_pago(sucursal_id, where_v, params_v),
            "productos": {
                "ranking": [
                    {"codigo": p["codigo"], "producto": p["producto"],
                     "unidades": p["unidades"], "ingresos": p["ingresos"]}
                    for p in self.mas_vendidos(desde, hasta, sucursal_id)
                    if p["unidades"] > 0],
                "por_mes": self.dao.unidades_por_producto_y_mes(
                    sucursal_id, where_v, params_v),
            },
            "estadistica": self._estadistica(tickets),
            "stock": self._stock(sucursal_id, desde, hasta),
            "devoluciones": self._devoluciones(sucursal_id, desde, hasta),
            **self._logistica(sucursal_id, desde, hasta, tickets, meses),
        }

    def _medios_pago(self, sucursal_id, where, parametros):
        filas = self.dao.ventas_por_medio_pago(sucursal_id, where, parametros)
        total = sum(f["ingresos"] for f in filas)
        return [{**f, "porcentaje": round(100 * f["ingresos"] / total, 1) if total else 0}
                for f in filas]

    def _estadistica(self, tickets):
        resultado = estadistica_tickets([t["total"] for t in tickets])
        alto = resultado.get("limite_atipico_alto")
        bajo = resultado.get("limite_atipico_bajo")
        resultado["puntos"] = [
            {"id": t["id"], "fecha": t["fecha"], "total": t["total"],
             "unidades": t["unidades"],
             "atipico": resultado["suficiente"] and (t["total"] > alto or t["total"] < bajo)}
            for t in tickets]
        return resultado

    def _stock(self, sucursal_id, desde, hasta):
        existencias = [
            {"producto": f["producto"], "libre": f["libre"], "minimo": f["stock_minimo"],
             "diferencia": f["libre"] - f["stock_minimo"],
             "estado": ("BAJO" if f["libre"] < f["stock_minimo"]
                        else "CERCA" if f["libre"] < f["stock_minimo"] * 1.5 else "OK")}
            for f in self.dao.existencias(sucursal_id)]
        movimientos = self.dao.movimientos_de_stock(sucursal_id, hasta)
        periodos = periodos_con_stock(movimientos, desde, hasta)
        return {
            "existencias": sorted(existencias, key=lambda e: e["diferencia"]),
            "alertas": self.dao.alertas_pendientes(sucursal_id),
            "permanencia": {
                "historial_desde": min((m["fecha"] for m in movimientos), default=None),
                "periodos": periodos,
                **resumen_permanencia(periodos),
            },
        }

    def _devoluciones(self, sucursal_id, desde, hasta):
        where_d, params_d = self.dao.filtro_fechas("d.fecha", desde, hasta)
        filas = self.dao.devoluciones_por_producto(sucursal_id, where_d, params_d)
        return {
            "por_producto": filas,
            "unidades": sum(f["unidades"] for f in filas),
            "importe": round(sum(f["importe"] or 0 for f in filas), 2),
        }

    def _logistica(self, sucursal_id, desde, hasta, tickets, meses):
        where_o, params_o = self.dao.filtro_fechas("o.fecha", desde, hasta)
        ordenes = self.dao.ordenes_del_local(sucursal_id, where_o, params_o)
        bultos = self.dao.bultos_del_local(sucursal_id)

        # --- estado de las órdenes pedidas en el período ---
        estados = {"pendientes": 0, "en_transito": 0, "entregadas": 0,
                   "canceladas": 0, "rechazadas": 0, "vencidas": 0}
        for o in ordenes:
            if o["estado"] in ("PENDIENTE", "EN_PREPARACION"):
                estados["pendientes"] += 1
            elif o["estado"] == "DESPACHADA":
                estados["en_transito"] += 1
            elif o["resolucion"] is None:
                estados["entregadas"] += 1
            else:
                estados[{"CANCELADA": "canceladas", "RECHAZADA": "rechazadas",
                         "VENCIDA": "vencidas"}[o["resolucion"]]] += 1

        # --- tiempo de tránsito: bultos recibidos en el período ---
        recibidos = [b for b in bultos
                     if b["fecha_despacho"] and b["fecha_recepcion"]
                     and _en_rango(b["fecha_recepcion"], desde, hasta)]
        horas = [_horas_entre(b["fecha_despacho"], b["fecha_recepcion"]) for b in recibidos]

        # --- bultos pedidos en el período (los anulados no se enviaron) ---
        pedidos = [b for b in bultos if b["estado"] != "ANULADO"
                   and _en_rango(b["fecha_pedido"], desde, hasta)]
        ventas = len(tickets)
        por_cd = {}
        for o in ordenes:
            por_cd.setdefault(o["cd"], {"cd": o["cd"], "pedidos": 0, "bultos": 0,
                                        "unidades": 0})["pedidos"] += 1
        for b in pedidos:
            fila = por_cd.setdefault(b["cd"], {"cd": b["cd"], "pedidos": 0,
                                                "bultos": 0, "unidades": 0})
            fila["bultos"] += 1
            fila["unidades"] += b["unidades"]
        for fila in por_cd.values():
            fila["porcentaje_bultos"] = (round(100 * fila["bultos"] / len(pedidos), 1)
                                         if pedidos else 0)

        mensual = {m: {"mes": m, "pedidos": 0, "bultos": 0, "ventas": 0} for m in meses}
        for o in ordenes:
            if o["fecha"][:7] in mensual:
                mensual[o["fecha"][:7]]["pedidos"] += 1
        for b in pedidos:
            if b["fecha_pedido"][:7] in mensual:
                mensual[b["fecha_pedido"][:7]]["bultos"] += 1
        for t in tickets:
            if t["mes"] in mensual:
                mensual[t["mes"]]["ventas"] += 1

        # --- rechazos (por la fecha en que el local los rechazó) ---
        where_r, params_r = self.dao.filtro_fechas("b.fecha_recepcion", desde, hasta)
        rechazados = [b for b in bultos if b["estado"] == "RECHAZADO"
                      and _en_rango(b["fecha_recepcion"], desde, hasta)]
        rechazos_mes, rechazos_cd = {}, {}
        for b in rechazados:
            mes = b["fecha_recepcion"][:7]
            rechazos_mes[mes] = rechazos_mes.get(mes, 0) + 1
            rechazos_cd[b["cd"]] = rechazos_cd.get(b["cd"], 0) + 1

        return {
            "ordenes": {
                "total": len(ordenes),
                **estados,
                "transito_horas_promedio": round(sum(horas) / len(horas), 1) if horas else None,
                "bultos_medidos": len(horas),
            },
            "rechazos": {
                "cantidad": len(rechazados),
                "unidades": sum(b["unidades"] for b in rechazados),
                "por_producto": self.dao.productos_rechazados(sucursal_id, where_r, params_r),
                "por_cd": [{"cd": cd, "bultos": n} for cd, n in sorted(
                    rechazos_cd.items(), key=lambda x: -x[1])],
                "por_mes": [{"mes": m, "bultos": rechazos_mes.get(m, 0)} for m in meses],
            },
            "logistica": {
                "pedidos": len(ordenes),
                "bultos": len(pedidos),
                "unidades": sum(b["unidades"] for b in pedidos),
                "ventas": ventas,
                # Relación = ventas / bultos. Sin bultos no se puede calcular.
                "ventas_por_bulto": round(ventas / len(pedidos), 1) if pedidos else None,
                "por_cd": sorted(por_cd.values(), key=lambda f: -f["bultos"]),
                "mensual": list(mensual.values()),
            },
        }


# ---------------------------------------------------------------------------
#  Ayudas del reporte del local
# ---------------------------------------------------------------------------
def _en_rango(fecha, desde, hasta):
    if not fecha:
        return False
    dia = fecha[:10]
    return (not desde or dia >= desde) and (not hasta or dia <= hasta)


def _horas_entre(inicio, fin):
    formato = "%Y-%m-%d %H:%M:%S"
    return (datetime.strptime(fin[:19], formato)
            - datetime.strptime(inicio[:19], formato)).total_seconds() / 3600


def _meses_del_periodo(desde, hasta, anio, tickets):
    """Lista 'AAAA-MM' de todos los meses del período (también los que no
    tuvieron ventas, para que los gráficos muestren los meses en cero)."""
    if anio is not None:
        return [f"{anio}-{m:02d}" for m in range(1, 13)]
    inicio = desde[:7] if desde else (tickets[0]["mes"] if tickets else None)
    fin = hasta[:7] if hasta else datetime.now().strftime("%Y-%m")
    if inicio is None:
        return []
    meses, anio_actual, mes_actual = [], int(inicio[:4]), int(inicio[5:7])
    while f"{anio_actual}-{mes_actual:02d}" <= fin:
        meses.append(f"{anio_actual}-{mes_actual:02d}")
        mes_actual += 1
        if mes_actual == 13:
            anio_actual, mes_actual = anio_actual + 1, 1
    return meses


def _resumen_ventas(tickets, meses):
    cantidad = len(tickets)
    facturado = round(sum(t["total"] for t in tickets), 2)
    mensual = {m: {"mes": m, "ventas": 0, "facturado": 0.0, "unidades": 0} for m in meses}
    for t in tickets:
        fila = mensual.setdefault(t["mes"], {"mes": t["mes"], "ventas": 0,
                                             "facturado": 0.0, "unidades": 0})
        fila["ventas"] += 1
        fila["facturado"] += t["total"]
        fila["unidades"] += t["unidades"]
    filas = sorted(mensual.values(), key=lambda f: f["mes"])
    for f in filas:
        f["facturado"] = round(f["facturado"], 2)
        # Ticket promedio = total facturado / cantidad de ventas (si hubo ventas)
        f["ticket_promedio"] = round(f["facturado"] / f["ventas"], 2) if f["ventas"] else None
    con_ventas = [f for f in filas if f["ventas"]]
    return {
        "ventas": cantidad,
        "facturado": facturado,
        "ticket_promedio": round(facturado / cantidad, 2) if cantidad else None,
        "unidades": sum(t["unidades"] for t in tickets),
        "mes_mayor_facturacion": max(con_ventas, key=lambda f: f["facturado"])
            if con_ventas else None,
        "mes_mayor_ventas": max(con_ventas, key=lambda f: f["ventas"]) if con_ventas else None,
        "mensual": filas,
    }
