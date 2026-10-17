# TP Integrador DAO 2026 — Tema 3: CD a Locales

Backend en **Python (Flask + SQLAlchemy + SQLite)**, frontend en **React + Vite**. Misma idea que el repo de
referencia (`alquilerDeAutos`), pero con las capas separadas en carpetas.

## Cómo correrlo

```bash
# Terminal 1 — backend
cd trabajo-practico/backend
python -m venv . # crea el entorno virtual
.\.venv\Scripts\Activate.ps1 # activa el entorno virtual
pip install -r requirements.txt
python app.py                # http://localhost:5000 (crea la base y carga datos de prueba)
python -m pytest -v          # 10 tests de logística

# Terminal 2 — frontend
cd trabajo-practico/frontend
npm install
npm run dev                  # http://localhost:5173
```

## Arquitectura

```
backend/
  app.py                    rutas de la API (HTTP -> service -> JSON)
  database/
    conexion.py             ★ SINGLETON: engine y sesiones SQLAlchemy compartidos
    schema.sql              definición SQL de referencia de las tablas
    datos_iniciales.py      1 CD, 2 locales, 4 productos, stock solo en el CD
  models/
    orm.py                  modelos ORM y esquema relacional
                            clases del dominio (Bulto, EstadoBulto, Sucursal, Producto)
  patrones/
    observer.py             ★ OBSERVER: Sujeto / Observador / Eventos
    factory_medio_pago.py   ★ FACTORY: esqueleto para que completes
  services/                 reglas de negocio (acá viven las validaciones)
    logistica_service.py    ✅ procesos 3-6 completos (modelo a imitar)
    stock_service.py        ✅ stock + StockObserver
    reportes_service.py     ✅ 2 reportes · ⬜ faltan 2+
    ventas_service.py       ⬜ proceso 7
  tests/test_logistica.py   ✅
frontend/src/pages/
  Logistica.jsx ✅  Stock.jsx ✅  Reportes.jsx ✅ (parcial)  Pendiente.jsx ⬜
```

## Qué ya está resuelto (y cómo defenderlo)

**Ciclo de vida del bulto** (`models/bulto.py`): `PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO →
VERIFICADO | RECHAZADO`. Las transiciones válidas están en una tabla (`TRANSICIONES`) y el propio
objeto rechaza saltos (`cambiar_estado`). No se puede despachar sin precintar, ni recibir dos veces.

**Trazabilidad inmutable**: cada cambio inserta una fila en `historial_bulto`. Dos triggers SQL
abortan cualquier `UPDATE` o `DELETE` sobre esa tabla → la inmutabilidad la garantiza la base,
no solo el código.

**Stock no disponible hasta verificar**: al despachar sale del CD; al local **no** entra nada hasta que
*todos* los bultos del remito están en estado final. Entonces el remito pasa a `VERIFICADO` y solo
se suma lo de los bultos verificados. Un bulto con precinto roto o con número distinto queda
`RECHAZADO` y su mercadería nunca se vuelve vendible (aparece en el reporte de mermas).

**Transacciones**: si el CD no tiene stock al despachar, el error hace rollback y el bulto queda
`PRECINTADO` (hay un test que lo prueba).

**Patrones**
| Patrón | Dónde | Qué problema resuelve |
|---|---|---|
| Singleton | `BaseDeDatos` | Todos los services comparten la misma conexión/transacción |
| Observer | `LogisticaService` (sujeto) → `StockObserver` | Logística no conoce al stock; solo avisa "remito verificado" |
| Factory | `MedioPagoFactory` (lo terminás vos) | Ventas no hace if/elif por medio de pago |

---

## 👉 Lo que te queda, en este orden

Para cada paso: **primero pensá entrada → proceso → salida y las validaciones**, después escribí.
Cuando tengas algo, mandámelo y lo corregimos.

### Paso 1 — Leer y entender lo hecho (antes de escribir nada)
Abrí `logistica_service.py` y respondete:
- ¿Por qué `crear_bulto` valida *todo* antes del `with self.db.transaccion()`?
- ¿Qué pasaría si `StockObserver` sumara stock en `BULTO_DESPACHADO` en lugar de en `REMITO_VERIFICADO`?
- ¿Quién llama a `StockObserver.actualizar`? (no es `app.py` directamente)

### Paso 2 — ABM de catálogo (procesos 1 y 2)
Clases `Categoria` y `Proveedor`; endpoints POST/PUT/DELETE. Validar duplicados por `codigo`
(producto) y `cuit` (proveedor) **en el service** con `ReglaNegocioError`, no solo confiando en
el `UNIQUE` de la base. ¿Por qué conviene hacer las dos cosas?

### Paso 3 — Consolidar necesidades (proceso 3, segunda mitad)
Hoy la orden se crea a mano. Agregá `LogisticaService.sugerir_orden(local_id)` que arme los ítems
con los productos por debajo de `stock_minimo` en ese local. Pista: `StockService.listar()`.

### Paso 4 — Terminar la Factory (`patrones/factory_medio_pago.py`)
`TarjetaCredito` (recargo según cuotas), `TarjetaDebito`, `Transferencia`. Escribí un test que
pruebe que un tipo inexistente lanza error.

### Paso 5 — Ventas y devoluciones (proceso 7)
1. Tablas en `schema.sql`: `venta`, `detalle_venta` (guardá el precio del momento), `pago`,
   `comprobante`, `devolucion`, `detalle_devolucion`.
2. `VentasService.registrar_venta` siguiendo los comentarios. `StockService.restar` ya valida
   que no se venda más de lo disponible.
3. `registrar_devolucion`: la venta debe existir y no se puede devolver más de lo vendido
   (¿qué pasa con una segunda devolución parcial de la misma venta?). Devuelve stock
   (`sumar(..., "DEVOLUCION")`) y registra el egreso de caja.
4. Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva.

### Paso 6 — Reportes (mínimo 4 no triviales: ya hay 2)
- Ventas e ingresos por período, local y medio de pago (`GROUP BY`).
- Productos más vendidos con margen estimado.
- Existencias y productos en stock mínimo.

### Paso 7 — Segundo Observer (opcional, suma)
`AlertaStockMinimoObserver`: avisa cuando una venta o despacho deja un producto bajo el mínimo.

### Paso 8 — Pantallas
Reemplazar `Pendiente.jsx` por Ventas y Catálogo, copiando la forma de `Logistica.jsx`.
