# Checklist TP Integrador — Tema 3: CD a Locales
_Armado sobre lo que hay HOY en `main` de GitHub (commit `caed36e` de Facundo: versión con sqlite3 + DAOs, sin ORM) — 19/10._

> ⚠ La versión con ORM (SQLAlchemy), ABM y PRs #1–#3 **no está en `main`**, pero no se perdió:
> está en la compu de Marlén (rama `main` local y rama `mar`). Si el grupo decide volver a ella, se restaura.

## 👥 Reparto de tareas
> Cada uno trabaja en **su rama** (`lucia`, `facu`, `mar`) y sube con Pull Request a `main`.
> Antes de empezar: `git checkout <su-rama>` y `git pull origin main`.
> Archivos compartidos (`app.py`, `api.js`, `App.jsx`, `schema.sql`, `reportes_service.py`): avisar en el grupo antes de tocarlos.

---

### 🔴 PRIMERO (bloquea a todos) — Facundo
**Hoy `main` no arranca: el backend y los tests fallan al iniciar.**
- [ ] `services/logistica_service.py` importa `models.bulto`, pero el archivo ahora es `models/contenedor.py`
      → cambiar a `from models.contenedor import Contenedor, EstadoContenedor` y renombrar `Bulto`/`EstadoBulto` en el service
- [ ] Mismo cambio en `tests/test_logistica.py`
- [ ] `models/categoria.py` tiene `from contenedor import Contenedor`: sobra y además rompe → borrar esa línea
- [ ] Decidir si las rutas/tablas siguen llamándose `bulto` o pasan a `contenedor` (API, `schema.sql`, frontend) y dejarlo parejo
- [ ] Verificar: `python app.py` levanta y `python -m pytest` pasa → recién ahí avisar al grupo

---

### 🔵 Facundo — rama `facu` · ABM de catálogo y sucursales (procesos 1 y 2)
_Ya armó los DAOs y models de categoría, producto y proveedor: falta conectarlos._
- [ ] **Unificar los DAOs con la base del proyecto**: hoy usan `inventario.db`; tienen que usar `tp_cd_locales.db` (la conexión Singleton `BaseDeDatos`)
- [ ] **Alinear DAOs con `schema.sql`**: `CategoriaDAO` usa `descripcion` y `ProveedorDAO` usa `nombre`, `telefono`, `mail`, `direccion`, que no existen en las tablas → agregar columnas o sacarlas
- [ ] `services/catalogo_service.py`: alta / modificación / baja de **productos, categorías y proveedores**
- [ ] Validar duplicados: producto por `codigo`, proveedor por `cuit` (consigna) → `ReglaNegocioError`
- [ ] No permitir borrar algo ya usado (con stock, órdenes o contenedores)
- [ ] **Proceso 1**: alta / modificación / baja de **sucursales** (no duplicar nombre, siempre al menos un CD)
- [ ] Endpoints `POST` / `PUT` / `DELETE` de todo lo anterior en `app.py`
- [ ] Pantalla **Catálogo** (reemplazar `Pendiente.jsx`) con productos, categorías, proveedores y sucursales
- [ ] Tests del ABM (duplicados, borrar algo usado, datos inválidos)

### 🟣 Lucía — rama `lucia` · Ventas, devoluciones y Factory (proceso 7)
- [ ] Tablas en `schema.sql`: `venta`, `detalle_venta` (precio del momento), `pago`, `comprobante`, `devolucion`, `detalle_devolucion` + sus clases en `models/`
- [ ] **Factory** (`patrones/factory_medio_pago.py`): `TarjetaCredito` (recargo por cuotas), `TarjetaDebito`, `Transferencia` + completar `MedioPagoFactory.crear` + test de tipo inexistente
- [ ] `VentasService.registrar_venta`: uno o más productos, solo en LOCAL, no más del stock disponible y verificado (`StockService.restar`)
- [ ] Cobro con medio de pago (usando la Factory) y comprobante con número correlativo
- [ ] `registrar_devolucion`: la venta tiene que existir, no más de lo vendido (sumando devoluciones anteriores), repone stock y registra egreso de caja
- [ ] `VentasService` recibe el **mismo** `StockService` que `app.py` (para el Observer)
- [ ] Endpoints `/api/ventas`, `/api/ventas/<id>`, `/api/devoluciones`
- [ ] Pantalla **Ventas y devoluciones**
- [ ] Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva

### 🟠 Marlén — rama `mar` · Logística, patrones, reportes y documentación
_El bloqueo y el Observer completo ya están hechos sobre sqlite3 en la rama `mar-bloqueo-observer`: solo hay que adaptarlos a `contenedor`._
- [ ] **Proceso 3**: `sugerir_orden(local_id)` con los productos bajo `stock_minimo` + botón "Sugerir orden" en Logística
- [ ] **Bloqueo de stock** (2 usuarios a la vez): reservar stock del CD al empaquetar + `GestorBloqueos` + tests de concurrencia
- [ ] **Observer completo**: `AlertaStockMinimoObserver` + `AuditoriaObserver` + `/api/alertas` y `/api/eventos` + avisos en Stock y Reportes
- [ ] Anular contenedor antes de despachar (libera la reserva)
- [ ] **Reporte**: existencias actuales y productos en stock mínimo
- [ ] **Reporte**: movimientos y valorización del inventario
- [ ] **Reporte** (cuando Lucía termine): ventas e ingresos por período, local y medio de pago
- [ ] **Reporte** (cuando Lucía termine): productos más vendidos y margen de ganancia/pérdida
- [ ] Filtro de fechas en la pantalla de Reportes
- [ ] **Diagrama de clases** y **diagrama de estados del contenedor** en `documentacion/`
- [ ] Documentar las reglas que definió el grupo + actualizar `documentacion/README.md`

### 🤝 Entre los tres (al final)
- [ ] Validar el JSON de entrada en `app.py` (campo faltante → 400, no 500)
- [ ] Probar el circuito completo: catálogo → orden → contenedor → despacho → recepción → venta → devolución → reportes
- [ ] Que no se suban `__pycache__`, `.pytest_cache` ni `*.db`
- [ ] Preparar la defensa: cada uno explica su parte y los 3 patrones (Singleton, Observer, Factory)

---

# 📋 Estado según la consigna (versión actual de `main`)

| # | Proceso | Estado | Responsable |
|---|---|---|---|
| 1 | Sucursales y CD | 🟡 solo listar | Facundo |
| 2 | Productos, categorías, precios, mínimos, proveedores | 🟡 models y DAOs, sin conectar | Facundo |
| 3 | Consolidar necesidades en orden de reposición | 🟡 orden manual, falta sugerir | Marlén |
| 4 | Empaquetar en contenedores con remito y precinto | 🟡 hecho, pero roto por el import + falta reserva | Facundo / Marlén |
| 5 | Despacho | 🟡 hecho, roto por el import | Facundo |
| 6 | Recepción con verificación de precinto | 🟡 hecho, roto por el import | Facundo |
| 7 | Ventas, cobros, comprobante, devoluciones | ❌ falta | Lucía |

**Validaciones de negocio**
- [x] Stock disponible en destino solo con remito + contenedor Verificado; precinto roto → Rechazado
- [x] Trazabilidad inmutable (triggers en `schema.sql`)
- [ ] No vender más que el stock disponible y verificado → Lucía
- [ ] Sin productos ni proveedores duplicados (los DAOs lo intentan, falta conectarlos) → Facundo
- [ ] No aceptar devoluciones inválidas → Lucía

**Patrones (mínimo 2)**
- [x] Singleton: `BaseDeDatos` en `database/conexion.py`
- [~] Observer: `StockObserver` funciona; faltan alertas y auditoría → Marlén
- [ ] Factory: medios de pago → Lucía

**Reportes (mínimo 4 no triviales — hay 2)**
- [x] Bultos/contenedores rechazados y merma
- [x] Tiempo promedio de tránsito CD → local
- [ ] Existencias y stock mínimo → Marlén
- [ ] Movimientos y valorización → Marlén
- [ ] Ventas por período, local y medio de pago → Marlén (después de Lucía)
- [ ] Más vendidos y margen → Marlén (después de Lucía)

**Opcionales (suman):** órdenes de compra sugeridas · promociones y listas de precios · lotes/vencimientos · clientes frecuentes · inventario físico
