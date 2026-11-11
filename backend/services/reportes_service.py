from dao.reportes_dao import ReportesDAO
from datetime import datetime, timedelta

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

    def tiempo_promedio_transito(self):
        return self.dao.tiempo_promedio_transito()

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