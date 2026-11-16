"""
PATRÓN SINGLETON
----------------
Problema: toda la aplicación necesita hablar con la MISMA base de datos.
Si cada servicio creara su propia conexión, habría conexiones duplicadas y
transacciones que no se ven entre sí.

Solución: la clase controla su propia instanciación en __new__.
La primera vez crea el objeto; las siguientes devuelve siempre el mismo.

    a = BaseDeDatos()
    b = BaseDeDatos()
    a is b   # True
"""
import os
import re
import sqlite3
import threading
from contextlib import contextmanager

RUTA_SCHEMA = os.path.join(os.path.dirname(__file__), "schema.sql")
RUTA_DB_DEFAULT = os.path.join(os.path.dirname(__file__), "..", "tp_cd_locales.db")


class BaseDeDatos:
    _instancia = None

    def __new__(cls, ruta=None):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._inicializar(ruta or RUTA_DB_DEFAULT)
        return cls._instancia

    def _inicializar(self, ruta):
        self._ruta = ruta
        # check_same_thread=False porque Flask atiende requests en distintos hilos
        self._conexion = sqlite3.connect(ruta, check_same_thread=False)
        self._conexion.row_factory = sqlite3.Row      # filas accesibles por nombre
        self._conexion.execute("PRAGMA foreign_keys = ON")
        # normalizar(texto) en SQL: minúsculas y sin acentos, para búsquedas parciales
        # que no distinguen mayúsculas (LIKE de SQLite solo lo hace con letras sin tilde).
        from services.paginacion import normalizar
        self._conexion.create_function("normalizar", 1, normalizar, deterministic=True)
        # Flask atiende cada request en un hilo distinto, pero la conexión es UNA sola.
        # Este candado evita que dos hilos mezclen sus consultas en la misma conexión.
        # Es RLock (reentrante) porque un mismo hilo puede volver a pedirlo
        # (por ejemplo: transaccion() -> ejecutar()).
        self._candado = threading.RLock()
        self._nivel_transaccion = 0      # cuántas transacciones anidadas hay abiertas
        with open(RUTA_SCHEMA, encoding="utf-8") as f:
            self._conexion.executescript(f.read())
        self._migrar()

    def _migrar(self):
        """Agrega columnas nuevas a bases creadas con una versión anterior del esquema."""
        columnas = [c["name"] for c in self.consultar("PRAGMA table_info(stock)")]
        if "reservado" not in columnas:
            self._conexion.execute(
                "ALTER TABLE stock ADD COLUMN reservado INTEGER NOT NULL DEFAULT 0")
            self._conexion.commit()
        columnas_orden = [
            c["name"] for c in self.consultar("PRAGMA table_info(orden_reposicion)")
        ]
        if "solicitado_por_usuario_id" not in columnas_orden:
            self._conexion.execute(
                """ALTER TABLE orden_reposicion
                   ADD COLUMN solicitado_por_usuario_id INTEGER REFERENCES usuario(id)""")
            self._conexion.commit()
        columnas_proveedor = [
            c["name"] for c in self.consultar("PRAGMA table_info(proveedor)")
        ]
        if "nombre" not in columnas_proveedor:
            self._conexion.execute(
                "ALTER TABLE proveedor ADD COLUMN nombre TEXT NOT NULL DEFAULT ''")
            self._conexion.execute(
                """UPDATE proveedor SET nombre=razon_social
                   WHERE trim(nombre)=''""")
            self._conexion.commit()
        columnas_proveedor = [
            c["name"] for c in self.consultar("PRAGMA table_info(proveedor)")
        ]
        if "activo" not in columnas_proveedor:
            self._conexion.execute(
                "ALTER TABLE proveedor ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
            self._conexion.commit()
        proveedores = self.consultar(
            "SELECT id, cuit, razon_social, activo FROM proveedor ORDER BY id")
        proveedores_por_cuit = {}
        for proveedor in proveedores:
            cuit_normalizado = re.sub(r"[^0-9]", "", proveedor["cuit"])
            if cuit_normalizado:
                proveedores_por_cuit.setdefault(cuit_normalizado, []).append(proveedor)

        with self.transaccion() as cx:
            for cuit_normalizado, grupo in proveedores_por_cuit.items():
                if len(grupo) > 1:
                    razones_sociales = {
                        re.sub(r"\s+", " ", proveedor["razon_social"]).strip().casefold()
                        for proveedor in grupo
                    }
                    if len(razones_sociales) > 1:
                        ids = ", ".join(str(proveedor["id"]) for proveedor in grupo)
                        raise sqlite3.IntegrityError(
                            f"Hay proveedores con CUIT duplicado y razones sociales "
                            f"distintas (IDs: {ids}); revisalos antes de iniciar la "
                            "aplicación")

                    referencias = {
                        proveedor["id"]: cx.execute(
                            "SELECT COUNT(*) FROM producto WHERE proveedor_id=?",
                            (proveedor["id"],),
                        ).fetchone()[0]
                        for proveedor in grupo
                    }
                    principal = min(
                        grupo,
                        key=lambda proveedor: (
                            proveedor["cuit"] != cuit_normalizado,
                            -referencias[proveedor["id"]],
                            proveedor["id"],
                        ),
                    )
                    activo = max(proveedor["activo"] for proveedor in grupo)
                    for proveedor in grupo:
                        if proveedor["id"] == principal["id"]:
                            continue
                        cx.execute(
                            "UPDATE producto SET proveedor_id=? WHERE proveedor_id=?",
                            (principal["id"], proveedor["id"]),
                        )
                        cx.execute(
                            "UPDATE proveedor SET activo=0 WHERE id=?",
                            (proveedor["id"],),
                        )
                    cx.execute(
                        "UPDATE proveedor SET cuit=?, activo=? WHERE id=?",
                        (cuit_normalizado, activo, principal["id"]),
                    )
                else:
                    proveedor = grupo[0]
                    if proveedor["cuit"] != cuit_normalizado:
                        cx.execute(
                            "UPDATE proveedor SET cuit=? WHERE id=?",
                            (cuit_normalizado, proveedor["id"]),
                        )
        columnas_sucursal = [
            c["name"] for c in self.consultar("PRAGMA table_info(sucursal)")
        ]
        if "activo" not in columnas_sucursal:
            self._conexion.execute(
                "ALTER TABLE sucursal ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")
            self._conexion.commit()
        columnas_sucursal = [
            c["name"] for c in self.consultar("PRAGMA table_info(sucursal)")
        ]
        if "codigo" not in columnas_sucursal:
            self._conexion.execute("ALTER TABLE sucursal ADD COLUMN codigo TEXT")
            self._conexion.commit()
        self._conexion.execute(
            """UPDATE sucursal SET codigo='SUC-' || printf('%06d', id)
               WHERE codigo IS NULL OR trim(codigo)=''""")
        self._conexion.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_sucursal_codigo ON sucursal(codigo)")

        columnas_categoria = [
            c["name"] for c in self.consultar("PRAGMA table_info(categoria)")
        ]
        if "activo" not in columnas_categoria:
            self._conexion.execute(
                "ALTER TABLE categoria ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")

        columnas_producto = [
            c["name"] for c in self.consultar("PRAGMA table_info(producto)")
        ]
        if "activo" not in columnas_producto:
            self._conexion.execute(
                "ALTER TABLE producto ADD COLUMN activo INTEGER NOT NULL DEFAULT 1")

        columnas_movimiento = [
            c["name"] for c in self.consultar("PRAGMA table_info(movimiento_stock)")
        ]
        if "costo_unitario" not in columnas_movimiento:
            self._conexion.execute(
                "ALTER TABLE movimiento_stock ADD COLUMN costo_unitario REAL")

        columnas_detalle_bulto = [
            c["name"] for c in self.consultar("PRAGMA table_info(detalle_bulto)")
        ]
        if "costo_unitario" not in columnas_detalle_bulto:
            self._conexion.execute(
                "ALTER TABLE detalle_bulto ADD COLUMN costo_unitario REAL")

        columnas_orden = [
            c["name"] for c in self.consultar("PRAGMA table_info(orden_reposicion)")
        ]
        if "fecha_vencimiento" not in columnas_orden:
            self._conexion.execute(
                "ALTER TABLE orden_reposicion ADD COLUMN fecha_vencimiento TEXT")
            self._conexion.execute(
                """UPDATE orden_reposicion
                   SET fecha_vencimiento=datetime(fecha, '+30 days')
                   WHERE fecha_vencimiento IS NULL OR trim(fecha_vencimiento)=''""")
        if "resolucion" not in columnas_orden:
            self._conexion.execute(
                "ALTER TABLE orden_reposicion ADD COLUMN resolucion TEXT")
        if "motivo_resolucion" not in columnas_orden:
            self._conexion.execute(
                "ALTER TABLE orden_reposicion ADD COLUMN motivo_resolucion TEXT")
        if "aviso_vencimiento_enviado" not in columnas_orden:
            self._conexion.execute(
                """ALTER TABLE orden_reposicion
                   ADD COLUMN aviso_vencimiento_enviado INTEGER NOT NULL DEFAULT 0""")

        columnas_bulto = [
            c["name"] for c in self.consultar("PRAGMA table_info(bulto)")
        ]
        if "intento" not in columnas_bulto:
            self._conexion.execute(
                "ALTER TABLE bulto ADD COLUMN intento INTEGER NOT NULL DEFAULT 1")
        if "usuario_despacho_id" not in columnas_bulto:
            self._conexion.execute(
                "ALTER TABLE bulto ADD COLUMN usuario_despacho_id INTEGER REFERENCES usuario(id)")
        if "observacion_rechazo" not in columnas_bulto:
            self._conexion.execute(
                "ALTER TABLE bulto ADD COLUMN observacion_rechazo TEXT")

        columnas_historial = [
            c["name"] for c in self.consultar("PRAGMA table_info(historial_bulto)")
        ]
        if "desde_estado" not in columnas_historial:
            self._conexion.execute(
                "ALTER TABLE historial_bulto ADD COLUMN desde_estado TEXT")
        if "usuario_id" not in columnas_historial:
            self._conexion.execute(
                "ALTER TABLE historial_bulto ADD COLUMN usuario_id INTEGER REFERENCES usuario(id)")
        if "intento" not in columnas_historial:
            self._conexion.execute(
                "ALTER TABLE historial_bulto ADD COLUMN intento INTEGER NOT NULL DEFAULT 1")

        for tabla in ("detalle_venta", "detalle_devolucion"):
            columnas = [
                c["name"] for c in self.consultar(f"PRAGMA table_info({tabla})")
            ]
            if "costo_unitario" not in columnas:
                self._conexion.execute(
                    f"ALTER TABLE {tabla} ADD COLUMN costo_unitario REAL")

        self._migrar_roles_de_usuario()
        self._migrar_minimo_por_sucursal()

        self._conexion.execute(
            """INSERT OR IGNORE INTO producto_sucursal (sucursal_id, producto_id, habilitado)
               SELECT s.id, p.id, 1 FROM sucursal s CROSS JOIN producto p
               WHERE s.tipo='LOCAL' AND s.activo=1 AND p.activo=1""")
        self._conexion.executescript("""
            CREATE TRIGGER IF NOT EXISTS sucursal_codigo_automatico
            AFTER INSERT ON sucursal
            WHEN NEW.codigo IS NULL OR trim(NEW.codigo) = ''
            BEGIN
                UPDATE sucursal SET codigo = 'SUC-' || printf('%06d', NEW.id)
                WHERE id = NEW.id;
            END;

            CREATE TRIGGER IF NOT EXISTS producto_habilitado_en_locales
            AFTER INSERT ON producto
            BEGIN
                INSERT OR IGNORE INTO producto_sucursal (sucursal_id, producto_id, habilitado)
                SELECT id, NEW.id, 1 FROM sucursal WHERE tipo = 'LOCAL' AND activo = 1;
            END;

            CREATE TRIGGER IF NOT EXISTS local_habilita_productos_activos
            AFTER INSERT ON sucursal
            WHEN NEW.tipo = 'LOCAL' AND NEW.activo = 1
            BEGIN
                INSERT OR IGNORE INTO producto_sucursal (sucursal_id, producto_id, habilitado)
                SELECT NEW.id, id, 1 FROM producto WHERE activo = 1;
            END;
        """)
        self._conexion.commit()

    def _migrar_minimo_por_sucursal(self):
        """Stock mínimo independiente por sucursal: cada una controla SOLO el suyo.
        - producto_sucursal.stock_minimo: mínimo propio de cada local (lo cambia
          únicamente el administrador del local). En bases anteriores se
          inicializa con el mínimo que tenía el producto.
        - minimo_cd: mínimo propio de cada CD (lo cambia únicamente ese CD). Si el
          CD todavía no lo configuró, vale el mínimo por defecto del producto.
          En bases anteriores (cuando el mínimo del CD era la suma de los locales)
          se inicializa con esa suma, así ninguna alerta cambia de golpe.
        - Vista minimo_vigente: el mínimo con el que se compara el stock de cada
          sucursal (local: el suyo, 0 si no vende el producto; CD: el suyo)."""
        columnas = [c["name"] for c in self.consultar("PRAGMA table_info(producto_sucursal)")]
        if "stock_minimo" not in columnas:
            self._conexion.executescript("""
                ALTER TABLE producto_sucursal ADD COLUMN stock_minimo INTEGER
                    CHECK (stock_minimo IS NULL OR stock_minimo >= 0);
                UPDATE producto_sucursal SET stock_minimo = (
                    SELECT p.stock_minimo FROM producto p WHERE p.id = producto_id);
            """)
        # ¿La base viene de la versión en que el mínimo del CD era la suma de los locales?
        vista = self.consultar_uno(
            "SELECT sql FROM sqlite_master WHERE type='view' AND name='minimo_vigente'")
        venia_de_la_suma = bool(vista and "SUM(" in vista["sql"])
        self._conexion.executescript("""
            CREATE TABLE IF NOT EXISTS minimo_cd (
                sucursal_id  INTEGER NOT NULL REFERENCES sucursal(id),
                producto_id  INTEGER NOT NULL REFERENCES producto(id),
                stock_minimo INTEGER NOT NULL CHECK (stock_minimo >= 0),
                PRIMARY KEY (sucursal_id, producto_id)
            );
        """)
        if venia_de_la_suma:
            self._conexion.execute("""
                INSERT OR IGNORE INTO minimo_cd (sucursal_id, producto_id, stock_minimo)
                SELECT cd.id, p.id,
                       COALESCE((SELECT SUM(COALESCE(ps.stock_minimo, 0))
                                 FROM producto_sucursal ps
                                 JOIN sucursal l ON l.id = ps.sucursal_id
                                 WHERE l.tipo = 'LOCAL' AND l.activo = 1
                                   AND ps.habilitado = 1 AND ps.producto_id = p.id), 0)
                FROM sucursal cd CROSS JOIN producto p
                WHERE cd.tipo = 'CD'""")
        self._conexion.executescript("""
            CREATE TRIGGER IF NOT EXISTS producto_sucursal_minimo_inicial
            AFTER INSERT ON producto_sucursal
            WHEN NEW.stock_minimo IS NULL
            BEGIN
                UPDATE producto_sucursal
                SET stock_minimo = (SELECT stock_minimo FROM producto WHERE id = NEW.producto_id)
                WHERE sucursal_id = NEW.sucursal_id AND producto_id = NEW.producto_id;
            END;

            DROP VIEW IF EXISTS minimo_vigente;
            CREATE VIEW minimo_vigente AS
                SELECT ps.sucursal_id, ps.producto_id,
                       CASE WHEN ps.habilitado = 1 THEN COALESCE(ps.stock_minimo, 0)
                            ELSE 0 END AS stock_minimo
                FROM producto_sucursal ps
                JOIN sucursal s ON s.id = ps.sucursal_id
                WHERE s.tipo = 'LOCAL'
                UNION ALL
                SELECT cd.id, p.id, COALESCE(mc.stock_minimo, p.stock_minimo)
                FROM sucursal cd CROSS JOIN producto p
                LEFT JOIN minimo_cd mc ON mc.sucursal_id = cd.id AND mc.producto_id = p.id
                WHERE cd.tipo = 'CD';
        """)
        self._conexion.commit()

    def _migrar_roles_de_usuario(self):
        """Agrega rol, estado y cambio obligatorio de contraseña a bases anteriores.
        Las cuentas que ya existían quedan APROBADAS (ya venían operando):
          - los usuarios del CD pasan a ADMINISTRADOR,
          - en cada local, la cuenta más antigua pasa a ADMINISTRADOR y el resto a EMPLEADO."""
        columnas = [c["name"] for c in self.consultar("PRAGMA table_info(usuario)")]
        if "rol" in columnas:
            return
        self._conexion.executescript("""
            ALTER TABLE usuario ADD COLUMN rol TEXT NOT NULL DEFAULT 'EMPLEADO'
                CHECK (rol IN ('ADMINISTRADOR', 'EMPLEADO'));
            ALTER TABLE usuario ADD COLUMN estado TEXT NOT NULL DEFAULT 'PENDIENTE'
                CHECK (estado IN ('PENDIENTE', 'APROBADO', 'RECHAZADO'));
            ALTER TABLE usuario ADD COLUMN debe_cambiar_password INTEGER NOT NULL DEFAULT 0
                CHECK (debe_cambiar_password IN (0, 1));
            ALTER TABLE usuario ADD COLUMN aprobado_por_usuario_id INTEGER REFERENCES usuario(id);
            ALTER TABLE usuario ADD COLUMN fecha_resolucion TEXT;
            ALTER TABLE usuario ADD COLUMN motivo_rechazo TEXT;

            UPDATE usuario SET estado = 'APROBADO';
            UPDATE usuario SET rol = 'ADMINISTRADOR'
            WHERE sucursal_id IN (SELECT id FROM sucursal WHERE tipo = 'CD')
               OR id IN (SELECT MIN(id) FROM usuario GROUP BY sucursal_id);
        """)
        self._conexion.commit()

    # ---------- helpers de consulta ----------
    
    def consultar(self, sql, params=()):
        """Devuelve una lista de dicts."""
        with self._candado:
            cursor = self._conexion.execute(sql, params)
            return [dict(fila) for fila in cursor.fetchall()]

    def consultar_uno(self, sql, params=()):
        with self._candado:
            fila = self._conexion.execute(sql, params).fetchone()
            return dict(fila) if fila else None

    def ejecutar(self, sql, params=()):
        """INSERT/UPDATE/DELETE. Devuelve el id insertado (si corresponde)."""
        with self._candado:
            return self._conexion.execute(sql, params).lastrowid

    def ejecutar_contando(self, sql, params=()):
        """UPDATE/DELETE. Devuelve cuántas filas modificó (0 = la condición no se cumplió)."""
        with self._candado:
            return self._conexion.execute(sql, params).rowcount

    @contextmanager
    def transaccion(self):
        """Uso:  with db.transaccion():  ...
        - Mientras dura, ningún otro hilo puede usar la base (candado tomado).
        - Si algo falla adentro, se hace rollback de todo; si no, commit.
        - Se puede anidar (ej. registrar_venta -> stock.restar): las transacciones
          internas se suman a la externa y SOLO la más externa hace commit o
          rollback. Antes, cada 'with' interno hacía commit al terminar, y si un
          paso posterior fallaba quedaban datos a medio guardar."""
        with self._candado:
            if self._nivel_transaccion:
                self._nivel_transaccion += 1
                try:
                    yield self._conexion
                finally:
                    self._nivel_transaccion -= 1
                return
            self._nivel_transaccion = 1
            try:
                with self._conexion:
                    yield self._conexion
            finally:
                self._nivel_transaccion = 0

    @classmethod
    def reiniciar(cls):
        """Solo para tests: descarta la instancia única."""
        if cls._instancia is not None:
            cls._instancia._conexion.close()
        cls._instancia = None
