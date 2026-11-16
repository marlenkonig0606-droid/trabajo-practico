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
            "primera_fecha": self.dao.primera_fecha(sucursal_id),
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


    # ================================================================
    #  REPORTE DEL CENTRO DE DISTRIBUCIÓN (toda la red de locales)
    # ================================================================
    def reporte_cd(self, desde=None, hasta=None, anio=None, cd_id=None):
        """Resultado económico de la red, ventas por local y por producto,
        top 10, pedidos de reposición (por local y si llegaron completos) y
        estacionalidad. cd_id limita los pedidos a los que atendió ese CD."""
        if anio is not None:
            desde, hasta = f"{anio}-01-01", f"{anio}-12-31"
        where_v, params_v = self.dao.filtro_fechas("v.fecha", desde, hasta)
        where_d, params_d = self.dao.filtro_fechas("d.fecha", desde, hasta)
        where_o, params_o = self.dao.filtro_fechas("o.fecha", desde, hasta)
        where_p, params_p = self.dao.filtro_fechas("h.fecha", desde, hasta)

        vendido = self.dao.ventas_por_local_producto_mes(where_v, params_v)
        devuelto = self.dao.devoluciones_por_local_producto_mes(where_d, params_d)
        tickets = self.dao.ventas_por_local_y_mes(where_v, params_v)
        perdidos = self.dao.bultos_perdidos(where_p, params_p)
        ordenes = self.dao.ordenes_para_cumplimiento(where_o, params_o, cd_id)
        locales = self.dao.locales_activos()

        primer_mes = min([f["mes"] for f in vendido] + [o["fecha"][:7] for o in ordenes],
                         default=None)
        meses = _meses_del_periodo(desde, hasta, anio,
                                   [{"mes": primer_mes}] if primer_mes else [])

        return {
            "periodo": {"desde": desde, "hasta": hasta, "anio": anio, "meses": meses},
            "anios_disponibles": self.dao.anios_con_datos_red(),
            "primera_fecha": self.dao.primera_fecha(),
            "locales": locales,
            "resultado": _resultado(vendido, devuelto, perdidos, meses),
            "ventas_por_local": _ventas_por_local(vendido, devuelto, tickets, locales, meses),
            "productos": _productos_por_local(vendido, devuelto, locales),
            "pedidos": _cumplimiento_pedidos(ordenes, locales),
            "estacionalidad": _estacionalidad(vendido, meses),
            "entradas": self._entradas_cds(desde, hasta, meses),
        }

    def _entradas_cds(self, desde, hasta, meses):
        """Mercadería que entra a cada CD (compras a proveedores) y que sale
        (despachos a los locales), para ver si el abastecimiento acompaña."""
        where_m, params_m = self.dao.filtro_fechas("m.fecha", desde, hasta)
        filas = self.dao.movimientos_de_cds(where_m, params_m)
        stock = self.dao.stock_de_cds()
        cds = {f["cd"]: {"cd": f["cd"], "ingresado": 0, "ingresado_valor": 0.0,
                         "ingresos": 0, "despachado": 0, "despachado_valor": 0.0,
                         "reingresado": 0, "ajustes": 0,
                         "stock_actual": f["unidades"], "stock_valor": _r(f["valor"]),
                         "mensual": {m: {"mes": m, "entradas": 0, "salidas": 0} for m in meses}}
               for f in stock}
        proveedores = {}
        for f in filas:
            c = cds.setdefault(f["cd"], {"cd": f["cd"], "ingresado": 0, "ingresado_valor": 0.0,
                                         "ingresos": 0, "despachado": 0, "despachado_valor": 0.0,
                                         "reingresado": 0, "ajustes": 0, "stock_actual": 0,
                                         "stock_valor": 0,
                                         "mensual": {m: {"mes": m, "entradas": 0, "salidas": 0}
                                                     for m in meses}})
            mes = c["mensual"].setdefault(f["mes"], {"mes": f["mes"], "entradas": 0, "salidas": 0})
            if f["motivo"] == "INGRESO_PROVEEDOR":
                c["ingresado"] += f["unidades"]
                c["ingresado_valor"] += f["valor"] or 0
                c["ingresos"] += f["documentos"]
                mes["entradas"] += f["unidades"]
                p = proveedores.setdefault(f["proveedor"], {"proveedor": f["proveedor"],
                                                            "unidades": 0, "valor": 0.0})
                p["unidades"] += f["unidades"]
                p["valor"] += f["valor"] or 0
            elif f["motivo"] == "DESPACHO":
                c["despachado"] += -f["unidades"]
                c["despachado_valor"] += -(f["valor"] or 0)
                mes["salidas"] += -f["unidades"]
            elif f["motivo"] == "RECHAZO_REINGRESO":
                c["reingresado"] += f["unidades"]
                mes["entradas"] += f["unidades"]
            elif not f["motivo"].startswith("APERTURA"):
                c["ajustes"] += f["unidades"]
        resultado = []
        for c in sorted(cds.values(), key=lambda c: c["cd"]):
            mensual = sorted(c.pop("mensual").values(), key=lambda m: m["mes"])
            resultado.append({**c, "ingresado_valor": _r(c["ingresado_valor"]),
                              "despachado_valor": _r(c["despachado_valor"]),
                              # Cobertura: cuántas veces lo que entró cubre lo que salió
                              "cobertura": round(c["ingresado"] / c["despachado"], 2)
                                           if c["despachado"] else None,
                              "mensual": mensual})
        where_u, params_u = self.dao.filtro_fechas("m.fecha", desde, hasta)
        return {
            "por_cd": resultado,
            "por_proveedor": sorted(({**p, "valor": _r(p["valor"])} for p in proveedores.values()),
                                    key=lambda p: -p["valor"]),
            "ultimos": self.dao.ultimos_ingresos_a_cds(where_u, params_u),
        }


# ---------------------------------------------------------------------------
#  Ayudas del reporte del CD
# ---------------------------------------------------------------------------
def _r(valor):
    return round(valor or 0, 2)


def _resultado(vendido, devuelto, perdidos, meses):
    """Ganancia (o pérdida) = ventas netas de devoluciones
    - costo de la mercadería vendida - mercadería perdida en tránsito."""
    mensual = {m: {"mes": m, "ingresos": 0.0, "costo": 0.0, "perdidas": 0.0} for m in meses}

    def fila(mes):
        return mensual.setdefault(mes, {"mes": mes, "ingresos": 0.0, "costo": 0.0,
                                        "perdidas": 0.0})
    for f in vendido:
        fila(f["mes"])["ingresos"] += f["ingresos"]
        fila(f["mes"])["costo"] += f["costo"]
    for f in devuelto:
        fila(f["mes"])["ingresos"] -= f["importe"]
        fila(f["mes"])["costo"] -= f["costo"]
    for f in perdidos:
        fila(f["mes"])["perdidas"] += f["valor"] or 0
    filas = sorted(mensual.values(), key=lambda f: f["mes"])
    for f in filas:
        f["resultado"] = _r(f["ingresos"] - f["costo"] - f["perdidas"])
        f["ingresos"], f["costo"], f["perdidas"] = _r(f["ingresos"]), _r(f["costo"]), _r(f["perdidas"])

    brutos = sum(f["ingresos"] for f in vendido)
    devoluciones = sum(f["importe"] for f in devuelto)
    netos = brutos - devoluciones
    costo = sum(f["costo"] for f in vendido) - sum(f["costo"] for f in devuelto)
    perdidas = sum(f["valor"] or 0 for f in perdidos)
    resultado = netos - costo - perdidas
    return {
        "ingresos_brutos": _r(brutos),
        "devoluciones": _r(devoluciones),
        "ingresos_netos": _r(netos),
        "costo_vendido": _r(costo),
        "ganancia_bruta": _r(netos - costo),
        "perdidas_transito": _r(perdidas),
        "bultos_perdidos": len(perdidos),
        "resultado": _r(resultado),
        "es_ganancia": resultado >= 0,
        "margen_pct": round(100 * resultado / netos, 1) if netos else None,
        "mensual": filas,
    }


def _ventas_por_local(vendido, devuelto, tickets, locales, meses):
    datos = {l["id"]: {"sucursal_id": l["id"], "local": l["nombre"], "ventas": 0,
                       "unidades": 0, "facturado": 0.0, "costo": 0.0,
                       "mensual": {m: 0.0 for m in meses}}
             for l in locales}

    def fila(f):
        return datos.setdefault(f["sucursal_id"], {
            "sucursal_id": f["sucursal_id"], "local": f.get("local", "Local inactivo"),
            "ventas": 0, "unidades": 0, "facturado": 0.0, "costo": 0.0,
            "mensual": {m: 0.0 for m in meses}})
    for f in vendido:
        d = fila(f)
        d["unidades"] += f["unidades"]
        d["facturado"] += f["ingresos"]
        d["costo"] += f["costo"]
        d["mensual"][f["mes"]] = d["mensual"].get(f["mes"], 0) + f["ingresos"]
    for f in devuelto:
        d = fila(f)
        d["unidades"] -= f["unidades"]
        d["facturado"] -= f["importe"]
        d["costo"] -= f["costo"]
        d["mensual"][f["mes"]] = d["mensual"].get(f["mes"], 0) - f["importe"]
    for f in tickets:
        fila(f)["ventas"] += f["ventas"]
    total = sum(d["facturado"] for d in datos.values())
    filas = []
    for d in datos.values():
        filas.append({
            "sucursal_id": d["sucursal_id"], "local": d["local"], "ventas": d["ventas"],
            "unidades": d["unidades"], "facturado": _r(d["facturado"]),
            "ganancia": _r(d["facturado"] - d["costo"]),
            "ticket_promedio": _r(d["facturado"] / d["ventas"]) if d["ventas"] else None,
            "participacion": round(100 * d["facturado"] / total, 1) if total else 0,
            "mensual": [{"mes": m, "facturado": _r(v)} for m, v in sorted(d["mensual"].items())],
        })
    return sorted(filas, key=lambda f: -f["facturado"])


def _productos_por_local(vendido, devuelto, locales):
    """Unidades e ingresos netos por producto y por local + top 10 de la red."""
    nombres = {l["id"]: l["nombre"] for l in locales}
    productos = {}
    for f in vendido:
        nombres.setdefault(f["sucursal_id"], f["local"])
        p = productos.setdefault(f["producto_id"], {
            "producto": f["producto"], "unidades": 0, "ingresos": 0.0, "costo": 0.0,
            "por_local": {}})
        p["unidades"] += f["unidades"]
        p["ingresos"] += f["ingresos"]
        p["costo"] += f["costo"]
        l = p["por_local"].setdefault(f["sucursal_id"], {"unidades": 0, "ingresos": 0.0})
        l["unidades"] += f["unidades"]
        l["ingresos"] += f["ingresos"]
    for f in devuelto:
        p = productos.get(f["producto_id"])
        if p is None:
            continue
        p["unidades"] -= f["unidades"]
        p["ingresos"] -= f["importe"]
        p["costo"] -= f["costo"]
        l = p["por_local"].setdefault(f["sucursal_id"], {"unidades": 0, "ingresos": 0.0})
        l["unidades"] -= f["unidades"]
        l["ingresos"] -= f["importe"]
    filas = [{
        "producto": p["producto"], "unidades": p["unidades"], "ingresos": _r(p["ingresos"]),
        "ganancia": _r(p["ingresos"] - p["costo"]),
        "por_local": [{"local": nombres[sid], "unidades": v["unidades"],
                       "ingresos": _r(v["ingresos"])}
                      for sid, v in sorted(p["por_local"].items(), key=lambda x: nombres[x[0]])],
    } for p in productos.values()]
    filas.sort(key=lambda f: (-f["unidades"], f["producto"]))
    return {"por_local": filas, "top": filas[:10],
            "locales": sorted({nombres[sid] for p in productos.values() for sid in p["por_local"]})}


ESTADOS_EN_CURSO = ("PENDIENTE", "EN_PREPARACION", "DESPACHADA")
CAUSAS = {"RECHAZADA": "Rechazada por el CD", "CANCELADA": "Cancelada por el local",
          "VENCIDA": "Vencida sin atender"}


def _cumplimiento_pedidos(ordenes, locales):
    """Completo: el local recibió y verificó TODO lo que pidió.
    Incompleto: la orden terminó y llegó menos (bultos rechazados o perdidos)
    o no llegó nada (rechazada, cancelada o vencida).
    En curso: todavía no terminó, no se puede juzgar."""
    por_local = {l["nombre"]: {"local": l["nombre"], "pedidos": 0, "unidades": 0,
                               "completos": 0, "incompletos": 0, "en_curso": 0}
                 for l in locales}
    causas, faltantes = {}, 0
    completos = incompletos = en_curso = 0
    for o in ordenes:
        fila = por_local.setdefault(o["local"], {"local": o["local"], "pedidos": 0,
                                                 "unidades": 0, "completos": 0,
                                                 "incompletos": 0, "en_curso": 0})
        fila["pedidos"] += 1
        fila["unidades"] += o["pedidas"] or 0
        if o["estado"] in ESTADOS_EN_CURSO and o["resolucion"] is None:
            fila["en_curso"] += 1
            en_curso += 1
        elif o["resolucion"] is None and o["recibidas"] >= (o["pedidas"] or 0):
            fila["completos"] += 1
            completos += 1
        else:
            fila["incompletos"] += 1
            incompletos += 1
            causa = CAUSAS.get(o["resolucion"], "Llegó con faltantes")
            causas[causa] = causas.get(causa, 0) + 1
            faltantes += max((o["pedidas"] or 0) - o["recibidas"], 0)
    terminados = completos + incompletos
    filas = sorted(por_local.values(), key=lambda f: -f["pedidos"])
    for f in filas:
        cerrados = f["completos"] + f["incompletos"]
        f["cumplimiento_pct"] = round(100 * f["completos"] / cerrados, 1) if cerrados else None
    return {
        "total": len(ordenes),
        "completos": completos,
        "incompletos": incompletos,
        "en_curso": en_curso,
        "cumplimiento_pct": round(100 * completos / terminados, 1) if terminados else None,
        "unidades_faltantes": faltantes,
        "causas": [{"causa": c, "pedidos": n} for c, n in
                   sorted(causas.items(), key=lambda x: -x[1])],
        "por_local": filas,
    }


def _estacionalidad(vendido, meses):
    """Unidades vendidas de cada producto en cada mes (toda la red).
    Índice estacional del mes = unidades del mes / promedio mensual del producto
    (1 = mes normal, 1,3 = se vendió 30 % más que en un mes promedio)."""
    productos = {}
    for f in vendido:
        p = productos.setdefault(f["producto"], {m: 0 for m in meses})
        p[f["mes"]] = p.get(f["mes"], 0) + f["unidades"]
    filas = []
    for nombre, por_mes in productos.items():
        valores = [por_mes.get(m, 0) for m in meses]
        total = sum(valores)
        promedio = total / len(meses) if meses else 0
        pico = max(range(len(meses)), key=lambda i: valores[i]) if meses else None
        valle = min(range(len(meses)), key=lambda i: valores[i]) if meses else None
        filas.append({
            "producto": nombre, "valores": valores, "total": total,
            "promedio_mensual": round(promedio, 1),
            "mes_pico": meses[pico] if pico is not None else None,
            "mes_valle": meses[valle] if valle is not None else None,
            "indice_pico": round(valores[pico] / promedio, 2) if promedio else None,
        })
    filas.sort(key=lambda f: -f["total"])
    return {"meses": meses, "productos": filas}


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
