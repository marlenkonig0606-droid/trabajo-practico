# Checklist TP Integrador — Tema 3: CD a Locales
_Versión con sqlite3 + DAOs, sin ORM. Actualizado 19/10 sobre `main` = `b03cfd0` (ya incluye lo de Marlén y lo de Lucía)._
_Hoy: Proceso 3, bloqueo de stock y Observer completo en `main`; merge con ventas y medios de pago de Lucía. Tests: **28/29** (falla 1 de Lucía por redondeo)._

> 🔄 **Todos: hacer `git pull origin main` en su rama antes de seguir.**
> - `observer.py` ahora está en **`models/observer.py`** (lo movió Lucía) y tiene la única clase `Eventos`.
> - Los imports van **sin** `backend.` (`from models.x import ...`), si no `python app.py` no arranca.

> ⚠ La versión con ORM (SQLAlchemy), ABM y PRs #1–#3 **no está en `main`**, pero no se perdió:
> está en la compu de Marlén (rama `main` local y rama `mar`). Si el grupo decide volver a ella, se restaura.

## 👥 Reparto de tareas
> Cada uno trabaja en **su rama** (`lucia`, `facu`, `mar`) y sube con Pull Request a `main`.
> Antes de empezar: `git checkout <su-rama>` y `git pull origin main`.
> Archivos compartidos (`app.py`, `api.js`, `App.jsx`, `schema.sql`, `reportes_service.py`): avisar en el grupo antes de tocarlos.

---

### ✅ PRIMERO (bloquea a todos) — resuelto por Marlén en la rama `mar`
**`main` no arrancaba: el backend y los tests fallaban al iniciar.**
- [x] `services/logistica_service.py` importaba `models.bulto`, pero el archivo se llamaba `models/contenedor.py`
      → se renombró el model a `models/bulto.py` (`Bulto` / `EstadoBulto`) y el service quedó igual
- [x] `tests/test_logistica.py` → no hacía falta tocarlo: no importa el model, solo el service
- [x] `models/categoria.py` tenía `from contenedor import Contenedor`: sobraba y además rompía → borrada
- [x] Nombre unificado: todo se llama **`bulto`** (model, service, tablas `bulto`/`detalle_bulto`/`historial_bulto`, rutas `/api/bultos/...`, frontend)
- [x] Verificar: la app levanta (endpoints GET responden 200) y `python -m pytest` pasa (10/10)
- [x] **Subido a `main`** (19/10) → avisar al grupo para que hagan `git pull origin main`

---

### 🔵 Facundo — rama `facu` · ABM de catálogo y sucursales (procesos 1 y 2)
_Ya armó los DAOs y models de categoría, producto y proveedor: falta conectarlos._
- [ ] **Unificar los DAOs con la base del proyecto**: hoy usan `inventario.db`; tienen que usar `tp_cd_locales.db` (la conexión Singleton `BaseDeDatos`)
- [ ] **Alinear DAOs con `schema.sql`**: `CategoriaDAO` usa `descripcion` y `ProveedorDAO` usa `nombre`, `telefono`, `mail`, `direccion`, que no existen en las tablas → agregar columnas o sacarlas
- [ ] `services/catalogo_service.py`: alta / modificación / baja de **productos, categorías y proveedores**
- [ ] Validar duplicados: producto por `codigo`, proveedor por `cuit` (consigna) → `ReglaNegocioError`
- [ ] No permitir borrar algo ya usado (con stock, órdenes o bultos)
- [ ] **Proceso 1**: alta / modificación / baja de **sucursales** (no duplicar nombre, siempre al menos un CD)
- [ ] Endpoints `POST` / `PUT` / `DELETE` de todo lo anterior en `app.py`
- [ ] Pantalla **Catálogo** (reemplazar `Pendiente.jsx`) con productos, categorías, proveedores y sucursales
- [ ] Tests del ABM (duplicados, borrar algo usado, datos inválidos)

### 🟣 Lucía — rama `lucia` · Ventas, devoluciones y medios de pago (proceso 7)
- [x] Tablas en `schema.sql`: `venta`, `detalle_venta` (precio del momento), `pago`, `comprobante`, `devolucion`, `detalle_devolucion` + sus clases en `models/`
- [x] Creación delegada de medios de pago con `CreadorMedioDePago`, creadores concretos e `IMedioDePago`; integrado en `VentasService` y probado
- [ ] **Arreglar test que falla por redondeo**: `test_venta_usa_el_creador...` da `1540.0000000000002` en vez de `1540` → `round(total, 2)` o `pytest.approx`
- [x] `VentasService.registrar_venta`: uno o más productos, solo en LOCAL, no más del stock disponible y verificado (`StockService.restar`)
- [x] Cobro con medio de pago (usando creadores concretos) y comprobante con número correlativo
- [ ] `registrar_devolucion`: la venta tiene que existir, no más de lo vendido (sumando devoluciones anteriores), repone stock y registra egreso de caja
- [ ] `VentasService` recibe el **mismo** `StockService` que `app.py` (para el Observer)
- [ ] Endpoints `/api/ventas`, `/api/ventas/<id>`, `/api/devoluciones`
- [ ] Pantalla **Ventas y devoluciones**
- [ ] Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva

### 🟠 Marlén — rama `mar` · Logística, patrones, reportes y documentación
- [x] **Proceso 3**: `sugerir_orden(local_id)` con los productos bajo `stock_minimo` + botón "Sugerir orden" en Logística
      (`LogisticaService.sugerir_orden` + `GET /api/sucursales/<id>/sugerencia` + botón en `Logistica.jsx`)
- [x] **Bloqueo de stock** (2 usuarios a la vez): reservar stock del CD al empaquetar + `GestorBloqueos` + tests de concurrencia
      (`services/bloqueos.py` + columna `reservado` en `stock` + `StockService.reservar/consumir_reserva` + 4 tests nuevos → 13/13)
- [x] **Observer completo**: `AlertaStockMinimoObserver` + `AuditoriaObserver` + `/api/alertas` y `/api/eventos` + avisos en Stock y Reportes
      (2 sujetos, 3 observadores, tablas `alerta_stock` y `evento_log`, 8 tests en `test_observer.py`)
- [~] **Anular bulto** antes de despachar (libera la reserva)
  - [x] Estado `ANULADO` en `EstadoBulto` (desde PREPARADO o PRECINTADO; es estado final)
  - [x] `StockService.liberar_reserva`
  - [ ] `LogisticaService.anular_bulto(bulto_id, motivo)`
  - [ ] Que lo empaquetado de la orden no cuente los bultos anulados (para poder re-empaquetar)
  - [ ] Endpoint `POST /api/bultos/<id>/anular` + botón "Anular" en Logística + test
- [ ] **Reporte**: existencias actuales y productos en stock mínimo
- [ ] **Reporte**: movimientos y valorización del inventario
- [ ] **Reporte** (cuando Lucía termine): ventas e ingresos por período, local y medio de pago
- [ ] **Reporte** (cuando Lucía termine): productos más vendidos y margen de ganancia/pérdida
- [ ] Filtro de fechas en la pantalla de Reportes
- [ ] **Diagrama de clases** y **diagrama de estados del bulto** en `documentacion/`
- [ ] Documentar las reglas que definió el grupo + actualizar `documentacion/README.md`

### 🤝 Entre los tres (al final)
- [ ] Validar el JSON de entrada en `app.py` (campo faltante → 400, no 500)
- [ ] Probar el circuito completo: catálogo → orden → bulto → despacho → recepción → venta → devolución → reportes
- [ ] Que no se suban `__pycache__`, `.pytest_cache` ni `*.db`
- [ ] Preparar la defensa: cada uno explica su parte y los patrones (Singleton, Observer y creación delegada)

---

# 📋 Estado según la consigna (versión actual de `main`)

| # | Proceso | Estado | Responsable |
|---|---|---|---|
| 1 | Sucursales y CD | 🟡 solo listar | Facundo |
| 2 | Productos, categorías, precios, mínimos, proveedores | 🟡 models y DAOs, sin conectar | Facundo |
| 3 | Consolidar necesidades en orden de reposición | ✅ orden manual + sugerencia por stock mínimo | Marlén |
| 4 | Empaquetar en bultos con remito y precinto | ✅ con reserva de stock y bloqueo entre usuarios | Marlén |
| 5 | Despacho | ✅ funciona | Facundo |
| 6 | Recepción con verificación de precinto | ✅ funciona | Facundo |
| 7 | Ventas, cobros, comprobante, devoluciones | 🟡 venta + cobro + comprobante; faltan devoluciones, endpoints y pantalla | Lucía |

**Validaciones de negocio**
- [x] Stock disponible en destino solo con remito + bulto Verificado; precinto roto → Rechazado
- [x] Trazabilidad inmutable (triggers en `schema.sql`)
- [x] No vender más que el stock disponible y verificado (`StockService.restar` atómico + test) → Lucía
- [ ] Sin productos ni proveedores duplicados (los DAOs lo intentan, falta conectarlos) → Facundo
- [ ] No aceptar devoluciones inválidas → Lucía

**Patrones (mínimo 2)**
- [x] Singleton: `BaseDeDatos` en `database/conexion.py`
- [x] Observer: 2 sujetos (`LogisticaService`, `StockService`) y 3 observadores (`StockObserver`, `AlertaStockMinimoObserver`, `AuditoriaObserver`)
- [x] Creación delegada de medios de pago (`CreadorMedioDePago` + `IMedioDePago`) → Lucía

**Reportes (mínimo 4 no triviales — hay 2)**
- [x] Bultos rechazados y merma
- [x] Tiempo promedio de tránsito CD → local
- [ ] Existencias y stock mínimo → Marlén
- [ ] Movimientos y valorización → Marlén
- [ ] Ventas por período, local y medio de pago → Marlén (después de Lucía)
- [ ] Más vendidos y margen → Marlén (después de Lucía)

**Opcionales (suman):** órdenes de compra sugeridas · promociones y listas de precios · lotes/vencimientos · clientes frecuentes · inventario físico
