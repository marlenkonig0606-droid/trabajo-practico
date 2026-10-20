# TP Integrador DAO 2026 — Tema 3: CD a Locales

Backend en **Python (Flask + SQLite)**, frontend en **React + Vite**. Misma idea que el repo de
referencia (`alquilerDeAutos`), pero con las capas separadas en carpetas.

## Cómo correrlo

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
python app.py                # http://localhost:5000 (crea la base y carga datos de prueba)
python -m pytest -v          # suite completa del backend

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

## Arquitectura

```
backend/
  app.py                    rutas de la API (HTTP -> service -> JSON)
  database/
    conexion.py             ★ SINGLETON: una sola conexión para toda la app
    schema.sql              tablas + triggers que hacen inmutable el historial
    datos_iniciales.py      1 CD, 2 locales, 4 productos, stock solo en el CD
  models/                   clases del dominio (incluye medios de pago)
  patrones/
    observer.py             ★ OBSERVER: Sujeto / Observador / Eventos
  services/                 reglas de negocio (acá viven las validaciones)
    creadores_medio_pago.py creadores concretos de los medios de pago
    logistica_service.py    ✅ procesos 3-6 completos (modelo a imitar)
    stock_service.py        ✅ stock + StockObserver
    reportes_service.py     ✅ 2 reportes · ⬜ faltan 2+
    ventas_service.py       ✅ proceso 7 · ventas, cobros y devoluciones
  tests/test_logistica.py   ✅
frontend/src/pages/
  Logistica.jsx ✅  Stock.jsx ✅  Reportes.jsx ✅ (parcial)  Ventas.jsx ✅
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
| Creación de medios de pago | `CreadorMedioDePago` y creadores concretos | Cada creador decide qué medio de pago construir; VentasService usa el producto común |

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

### Paso 4 — Creación de medios de pago
Los productos de pago están en `models/medio_pago.py`. En `services/creadores_medio_pago.py`,
`CreadorMedioDePago` declara el método de creación y cada creador
concreto (`CreadorEfectivo`, `CreadorTarjetaCredito`, etc.) lo redefine para construir su medio.
`VentasService` selecciona el creador según el tipo solicitado y trabaja con `IMedioDePago`.
El crédito aplica un recargo del 5% por cuota. Un tipo desconocido produce un error de negocio.

### Paso 5 — Ventas y devoluciones (proceso 7)
1. ✅ Tablas en `schema.sql` y modelos para `venta`, `detalle_venta` (precio del momento),
   `pago`, `comprobante`, `devolucion` y `detalle_devolucion`.
2. `VentasService.registrar_venta` siguiendo los comentarios. `StockService.restar` ya valida
   que no se venda más de lo disponible.
3. `registrar_devolucion`: la venta debe existir y no se puede devolver más de lo vendido
   (también sumando devoluciones parciales anteriores). Repone stock (`sumar(..., "DEVOLUCION")`)
   y registra el egreso en `movimiento_caja`. El reintegro es proporcional al total efectivamente
   pagado para distribuir descuentos y recargos de la venta.
4. Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva.

### Paso 6 — Reportes (mínimo 4 no triviales: ya hay 2)
- Ventas e ingresos por período, local y medio de pago (`GROUP BY`).
- Productos más vendidos con margen estimado.
- Existencias y productos en stock mínimo.

### Paso 7 — Segundo Observer (opcional, suma)
`AlertaStockMinimoObserver`: avisa cuando una venta o despacho deja un producto bajo el mínimo.

### Paso 8 — Pantallas
Reemplazar `Pendiente.jsx` por Ventas y Catálogo, copiando la forma de `Logistica.jsx`.
