# TP Integrador DAO 2026 — Tema 3: CD a Locales

Backend en **Python (Flask + SQLAlchemy + SQLite)**, frontend en **React + Vite**.

## Cómo correrlo

```bash
# Terminal 1 — backend
cd trabajo-practico/backend
python -m venv . # crea el entorno virtual
.\.venv\Scripts\Activate.ps1 # activa el entorno virtual
pip install -r requirements.txt
python app.py                # http://localhost:5000 (crea la base y carga datos de prueba)
python -m pytest -v          # 11 tests de logística

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
    datos_iniciales.py      1 CD, 2 locales, 4 productos, stock solo en el CD
  models/
    base.py                 base declarativa compartida de SQLAlchemy
    categoria.py            Categoria: entidad y mapeo SQLAlchemy
    producto.py             Producto: entidad y mapeo SQLAlchemy
    proveedor.py            Proveedor: entidad y mapeo SQLAlchemy
    sucursal.py             Sucursal y subtipos: entidad y mapeo SQLAlchemy
    orden_reposicion.py     OrdenReposicion, DetalleOrden y Remito
    stock.py                Stock y MovimientoStock
    contenedor.py           Contenedor, DetalleContenedor y HistorialContenedor
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

**Ciclo de vida del contenedor** (`models/contenedor.py`): `PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO →
VERIFICADO | RECHAZADO`. Las transiciones válidas están en una tabla (`TRANSICIONES`) y el propio
objeto rechaza saltos (`cambiar_estado`). No se puede despachar sin precintar, ni recibir dos veces.

**Trazabilidad inmutable**: cada cambio inserta una fila en `historial_contenedor`. Dos triggers SQL
abortan cualquier `UPDATE` o `DELETE` sobre esa tabla → la inmutabilidad la garantiza la base,
no solo el código.

**Modelos**: cada entidad persistida es una única clase SQLAlchemy en `models/`.
La misma instancia aplica reglas del dominio y se guarda en SQLite.

**Stock no disponible hasta verificar**: al despachar sale del CD; al local **no** entra nada hasta que
*todos* los contenedores del remito están en estado final. Entonces el remito pasa a `VERIFICADO` y solo
se suma lo de los contenedores verificados. Un contenedor con precinto roto o con número distinto queda
`RECHAZADO` y su mercadería nunca se vuelve vendible (aparece en el reporte de mermas).

**Transacciones**: si el CD no tiene stock al despachar, el error hace rollback y el contenedor queda
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
- ¿Por qué `crear_contenedor` valida *todo* antes del `with self.db.transaccion()`?
- ¿Qué pasaría si `StockObserver` sumara stock en `CONTENEDOR_DESPACHADO` en lugar de en `REMITO_VERIFICADO`?
- ¿Quién llama a `StockObserver.actualizar`? (no es `app.py` directamente)

### Paso 2 — ABM de catálogo (procesos 1 y 2) ✅
Clases `Categoria` y `Proveedor`, endpoints GET/POST/PUT/PATCH/DELETE y validación de duplicados
en los services (`codigo` de producto, `cuit` de proveedor y nombre de categoría), además del
`UNIQUE` de la base.
-----------------------------HECHO-------------------------------------------------------

### Paso 3 — Consolidar necesidades (proceso 3, segunda mitad)
Hoy la orden se crea a mano. Agregá `LogisticaService.sugerir_orden(local_id)` que arme los ítems
con los productos por debajo de `stock_minimo` en ese local. Pista: `StockService.listar()`.

### Paso 4 — Terminar la Factory (`patrones/factory_medio_pago.py`)
`TarjetaCredito` (recargo según cuotas), `TarjetaDebito`, `Transferencia`. Escribí un test que
pruebe que un tipo inexistente lanza error.

### Paso 5 — Ventas y devoluciones (proceso 7)

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
