-- =========================================================
-- TP Integrador DAO 2026 - Tema 3: Ventas e Inventario CD-Locales
-- Esquema SQLite
-- =========================================================
PRAGMA foreign_keys = ON;

-- ---------- 1. Sucursales (locales + Centro de Distribución) ----------
CREATE TABLE IF NOT EXISTS sucursal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    direccion   TEXT,
    tipo        TEXT NOT NULL CHECK (tipo IN ('CD', 'LOCAL'))
);

-- ---------- 2. Catálogo ----------
CREATE TABLE IF NOT EXISTS categoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS proveedor (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cuit    TEXT NOT NULL UNIQUE,          -- identificador que evita duplicados
    razon_social TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS producto (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT NOT NULL UNIQUE,    -- identificador que evita duplicados
    nombre        TEXT NOT NULL,
    categoria_id  INTEGER NOT NULL REFERENCES categoria(id),
    proveedor_id  INTEGER REFERENCES proveedor(id),
    precio_costo  REAL NOT NULL CHECK (precio_costo >= 0),
    precio_venta  REAL NOT NULL CHECK (precio_venta >= 0),
    stock_minimo  INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0)
);

-- Stock DISPONIBLE (vendible) por sucursal y producto.
-- Solo se suma acá cuando el remito se verifica (ver StockObserver).
CREATE TABLE IF NOT EXISTS stock (
    sucursal_id  INTEGER NOT NULL REFERENCES sucursal(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    disponible   INTEGER NOT NULL DEFAULT 0 CHECK (disponible >= 0),
    PRIMARY KEY (sucursal_id, producto_id)
);

-- Movimientos de inventario (sirve para el reporte de valorización/movimientos)
CREATE TABLE IF NOT EXISTS movimiento_stock (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id  INTEGER NOT NULL REFERENCES sucursal(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    cantidad     INTEGER NOT NULL,          -- positivo = entra, negativo = sale
    motivo       TEXT NOT NULL,             -- DESPACHO, RECEPCION, VENTA, DEVOLUCION, AJUSTE
    referencia   TEXT,
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- 3. Orden de reposición ----------
CREATE TABLE IF NOT EXISTS orden_reposicion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    origen_id   INTEGER NOT NULL REFERENCES sucursal(id),   -- el CD
    destino_id  INTEGER NOT NULL REFERENCES sucursal(id),   -- un local
    fecha       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    estado      TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK (estado IN ('PENDIENTE', 'EN_PREPARACION', 'DESPACHADA', 'CERRADA'))
);

CREATE TABLE IF NOT EXISTS detalle_orden (
    orden_id     INTEGER NOT NULL REFERENCES orden_reposicion(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    cantidad     INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (orden_id, producto_id)
);

-- ---------- 4. Remito y contenedores ----------
CREATE TABLE IF NOT EXISTS remito (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    numero    TEXT NOT NULL UNIQUE,
    orden_id  INTEGER NOT NULL UNIQUE REFERENCES orden_reposicion(id),
    estado    TEXT NOT NULL DEFAULT 'ABIERTO'
              CHECK (estado IN ('ABIERTO', 'DESPACHADO', 'VERIFICADO', 'RECHAZADO'))
);

CREATE TABLE IF NOT EXISTS contenedor (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    remito_id       INTEGER NOT NULL REFERENCES remito(id),
    precinto        TEXT UNIQUE,            -- se asigna al precintar
    estado          TEXT NOT NULL DEFAULT 'PREPARADO',
    fecha_despacho  TEXT,
    fecha_recepcion TEXT
);

CREATE TABLE IF NOT EXISTS detalle_contenedor (
    contenedor_id     INTEGER NOT NULL REFERENCES contenedor(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    cantidad     INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (contenedor_id, producto_id)
);

-- Trazabilidad INMUTABLE: solo se puede insertar.
CREATE TABLE IF NOT EXISTS historial_contenedor (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    contenedor_id     INTEGER NOT NULL REFERENCES contenedor(id),
    estado       TEXT NOT NULL,
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    observacion  TEXT
);

CREATE TRIGGER IF NOT EXISTS historial_contenedor_sin_update
BEFORE UPDATE ON historial_contenedor
BEGIN
    SELECT RAISE(ABORT, 'El historial de contenedores es inmutable');
END;

CREATE TRIGGER IF NOT EXISTS historial_contenedor_sin_delete
BEFORE DELETE ON historial_contenedor
BEGIN
    SELECT RAISE(ABORT, 'El historial de contenedores es inmutable');
END;

-- ---------- 7. Ventas (TODO: completar vos) ----------
-- Pensá: venta (cabecera), detalle_venta, pago (medio de pago), comprobante,
-- devolucion (+ detalle). Mirá la guía en README.md.
