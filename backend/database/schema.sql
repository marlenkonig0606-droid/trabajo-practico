-- =========================================================
-- TP Integrador DAO 2026 - Tema 3: Ventas e Inventario CD-Locales
-- Esquema SQLite
-- =========================================================
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS datos_iniciales (
    nombre TEXT PRIMARY KEY,
    fecha  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- 1. Sucursales (locales + Centro de Distribución) ----------
CREATE TABLE IF NOT EXISTS sucursal (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT NOT NULL UNIQUE,
    codigo      TEXT UNIQUE,
    direccion   TEXT,
    tipo        TEXT NOT NULL CHECK (tipo IN ('CD', 'LOCAL')),
    activo      INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS usuario (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    email          TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash  TEXT NOT NULL,
    sucursal_id    INTEGER NOT NULL REFERENCES sucursal(id),
    fecha_alta     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- 2. Catálogo ----------
CREATE TABLE IF NOT EXISTS categoria (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT NOT NULL UNIQUE,
    descripcion TEXT,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS proveedor (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    cuit    TEXT NOT NULL UNIQUE,          -- identificador que evita duplicados
    razon_social TEXT NOT NULL,
    nombre TEXT NOT NULL,
    activo INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS producto (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo        TEXT NOT NULL UNIQUE,    -- identificador que evita duplicados
    nombre        TEXT NOT NULL,
    categoria_id  INTEGER NOT NULL REFERENCES categoria(id),
    proveedor_id  INTEGER REFERENCES proveedor(id),
    precio_costo  REAL NOT NULL CHECK (precio_costo >= 0),
    precio_venta  REAL NOT NULL CHECK (precio_venta >= 0),
    stock_minimo  INTEGER NOT NULL DEFAULT 0 CHECK (stock_minimo >= 0),
    activo        INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1))
);

CREATE TABLE IF NOT EXISTS producto_sucursal (
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    producto_id INTEGER NOT NULL REFERENCES producto(id),
    habilitado  INTEGER NOT NULL DEFAULT 1 CHECK (habilitado IN (0, 1)),
    PRIMARY KEY (sucursal_id, producto_id)
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
    costo_unitario REAL,
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ---------- 3. Orden de reposición ----------
CREATE TABLE IF NOT EXISTS orden_reposicion (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    origen_id                 INTEGER NOT NULL REFERENCES sucursal(id),   -- el CD
    destino_id                INTEGER NOT NULL REFERENCES sucursal(id),   -- un local
    solicitado_por_usuario_id INTEGER REFERENCES usuario(id),
    fecha                     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    fecha_vencimiento         TEXT NOT NULL DEFAULT (datetime('now', 'localtime', '+30 days')),
    resolucion                TEXT CHECK (resolucion IN ('RECHAZADA', 'CANCELADA', 'VENCIDA')),
    motivo_resolucion         TEXT,
    aviso_vencimiento_enviado INTEGER NOT NULL DEFAULT 0 CHECK (aviso_vencimiento_enviado IN (0, 1)),
    estado                    TEXT NOT NULL DEFAULT 'PENDIENTE'
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
    fecha_recepcion TEXT,
    intento         INTEGER NOT NULL DEFAULT 1 CHECK (intento > 0),
    usuario_despacho_id INTEGER REFERENCES usuario(id),
    observacion_rechazo TEXT
);

CREATE TABLE IF NOT EXISTS precinto_anulado (
    precinto TEXT PRIMARY KEY,
    bulto_id INTEGER NOT NULL REFERENCES bulto(id),
    motivo TEXT NOT NULL,
    fecha TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS detalle_bulto (
    bulto_id     INTEGER NOT NULL REFERENCES bulto(id),
    producto_id  INTEGER NOT NULL REFERENCES producto(id),
    cantidad     INTEGER NOT NULL CHECK (cantidad > 0),
    costo_unitario REAL,
    PRIMARY KEY (bulto_id, producto_id)
);

-- Trazabilidad INMUTABLE: solo se puede insertar.
CREATE TABLE IF NOT EXISTS historial_bulto (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    bulto_id     INTEGER NOT NULL REFERENCES bulto(id),
    estado       TEXT NOT NULL,
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    observacion  TEXT,
    desde_estado TEXT,
    usuario_id   INTEGER REFERENCES usuario(id),
    intento      INTEGER NOT NULL DEFAULT 1 CHECK (intento > 0)
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

CREATE TABLE IF NOT EXISTS notificacion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id INTEGER NOT NULL REFERENCES sucursal(id),
    evento      TEXT NOT NULL,
    referencia  TEXT,
    mensaje     TEXT NOT NULL,
    fecha       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    leida       INTEGER NOT NULL DEFAULT 0 CHECK (leida IN (0, 1))
);

-- ---------- Ventas, cobros y devoluciones ----------
CREATE TABLE IF NOT EXISTS venta (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id  INTEGER NOT NULL REFERENCES sucursal(id),
    fecha        TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    subtotal     REAL NOT NULL CHECK (subtotal >= 0),
    total        REAL NOT NULL CHECK (total >= 0)
);

CREATE TABLE IF NOT EXISTS detalle_venta (
    venta_id        INTEGER NOT NULL REFERENCES venta(id),
    producto_id     INTEGER NOT NULL REFERENCES producto(id),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    costo_unitario  REAL,
    PRIMARY KEY (venta_id, producto_id)
);

CREATE TABLE IF NOT EXISTS pago (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id     INTEGER NOT NULL UNIQUE REFERENCES venta(id),
    medio_pago   TEXT NOT NULL CHECK (
                     medio_pago IN ('EFECTIVO', 'TARJETA_CREDITO', 'TARJETA_DEBITO', 'TRANSFERENCIA')
                 ),
    importe      REAL NOT NULL CHECK (importe >= 0),
    cuotas       INTEGER NOT NULL DEFAULT 1 CHECK (cuotas > 0),
    referencia   TEXT
);

CREATE TABLE IF NOT EXISTS comprobante (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id  INTEGER NOT NULL UNIQUE REFERENCES venta(id),
    numero    INTEGER NOT NULL UNIQUE CHECK (numero > 0),
    fecha     TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS devolucion (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id    INTEGER NOT NULL REFERENCES venta(id),
    fecha       TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    motivo      TEXT NOT NULL,
    total       REAL NOT NULL CHECK (total >= 0)
);

CREATE TABLE IF NOT EXISTS detalle_devolucion (
    devolucion_id   INTEGER NOT NULL REFERENCES devolucion(id),
    producto_id     INTEGER NOT NULL REFERENCES producto(id),
    cantidad        INTEGER NOT NULL CHECK (cantidad > 0),
    precio_unitario REAL NOT NULL CHECK (precio_unitario >= 0),
    costo_unitario  REAL,
    PRIMARY KEY (devolucion_id, producto_id)
);

CREATE TABLE IF NOT EXISTS movimiento_caja (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    sucursal_id    INTEGER NOT NULL REFERENCES sucursal(id),
    devolucion_id  INTEGER NOT NULL UNIQUE REFERENCES devolucion(id),
    tipo           TEXT NOT NULL CHECK (tipo = 'EGRESO'),
    importe        REAL NOT NULL CHECK (importe >= 0),
    fecha          TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
