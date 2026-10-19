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
    -- reservado = unidades ya comprometidas en bultos armados y todavía no despachados
    -- libre     = disponible - reservado  -> lo único que se puede tomar
    reservado    INTEGER NOT NULL DEFAULT 0 CHECK (reservado >= 0),
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

-- ---------- 4. Remito y bultos ----------
CREATE TABLE IF NOT EXISTS remito (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    numero    TEXT NOT NULL UNIQUE,
    orden_id  INTEGER NOT NULL UNIQUE REFERENCES orden_reposicion(id),
    estado    TEXT NOT NULL DEFAULT 'ABIERTO'
              CHECK (estado IN ('ABIERTO', 'DESPACHADO', 'VERIFICADO', 'RECHAZADO'))
);

CREATE TABLE IF NOT EXISTS bulto (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    remito_id       INTEGER NOT NULL REFERENCES remito(id),
    precinto        TEXT UNIQUE,            -- se asigna al precintar
    estado          TEXT NOT NULL DEFAULT 'PREPARADO',
    fecha_despacho  TEXT,
    fecha_recepcion TEXT
);

CREATE TABLE IF NOT EXISTS detalle_bulto (
    bulto_id     INTEGER NOT NULL REFERENCES bulto(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    cantidad     INTEGER NOT NULL CHECK (cantidad > 0),
    PRIMARY KEY (bulto_id, producto_id)
);

-- Trazabilidad INMUTABLE: solo se puede insertar.
CREATE TABLE IF NOT EXISTS historial_bulto (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bulto_id     INTEGER NOT NULL REFERENCES bulto(id),
    estado       TEXT NOT NULL,
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    observacion  TEXT
);

CREATE TRIGGER IF NOT EXISTS historial_sin_update
BEFORE UPDATE ON historial_bulto
BEGIN
    SELECT RAISE(ABORT, 'El historial de bultos es inmutable');
END;

CREATE TRIGGER IF NOT EXISTS historial_sin_delete
BEFORE DELETE ON historial_bulto
BEGIN
    SELECT RAISE(ABORT, 'El historial de bultos es inmutable');
END;

-- ---------- Observadores ----------
-- Alertas de stock mínimo (AlertaStockMinimoObserver).
-- Hay como máximo UNA alerta pendiente por sucursal+producto; se resuelve sola
-- cuando el stock libre vuelve a llegar al mínimo.
CREATE TABLE IF NOT EXISTS alerta_stock (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id       INTEGER NOT NULL REFERENCES sucursal(id),
    producto_id       INTEGER NOT NULL REFERENCES producto(id),
    libre             INTEGER NOT NULL,       -- stock libre al momento de la alerta
    minimo            INTEGER NOT NULL,
    fecha             TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    resuelta          INTEGER NOT NULL DEFAULT 0 CHECK (resuelta IN (0, 1)),
    fecha_resolucion  TEXT
);

-- Registro de eventos logísticos (AuditoriaObserver)
CREATE TABLE IF NOT EXISTS evento_log (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    evento   TEXT NOT NULL,
    detalle  TEXT NOT NULL,                   -- descripción legible
    fecha    TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- 7. Ventas (TODO: completar vos) ----------
-- Pensá: venta (cabecera), detalle_venta, pago (medio de pago), comprobante,
-- devolucion (+ detalle). Mirá la guía en README.md.
