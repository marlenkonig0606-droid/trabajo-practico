import sqlite3

from database.conexion import BaseDeDatos
from database.datos_iniciales import cargar
from dao.proveedor_dao import ProveedorDAO


def test_migra_nombre_de_proveedor_en_base_existente(tmp_path):
    ruta = str(tmp_path / "proveedor_legacy.db")
    conexion_legacy = sqlite3.connect(ruta)
    conexion_legacy.execute("""
        CREATE TABLE proveedor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuit TEXT NOT NULL UNIQUE,
            razon_social TEXT NOT NULL
        )
    """)
    conexion_legacy.execute("""
        CREATE TABLE sucursal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE,
            direccion TEXT,
            tipo TEXT NOT NULL CHECK (tipo IN ('CD', 'LOCAL'))
        )
    """)
    conexion_legacy.execute(
        "INSERT INTO proveedor (cuit, razon_social) VALUES (?, ?)",
        ("30-12345678-9", "Distribuidora Norte SA"))
    conexion_legacy.execute(
        "INSERT INTO sucursal (nombre, direccion, tipo) VALUES (?, ?, ?)",
        ("CD Central", "Dirección", "CD"))
    conexion_legacy.commit()
    conexion_legacy.close()

    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        cargar(incluir_demo=False)

        proveedor = ProveedorDAO(db).obtener_por_cuit("30-12345678-9")
        assert proveedor["nombre"] == "Distribuidora Norte SA"
        assert proveedor["razon_social"] == "Distribuidora Norte SA"
        assert proveedor["activo"] == 1
        assert db.consultar_uno(
            "SELECT activo FROM sucursal WHERE nombre='CD Central'")["activo"] == 1
    finally:
        BaseDeDatos.reiniciar()


def test_migra_cuits_duplicados_del_mismo_proveedor_sin_borrar_registros(tmp_path):
    ruta = str(tmp_path / "proveedores_duplicados.db")
    conexion_legacy = sqlite3.connect(ruta)
    conexion_legacy.executescript("""
        CREATE TABLE proveedor (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cuit TEXT NOT NULL UNIQUE,
            razon_social TEXT NOT NULL
        );
        INSERT INTO proveedor (id, cuit, razon_social)
            VALUES (1, '30123456789', 'Distribuidora Norte SA');
        INSERT INTO proveedor (id, cuit, razon_social)
            VALUES (2, '30-12345678-9', 'Distribuidora Norte SA');
        CREATE TABLE producto (
            id INTEGER PRIMARY KEY,
            proveedor_id INTEGER REFERENCES proveedor(id)
        );
        INSERT INTO producto (id, proveedor_id) VALUES (1, 2);
    """)
    conexion_legacy.commit()
    conexion_legacy.close()

    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        proveedores = db.consultar(
            "SELECT id, cuit, activo FROM proveedor ORDER BY id")
        producto = db.consultar_uno(
            "SELECT proveedor_id FROM producto WHERE id=1")

        assert proveedores == [
            {"id": 1, "cuit": "30123456789", "activo": 1},
            {"id": 2, "cuit": "30-12345678-9", "activo": 0},
        ]
        assert producto["proveedor_id"] == 1
        assert ProveedorDAO(db).obtener_por_cuit("30-12345678-9")["id"] == 1
    finally:
        BaseDeDatos.reiniciar()


def test_carga_demo_no_duplica_proveedores_por_formato_de_cuit(tmp_path):
    ruta = str(tmp_path / "demo_proveedores.db")
    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        cargar()
        cargar()

        assert db.consultar_uno(
            "SELECT COUNT(*) AS cantidad FROM proveedor")["cantidad"] == 3
        assert db.consultar_uno(
            "SELECT COUNT(*) AS cantidad FROM proveedor WHERE cuit='30123456789'"
        )["cantidad"] == 1
    finally:
        BaseDeDatos.reiniciar()


def test_migra_vencimientos_y_toma_de_rastros_en_esquema_logistico_anterior(tmp_path):
    ruta = str(tmp_path / "logistica_legacy.db")
    conexion_legacy = sqlite3.connect(ruta)
    conexion_legacy.executescript("""
        CREATE TABLE sucursal (
            id INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL UNIQUE,
            direccion TEXT,
            tipo TEXT NOT NULL
        );
        INSERT INTO sucursal (id, nombre, tipo) VALUES (1, 'CD', 'CD');
        INSERT INTO sucursal (id, nombre, tipo) VALUES (2, 'Local', 'LOCAL');
        CREATE TABLE orden_reposicion (
            id INTEGER PRIMARY KEY,
            origen_id INTEGER NOT NULL REFERENCES sucursal(id),
            destino_id INTEGER NOT NULL REFERENCES sucursal(id),
            fecha TEXT NOT NULL,
            estado TEXT NOT NULL
        );
        INSERT INTO orden_reposicion
            (id, origen_id, destino_id, fecha, estado)
            VALUES (1, 1, 2, '2025-01-01 10:00:00', 'PENDIENTE');
        CREATE TABLE remito (
            id INTEGER PRIMARY KEY,
            numero TEXT NOT NULL UNIQUE,
            orden_id INTEGER NOT NULL UNIQUE REFERENCES orden_reposicion(id),
            estado TEXT NOT NULL
        );
        CREATE TABLE bulto (
            id INTEGER PRIMARY KEY,
            remito_id INTEGER NOT NULL REFERENCES remito(id),
            precinto TEXT,
            estado TEXT NOT NULL,
            fecha_despacho TEXT,
            fecha_recepcion TEXT
        );
        CREATE TABLE historial_bulto (
            id INTEGER PRIMARY KEY,
            bulto_id INTEGER NOT NULL REFERENCES bulto(id),
            estado TEXT NOT NULL,
            fecha TEXT NOT NULL,
            observacion TEXT
        );
    """)
    conexion_legacy.commit()
    conexion_legacy.close()

    BaseDeDatos.reiniciar()
    try:
        db = BaseDeDatos(ruta)
        orden = db.consultar_uno(
            "SELECT fecha_vencimiento FROM orden_reposicion WHERE id=1")
        assert orden["fecha_vencimiento"] == "2025-01-31 10:00:00"
        assert {"resolucion", "motivo_resolucion", "aviso_vencimiento_enviado"} <= {
            columna["name"]
            for columna in db.consultar("PRAGMA table_info(orden_reposicion)")
        }
        assert {"intento", "usuario_despacho_id", "observacion_rechazo"} <= {
            columna["name"] for columna in db.consultar("PRAGMA table_info(bulto)")
        }
        assert {"desde_estado", "usuario_id", "intento"} <= {
            columna["name"]
            for columna in db.consultar("PRAGMA table_info(historial_bulto)")
        }
    finally:
        BaseDeDatos.reiniciar()
