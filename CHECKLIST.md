# Checklist TP Integrador — Tema 3: CD a Locales
_Versión con sqlite3 + DAOs, sin ORM. Actualizado 19/10 sobre `main` (incluye lo de Marlén y lo de Lucía)._
_Hoy: Proceso 3, bloqueo de stock y Observer completo en `main`; Lucía: ventas, devoluciones, API y pantalla de Ventas. Tests: **41/41** ✅ (incluye anular bulto, devoluciones y API de ventas)._

> 🔄 **Todos: hacer `git pull origin main` en su rama antes de seguir.**
> - `observer.py` ahora está en **`models/observer.py`** (lo movió Lucía) y tiene la única clase `Eventos`.
> - Los imports van **sin** `backend.` (`from models.x import ...`), si no `python app.py` no arranca.

> ⚠ La versión con ORM (SQLAlchemy), ABM y PRs #1–#3 **no está en `main`**, pero no se perdió:
> está en la compu de Marlén (rama `main` local y rama `mar`). Si el grupo decide volver a ella, se restaura.

## 🔜 LO QUE FALTA (actualizado 31/10)
_Estado: los 7 procesos ✅ · 6 reportes ✅ · 3 patrones ✅ · **76/76 tests** ✅_

**1. Guardar y subir lo último**
- [x] Commit de los cambios sin guardar: "el CD no registra ventas ni devoluciones" (`app.py` + test + `README.md`)
- [x] Subir `mar` y pasarla a `main` (PR o `git push origin mar:main`)

**2. Limpieza de código**
- [x] Borrar los DAOs viejos duplicados en `models/` (`categoria_dao.py`, `producto_dao.py`, `proveedor_dao.py`): usan `inventario.db` y nadie los importa; los buenos están en `dao/` → Facundo
- [x] Actualizar el dibujo del comentario de `models/bulto.py` (falta el estado `ANULADO`) → Marlén

**3. Documentación (lo único grande que queda)** → Marlén
- [ ] **Diagrama de clases** en `documentacion/` (models + services + patrones)
- [ ] **Diagrama de estados del bulto** (PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO → VERIFICADO / RECHAZADO, y ANULADO desde PREPARADO/PRECINTADO)
- [ ] Enlazar los diagramas desde `documentacion/README.md`

**4. Prueba final entre los tres**
- [ ] Probar el circuito completo con login: catálogo → solicitud → bulto → despacho → recepción → verificación → venta → devolución → reportes
- [ ] Probar con dos usuarios a la vez armando bultos del mismo producto (bloqueo de stock)

**5. Defensa**
- [ ] Cada uno sabe explicar su parte: Facundo (ABM, procesos 1-2), Lucía (ventas, devoluciones, login, procesos 7), Marlén (logística, bloqueo, Observer, reportes, procesos 3-6)
- [ ] Los 3 explican los patrones: Singleton (`BaseDeDatos`), Observer (2 sujetos / 3 observadores), creación delegada / Factory (medios de pago)
- [ ] Repasar las reglas de negocio: stock solo verificado, precinto roto → rechazado, historial inmutable, no vender sin stock, devoluciones válidas

**Opcionales (suman si sobra tiempo):** promociones / listas de precios · lotes y vencimientos · clientes frecuentes · inventario físico

---

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
_Terminado: `catalogo_service.py` + DAOs en `dao/` sobre `BaseDeDatos`, endpoints, pantalla Catálogo y 16 tests._
- [x] **Unificar los DAOs con la base del proyecto**: hoy usan `inventario.db`; tienen que usar `tp_cd_locales.db` (la conexión Singleton `BaseDeDatos`)
- [x] **Alinear DAOs con `schema.sql`**: `CategoriaDAO` usa `descripcion` y `ProveedorDAO` usa `nombre`, `telefono`, `mail`, `direccion`, que no existen en las tablas → agregar columnas o sacarlas
- [x] `services/catalogo_service.py`: alta / modificación / baja de **productos, categorías y proveedores**
- [x] Validar duplicados: producto por `codigo`, proveedor por `cuit` (consigna) → `ReglaNegocioError`
- [x] No permitir borrar algo ya usado (con stock, órdenes o bultos)
- [x] **Proceso 1**: alta / modificación / baja de **sucursales** (no duplicar nombre, siempre al menos un CD)
- [x] Endpoints `POST` / `PUT` / `DELETE` de todo lo anterior en `app.py`
- [x] Pantalla **Catálogo** (reemplazar `Pendiente.jsx`) con productos, categorías, proveedores y sucursales
- [x] Tests del ABM (duplicados, borrar algo usado, datos inválidos)

### 🟣 Lucía — rama `lucia` · Ventas, devoluciones y medios de pago (proceso 7)
- [x] Tablas en `schema.sql`: `venta`, `detalle_venta` (precio del momento), `pago`, `comprobante`, `devolucion`, `detalle_devolucion` + sus clases en `models/`
- [x] Creación delegada de medios de pago con `CreadorMedioDePago`, creadores concretos e `IMedioDePago`; integrado en `VentasService` y probado
- [x] **Arreglar test que falla por redondeo**: `test_venta_usa_el_creador...` da `1540.0000000000002` en vez de `1540` → `round(total, 2)` o `pytest.approx`
- [x] `VentasService.registrar_venta`: uno o más productos, solo en LOCAL, no más del stock disponible y verificado (`StockService.restar`)
- [x] Cobro con medio de pago (usando creadores concretos) y comprobante con número correlativo
- [x] `registrar_devolucion`: la venta tiene que existir, no más de lo vendido (sumando devoluciones anteriores), repone stock y registra egreso de caja
- [x] `VentasService` recibe el **mismo** `StockService` que `app.py` (para el Observer)
- [x] Endpoints `/api/ventas`, `/api/ventas/<id>`, `/api/devoluciones`
- [x] Pantalla **Ventas y devoluciones**
- [x] Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva

### 🟠 Marlén — rama `mar` · Logística, patrones, reportes y documentación
- [x] **Proceso 3**: `sugerir_orden(local_id)` con los productos bajo `stock_minimo` + botón "Sugerir orden" en Logística
      (`LogisticaService.sugerir_orden` + `GET /api/sucursales/<id>/sugerencia` + botón en `Logistica.jsx`)
- [x] **Bloqueo de stock** (2 usuarios a la vez): reservar stock del CD al empaquetar + `GestorBloqueos` + tests de concurrencia
      (`services/bloqueos.py` + columna `reservado` en `stock` + `StockService.reservar/consumir_reserva` + 4 tests nuevos → 13/13)
- [x] **Observer completo**: `AlertaStockMinimoObserver` + `AuditoriaObserver` + `/api/alertas` y `/api/eventos` + avisos en Stock y Reportes
      (2 sujetos, 3 observadores, tablas `alerta_stock` y `evento_log`, 8 tests en `test_observer.py`)
- [x] **Anular bulto** antes de despachar (libera la reserva)
  - [x] Estado `ANULADO` en `EstadoBulto` (desde PREPARADO o PRECINTADO; es estado final)
  - [x] `StockService.liberar_reserva`
  - [x] `LogisticaService.anular_bulto(bulto_id, motivo)` (con bloqueo + transacción; solo desde PREPARADO/PRECINTADO)
  - [x] Que lo empaquetado de la orden no cuente los bultos anulados (`AND b.estado != 'ANULADO'` en `obtener_orden`)
  - [x] Endpoint `POST /api/bultos/<id>/anular` (body: `{"motivo": "..."}`)
  - [x] Botón "Anular" en Logística (`api.js` + `Logistica.jsx`; pide el motivo, solo en PREPARADO/PRECINTADO)
  - [x] Test: anular libera la reserva / no se puede anular un bulto despachado (+ motivo obligatorio → 3 tests nuevos)
- [x] **Reporte**: existencias actuales y productos en stock mínimo (`/api/reportes/existencias`, filas bajo mínimo en rojo)
- [x] **Reporte**: movimientos y valorización del inventario (`/api/reportes/movimientos`: entradas, salidas y valor a costo por sucursal y motivo)
- [x] **Reporte**: ventas e ingresos por período, local y medio de pago (`/api/reportes/ventas`)
- [x] **Reporte**: productos más vendidos y margen de ganancia/pérdida, descontando devoluciones (`/api/reportes/mas-vendidos`)
- [x] Filtro de fechas en la pantalla de Reportes (desde/hasta → ventas, más vendidos y rechazados)


----------------------------------------------------
- [ ] **Diagrama de clases** y **diagrama de estados del bulto** en `documentacion/`
- [x] Documentar las reglas que definió el grupo + actualizar `documentacion/README.md` (hecho por Lucía)

### 🤝 Entre los tres (al final)
- [x] Validar el JSON de entrada en `app.py` (`cuerpo_json` / `entero_positivo` → 400)
- [ ] Probar el circuito completo: catálogo → orden → bulto → despacho → recepción → venta → devolución → reportes
- [x] Que no se suban `__pycache__`, `.pytest_cache` ni `*.db` (`.gitignore`)
- [ ] Preparar la defensa: cada uno explica su parte y los patrones (Singleton, Observer y creación delegada)

---

# 📋 Estado según la consigna (versión actual de `main`)

| # | Proceso | Estado | Responsable |
|---|---|---|---|
| 1 | Sucursales y CD | ✅ ABM completo (siempre queda un CD) | Facundo |
| 2 | Productos, categorías, precios, mínimos, proveedores | ✅ ABM + pantalla Catálogo | Facundo |
| 3 | Consolidar necesidades en orden de reposición | ✅ orden manual + sugerencia por stock mínimo | Marlén |
| 4 | Empaquetar en bultos con remito y precinto | ✅ con reserva de stock y bloqueo entre usuarios | Marlén |
| 5 | Despacho | ✅ funciona | Facundo |
| 6 | Recepción con verificación de precinto | ✅ funciona | Facundo |
| 7 | Ventas, cobros, comprobante, devoluciones | ✅ | Lucía |

**Validaciones de negocio**
- [x] Stock disponible en destino solo con remito + bulto Verificado; precinto roto → Rechazado
- [x] Trazabilidad inmutable (triggers en `schema.sql`)
- [x] No vender más que el stock disponible y verificado (`StockService.restar` atómico + test) → Lucía
- [x] Sin productos ni proveedores duplicados (código y CUIT `UNIQUE` + tests) → Facundo
- [x] No aceptar devoluciones inválidas → Lucía

**Patrones (mínimo 2)**
- [x] Singleton: `BaseDeDatos` en `database/conexion.py`
- [x] Observer: 2 sujetos (`LogisticaService`, `StockService`) y 3 observadores (`StockObserver`, `AlertaStockMinimoObserver`, `AuditoriaObserver`)
- [x] Creación delegada de medios de pago (`CreadorMedioDePago` + `IMedioDePago`) → Lucía

**Reportes (mínimo 4 no triviales — hay 6 ✅)**
- [x] Bultos rechazados y merma
- [x] Tiempo promedio de tránsito CD → local
- [x] Existencias y stock mínimo → Marlén
- [x] Movimientos y valorización → Marlén
- [x] Ventas por período, local y medio de pago → Marlén
- [x] Más vendidos y margen → Marlén

**Opcionales (suman):** órdenes de compra sugeridas · promociones y listas de precios · lotes/vencimientos · clientes frecuentes · inventario físico
