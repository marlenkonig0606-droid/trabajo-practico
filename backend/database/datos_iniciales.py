"""Carga el catálogo base y, en la aplicación, datos de demostración idempotentes."""
from datetime import datetime, timedelta

from database.conexion import BaseDeDatos


def _insertar_o_buscar(db, tabla, columna_unica, valores):
    columnas = ", ".join(valores)
    signos = ", ".join("?" for _ in valores)
    db.ejecutar(
        f"INSERT OR IGNORE INTO {tabla} ({columnas}) VALUES ({signos})",
        tuple(valores.values()))
    return db.consultar_uno(
        f"SELECT id FROM {tabla} WHERE {columna_unica}=?",
        (valores[columna_unica],))["id"]


def _fecha_hace(dias):
    return (datetime.now().astimezone() - timedelta(days=dias)).strftime(
        "%Y-%m-%d %H:%M:%S")


def _crear_venta_demo(db, sucursal_id, items, medio_pago, total, dias):
    subtotal = sum(item["cantidad"] * item["precio"] for item in items)
    fecha = _fecha_hace(dias)
    venta_id = db.ejecutar(
        """INSERT INTO venta (sucursal_id, fecha, subtotal, total)
           VALUES (?, ?, ?, ?)""",
        (sucursal_id, fecha, subtotal, total))
    for item in items:
        costo_unitario = db.consultar_uno(
            "SELECT precio_costo FROM producto WHERE id=?",
            (item["producto_id"],))["precio_costo"]
        db.ejecutar(
            """INSERT INTO detalle_venta
               (venta_id, producto_id, cantidad, precio_unitario, costo_unitario)
               VALUES (?, ?, ?, ?, ?)""",
            (venta_id, item["producto_id"], item["cantidad"], item["precio"],
             costo_unitario))
        db.ejecutar(
            """UPDATE stock SET disponible=disponible-?
               WHERE sucursal_id=? AND producto_id=?""",
            (item["cantidad"], sucursal_id, item["producto_id"]))
        db.ejecutar(
            """INSERT INTO movimiento_stock
               (sucursal_id, producto_id, cantidad, motivo, referencia, fecha,
                costo_unitario)
               VALUES (?, ?, ?, 'VENTA', ?, ?, ?)""",
            (sucursal_id, item["producto_id"], -item["cantidad"],
             f"venta {venta_id}", fecha, costo_unitario))

    db.ejecutar(
        """INSERT INTO pago (venta_id, medio_pago, importe, cuotas, referencia)
           VALUES (?, ?, ?, 1, ?)""",
        (venta_id, medio_pago, total, "Venta de demostración"))
    numero = db.consultar_uno(
        "SELECT COALESCE(MAX(numero), 0) + 1 AS numero FROM comprobante")["numero"]
    db.ejecutar(
        """INSERT INTO comprobante (venta_id, numero, fecha)
           VALUES (?, ?, ?)""", (venta_id, numero, fecha))
    return venta_id, fecha, subtotal


def _registrar_aperturas_stock(db):
    if db.consultar_uno(
            "SELECT nombre FROM datos_iniciales WHERE nombre='stock-ledger-v1'"):
        return
    saldos = db.consultar("""
        SELECT s.sucursal_id, s.producto_id, s.disponible,
               COALESCE(SUM(m.cantidad), 0) AS movimientos
        FROM stock s
        LEFT JOIN movimiento_stock m
          ON m.sucursal_id=s.sucursal_id AND m.producto_id=s.producto_id
        GROUP BY s.sucursal_id, s.producto_id, s.disponible
    """)
    for saldo in saldos:
        diferencia = saldo["disponible"] - saldo["movimientos"]
        if diferencia:
            db.ejecutar(
                """INSERT INTO movimiento_stock
                   (sucursal_id, producto_id, cantidad, motivo, referencia)
                   VALUES (?, ?, ?, 'APERTURA_MIGRACION', ?)""",
                (saldo["sucursal_id"], saldo["producto_id"], diferencia,
                 "Apertura auditada del libro de movimientos"))
    db.ejecutar(
        "INSERT INTO datos_iniciales (nombre) VALUES ('stock-ledger-v1')")


def _cargar_demo(db, sucursales, categorias, productos):
    cd_norte = _insertar_o_buscar(db, "sucursal", "nombre", {
        "nombre": "CD Norte", "direccion": "Av. Circunvalación 1800", "tipo": "CD"})
    proveedor_lacteos = _insertar_o_buscar(db, "proveedor", "cuit", {
        "cuit": "30-98765432-1", "razon_social": "Lácteos del Centro SA",
        "nombre": "Lácteos del Centro"})
    proveedor_limpieza = _insertar_o_buscar(db, "proveedor", "cuit", {
        "cuit": "30-24681357-9", "razon_social": "Hogar y Limpieza SRL",
        "nombre": "Hogar y Limpieza"})

    leche = _insertar_o_buscar(db, "producto", "codigo", {
        "codigo": "LAC-001", "nombre": "Leche entera 1L",
        "categoria_id": categorias["Bebidas"], "proveedor_id": proveedor_lacteos,
        "precio_costo": 950, "precio_venta": 1550, "stock_minimo": 20})
    detergente = _insertar_o_buscar(db, "producto", "codigo", {
        "codigo": "LIM-001", "nombre": "Detergente 750ml",
        "categoria_id": categorias["Almacén"], "proveedor_id": proveedor_limpieza,
        "precio_costo": 1300, "precio_venta": 2200, "stock_minimo": 12})

    todos_productos = {**productos, "LAC-001": leche, "LIM-001": detergente}
    if db.consultar_uno(
            "SELECT nombre FROM datos_iniciales WHERE nombre='demo-v1'"):
        return

    for producto_id in todos_productos.values():
        db.ejecutar(
            """INSERT OR IGNORE INTO stock (sucursal_id, producto_id, disponible)
               VALUES (?, ?, 500)""", (sucursales["CD Central"], producto_id))
        db.ejecutar(
            """INSERT OR IGNORE INTO stock (sucursal_id, producto_id, disponible)
               VALUES (?, ?, 300)""", (cd_norte, producto_id))
        for nombre in ("Local Centro", "Local Nueva Córdoba"):
            db.ejecutar(
                """INSERT INTO stock (sucursal_id, producto_id, disponible)
                   VALUES (?, ?, 80)
                   ON CONFLICT(sucursal_id, producto_id)
                   DO UPDATE SET disponible=MAX(stock.disponible, excluded.disponible)""",
                (sucursales[nombre], producto_id))

    agua = todos_productos["BEB-001"]
    gaseosa = todos_productos["BEB-002"]
    yerba = todos_productos["ALM-001"]
    fideos = todos_productos["ALM-002"]
    leche = todos_productos["LAC-001"]
    detergente = todos_productos["LIM-001"]
    local_centro = sucursales["Local Centro"]
    local_nueva_cordoba = sucursales["Local Nueva Córdoba"]

    venta_devolucion, _, subtotal_devolucion = _crear_venta_demo(
        db, local_centro,
        [{"producto_id": agua, "cantidad": 2, "precio": 700},
         {"producto_id": yerba, "cantidad": 1, "precio": 3800}],
        "EFECTIVO", 4680, 8)
    _crear_venta_demo(
        db, local_centro,
        [{"producto_id": gaseosa, "cantidad": 3, "precio": 1900},
         {"producto_id": fideos, "cantidad": 2, "precio": 1050}],
        "TARJETA_DEBITO", 7800, 4)
    _crear_venta_demo(
        db, local_nueva_cordoba,
        [{"producto_id": agua, "cantidad": 1, "precio": 700},
         {"producto_id": leche, "cantidad": 3, "precio": 1550}],
        "TRANSFERENCIA", 5350, 2)
    _crear_venta_demo(
        db, local_nueva_cordoba,
        [{"producto_id": yerba, "cantidad": 2, "precio": 3800},
         {"producto_id": detergente, "cantidad": 1, "precio": 2200}],
        "TARJETA_CREDITO", 10290, 1)

    precio_agua = 700
    importe_devuelto = round(4680 * precio_agua / subtotal_devolucion, 2)
    devolucion_id = db.ejecutar(
        """INSERT INTO devolucion (venta_id, fecha, motivo, total)
           VALUES (?, ?, ?, ?)""",
        (venta_devolucion, _fecha_hace(3), "Producto de demostración devuelto",
         importe_devuelto))
    costo_agua = db.consultar_uno(
        "SELECT precio_costo FROM producto WHERE id=?", (agua,))["precio_costo"]
    db.ejecutar(
        """INSERT INTO detalle_devolucion
           (devolucion_id, producto_id, cantidad, precio_unitario, costo_unitario)
           VALUES (?, ?, 1, ?, ?)""", (devolucion_id, agua, precio_agua, costo_agua))
    db.ejecutar(
        """UPDATE stock SET disponible=disponible+1
           WHERE sucursal_id=? AND producto_id=?""", (local_centro, agua))
    db.ejecutar(
        """INSERT INTO movimiento_stock
           (sucursal_id, producto_id, cantidad, motivo, referencia, fecha, costo_unitario)
           VALUES (?, ?, 1, 'DEVOLUCION', ?, ?, ?)""",
        (local_centro, agua, f"devolucion {devolucion_id}", _fecha_hace(3), costo_agua))
    db.ejecutar(
        """INSERT INTO movimiento_caja
           (sucursal_id, devolucion_id, tipo, importe, fecha)
           VALUES (?, ?, 'EGRESO', ?, ?)""",
        (local_centro, devolucion_id, importe_devuelto, _fecha_hace(3)))
    db.ejecutar("INSERT INTO datos_iniciales (nombre) VALUES ('demo-v1')")


def cargar(incluir_demo=True):
    db = BaseDeDatos()
    with db.transaccion():
        sucursales = {
            "CD Central": _insertar_o_buscar(db, "sucursal", "nombre", {
                "nombre": "CD Central", "direccion": "Ruta 9 km 695", "tipo": "CD"}),
            "Local Centro": _insertar_o_buscar(db, "sucursal", "nombre", {
                "nombre": "Local Centro", "direccion": "27 de Abril 300", "tipo": "LOCAL"}),
            "Local Nueva Córdoba": _insertar_o_buscar(db, "sucursal", "nombre", {
                "nombre": "Local Nueva Córdoba", "direccion": "Bv. Illia 500", "tipo": "LOCAL"}),
        }
        categorias = {
            "Bebidas": _insertar_o_buscar(db, "categoria", "nombre", {"nombre": "Bebidas"}),
            "Almacén": _insertar_o_buscar(db, "categoria", "nombre", {"nombre": "Almacén"}),
        }
        proveedor_base = _insertar_o_buscar(db, "proveedor", "cuit", {
            "cuit": "30-12345678-9", "razon_social": "Distribuidora Norte SA",
            "nombre": "Distribuidora Norte"})
        productos = {}
        productos_base = [
            ("BEB-001", "Agua 1.5L", "Bebidas", 400, 700, 20),
            ("BEB-002", "Gaseosa cola 2L", "Bebidas", 1100, 1900, 15),
            ("ALM-001", "Yerba 1kg", "Almacén", 2500, 3800, 10),
            ("ALM-002", "Fideos 500g", "Almacén", 600, 1050, 25),
        ]
        for codigo, nombre, categoria, costo, venta, minimo in productos_base:
            producto_id = _insertar_o_buscar(db, "producto", "codigo", {
                "codigo": codigo, "nombre": nombre,
                "categoria_id": categorias[categoria], "proveedor_id": proveedor_base,
                "precio_costo": costo, "precio_venta": venta,
                "stock_minimo": minimo})
            productos[codigo] = producto_id
            db.ejecutar(
                """INSERT OR IGNORE INTO stock (sucursal_id, producto_id, disponible)
                   VALUES (?, ?, 500)""", (sucursales["CD Central"], producto_id))

        if incluir_demo:
            _cargar_demo(db, sucursales, categorias, productos)
        _registrar_aperturas_stock(db)


if __name__ == "__main__":
    cargar()
    print("Datos iniciales cargados.")
