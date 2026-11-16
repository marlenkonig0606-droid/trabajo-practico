"""Genera la base de DEMOSTRACIÓN que se comparte con el equipo
(database/demo/datos_demo.db). Simula la operación real día por día desde el
06/01/2025 hasta la fecha indicada, usando los servicios del sistema:

- Los CD compran a los proveedores (INGRESO_PROVEEDOR, con número de factura).
- Los locales venden (comprobante, pago, costo histórico) y a veces devuelven.
  Los importes de la mayoría de los tickets siguen una normal (≈ $7.500 ± $1.800)
  para que la campana de Gauss del reporte se lea bien; hay compras grandes
  ocasionales (tickets atípicos).
- Los lunes cada local pide reposición a un CD: el CD arma, precinta y despacha
  bultos; el local los recibe días después y los verifica (o rechaza algunos).
  Algunas órdenes las rechaza el CD o las cancela el local.

Cada fila queda con la fecha del día simulado. Es determinístico (misma semilla):
todos los integrantes obtienen exactamente la misma base.

Uso:  python generar_datos_demo.py [ruta de salida] [AAAA-MM-DD fecha final]
"""
import os
import random
import sys
from datetime import date, datetime, timedelta

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from database.conexion import BaseDeDatos  # noqa: E402
from database.datos_iniciales import cargar  # noqa: E402
from services.logistica_service import LogisticaService  # noqa: E402
from services.observadores import (  # noqa: E402
    AlertaStockMinimoObserver, AuditoriaObserver, StockObserver)
from services.stock_service import StockService  # noqa: E402
from services.ventas_service import VentasService  # noqa: E402

SALIDA = sys.argv[1] if len(sys.argv) > 1 else os.path.join(RAIZ, "database", "demo", "datos_demo.db")
HOY = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date.today()
INICIO = date(2025, 1, 6)

if os.path.exists(SALIDA):
    os.remove(SALIDA)
os.makedirs(os.path.dirname(SALIDA), exist_ok=True)
random.seed(2026)
db = BaseDeDatos(SALIDA)
cargar(incluir_demo=True)
with db.transaccion():
    # Las aperturas quedan al 01/01/2025: el historial arranca en orden.
    db.ejecutar("UPDATE movimiento_stock SET fecha='2025-01-01 08:00:00' WHERE motivo LIKE 'APERTURA%'")

stock = StockService()
stock.suscribir(AlertaStockMinimoObserver())
logistica = LogisticaService(stock)
logistica.suscribir(StockObserver(stock))
logistica.suscribir(AuditoriaObserver())
ventas = VentasService(stock)

LOCALES = [s["id"] for s in db.consultar(
    "SELECT id FROM sucursal WHERE tipo='LOCAL' AND activo=1 AND nombre IN "
    "('Local Centro', 'Local Nueva Córdoba') ORDER BY id")]
CDS = [s["id"] for s in db.consultar("SELECT id FROM sucursal WHERE tipo='CD' AND activo=1 ORDER BY id")]
PRODUCTOS = {local: db.consultar("""
    SELECT p.id, p.precio_venta FROM producto_sucursal ps JOIN producto p ON p.id = ps.producto_id
    WHERE ps.sucursal_id=? AND ps.habilitado=1 AND p.activo=1 ORDER BY p.id""", (local,))
    for local in LOCALES}
CATALOGO = db.consultar("""
    SELECT p.id, p.precio_costo, COALESCE(pr.nombre, 'Proveedor') AS proveedor
    FROM producto p LEFT JOIN proveedor pr ON pr.id = p.proveedor_id WHERE p.activo=1 ORDER BY p.id""")

TABLAS = ["movimiento_stock", "venta", "comprobante", "devolucion", "movimiento_caja",
          "orden_reposicion", "alerta_stock", "evento_log", "notificacion"]
ultimo = {t: db.consultar_uno(f"SELECT COALESCE(MAX(id),0) AS m FROM {t}")["m"] for t in TABLAS}


def fechar(dia, hora=12):
    """Pone la fecha 'dia' a todo lo creado desde la última llamada."""
    marca = f"{dia.isoformat()} {hora:02d}:{random.randint(0, 59):02d}:00"
    with db.transaccion():
        for tabla in TABLAS:
            db.ejecutar(f"UPDATE {tabla} SET fecha=? WHERE id>?", (marca, ultimo[tabla]))
            ultimo[tabla] = db.consultar_uno(f"SELECT COALESCE(MAX(id),0) AS m FROM {tabla}")["m"]
    return marca


def canasta(local):
    """Productos de un ticket. El 85 % apunta a un importe con distribución normal."""
    productos = PRODUCTOS[local]
    if random.random() < 0.02:                         # compra grande ocasional (atípica)
        return [{"producto_id": p["id"], "cantidad": 12} for p in random.sample(productos, 2)]
    if random.random() < 0.15:                         # compra chica al azar
        return [{"producto_id": p["id"], "cantidad": random.choice([1, 1, 2])}
                for p in random.sample(productos, random.randint(1, 2))]
    objetivo = min(max(random.gauss(7500, 1800), 2000), 14000)
    elegidos = random.sample(productos, random.choice([1, 2, 2, 3, 3]))
    partes = [random.random() + 0.3 for _ in elegidos]
    return [{"producto_id": p["id"],
             "cantidad": max(1, round(objetivo * parte / sum(partes) / p["precio_venta"]))}
            for p, parte in zip(elegidos, partes)]


MEDIOS = ["EFECTIVO"] * 4 + ["TARJETA_DEBITO"] * 3 + ["TARJETA_CREDITO"] * 2 + ["TRANSFERENCIA"]
MOTIVOS_DEV = ["Producto fallado", "Vencido", "Envase dañado", "Cambio de opinión"]
MOTIVOS_RECHAZO = ["Precinto dañado", "Faltan unidades", "Mercadería golpeada"]
actividad = {LOCALES[0]: 1.0, LOCALES[-1]: 0.8}       # un local vende algo más que el otro
pendientes = []                                         # (bulto, día de llegada, rechazar)
factura = 1000
resumen = {"ventas": 0, "devoluciones": 0, "ordenes": 0, "bultos": 0, "rechazos": 0, "compras": 0}

dia = INICIO
while dia <= HOY:
    estacional = 1.35 if dia.month in (12, 1) else 0.8 if dia.month in (6, 7) else 1.0
    finde = 1.3 if dia.weekday() >= 4 else 1.0
    # 0) los lunes, cada CD compra a los proveedores lo que le está faltando
    if dia.weekday() == 0:
        for cd in CDS:
            por_proveedor = {}
            for p in CATALOGO:
                if stock.libre(cd, p["id"]) < 700:
                    por_proveedor.setdefault(p["proveedor"], []).append(p)
            for proveedor, productos in por_proveedor.items():
                factura += 1
                referencia = f"Factura A-0001-{factura:08d} · {proveedor}"
                for p in productos:
                    stock.sumar(cd, p["id"], random.choice([600, 800, 1000]), "INGRESO_PROVEEDOR",
                                referencia, costo_unitario=p["precio_costo"])
                resumen["compras"] += 1
            fechar(dia, 7)
    # 1) llegan los bultos despachados
    for b in [x for x in pendientes if x[1] <= dia]:
        pendientes.remove(b)
        logistica.recibir(b[0])
        logistica.verificar_recepcion(b[0], not b[2], random.choice(MOTIVOS_RECHAZO) if b[2] else None)
        resumen["rechazos"] += b[2]
        marca = fechar(dia, 10)
        with db.transaccion():
            db.ejecutar("UPDATE bulto SET fecha_recepcion=? WHERE id=?", (marca, b[0]))
    # 2) ventas y devoluciones de cada local
    for local in LOCALES:
        for _ in range(random.randint(1, round(5 * estacional * finde * actividad[local]))):
            hora = random.randint(9, 20)
            if dia == HOY and hora >= datetime.now().hour:
                continue                                 # nada en el futuro
            items = canasta(local)
            medio = random.choice(MEDIOS)
            extra = {"cuotas": random.choice([1, 3, 6])} if medio == "TARJETA_CREDITO" else {}
            try:
                v = ventas.registrar_venta(local, items, medio, **extra)
                resumen["ventas"] += 1
                if random.random() < 0.04:
                    ventas.registrar_devolucion(
                        v["id"], [{"producto_id": items[0]["producto_id"], "cantidad": 1}],
                        random.choice(MOTIVOS_DEV))
                    resumen["devoluciones"] += 1
            except Exception:
                pass                                     # sin stock suficiente: no se vende
            fechar(dia, hora)
    # 3) los lunes cada local pide reposición a un CD
    if dia.weekday() == 0:
        for local in LOCALES:
            faltan = [p["id"] for p in PRODUCTOS[local] if stock.libre(local, p["id"]) < 45]
            if not faltan:
                continue
            items = [{"producto_id": p, "cantidad": random.choice([60, 70, 80])} for p in faltan]
            orden = logistica.crear_orden(local, items, random.choice(CDS))
            resumen["ordenes"] += 1
            fechar(dia, 8)
            azar = random.random()
            if azar < 0.04:                              # el CD no puede atenderla
                logistica.resolver_orden(orden["id"], "RECHAZAR", "Sin capacidad de despacho")
                fechar(dia, 9)
                continue
            if azar < 0.07:                              # el local se arrepiente
                logistica.resolver_orden(orden["id"], "CANCELAR", "Se compró a otro proveedor")
                fechar(dia, 9)
                continue
            if dia + timedelta(days=1) > HOY:
                continue                                 # queda pendiente: se pidió hoy
            mitad = (len(items) + 1) // 2
            creados = [logistica.crear_bulto(orden["id"], g)      # primero se arman todos
                       for g in (items[:mitad], items[mitad:]) if g]
            for bulto in creados:
                logistica.precintar(bulto["id"])
                logistica.despachar(bulto["id"])
                resumen["bultos"] += 1
                marca = fechar(dia + timedelta(days=1), random.randint(7, 15))
                with db.transaccion():
                    db.ejecutar("UPDATE bulto SET fecha_despacho=? WHERE id=?", (marca, bulto["id"]))
                pendientes.append((bulto["id"], dia + timedelta(days=random.choice([2, 2, 3, 4])),
                                   random.random() < 0.06))
    dia += timedelta(days=1)

# 4) Una orden pendiente por local, para que "Estado de mis órdenes" muestre de todo.
for local in LOCALES:
    logistica.crear_orden(local, [{"producto_id": PRODUCTOS[local][0]["id"], "cantidad": 30}],
                          random.choice(CDS))
    fechar(HOY, 8)
stock.revisar_alertas()

distintos = db.consultar_uno("""
    SELECT COUNT(*) AS n FROM stock st
    WHERE st.disponible <> COALESCE((SELECT SUM(m.cantidad) FROM movimiento_stock m
          WHERE m.sucursal_id = st.sucursal_id AND m.producto_id = st.producto_id), 0)""")["n"]
from database.base_demo import VERSION_DATOS  # noqa: E402
db.ejecutar(f"PRAGMA user_version = {VERSION_DATOS}")   # versión de los datos del equipo
db.ejecutar("VACUUM")
print("RESUMEN", resumen, "| en tránsito:", len(pendientes))
print("stock distinto de movimientos:", distintos,
      "| integridad:", db.consultar_uno("PRAGMA integrity_check")["integrity_check"])
print("base generada en", SALIDA)
