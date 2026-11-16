# TP Integrador DAO 2026 — Tema 3: CD a Locales

Backend en **Python (Flask + SQLite)**, frontend en **React + Vite**. Misma idea que el repo de
referencia (`alquilerDeAutos`), pero con las capas separadas en carpetas.

## Cómo correrlo

```bash
# Terminal 1 — backend
cd backend
pip install -r requirements.txt
$env:CD_REGISTRATION_CODE = "marlufa"
python app.py                # http://localhost:5000 (crea la base y carga datos de prueba)

# Terminal 2 — frontend
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

La variable debe configurarse antes de iniciar Flask y en la misma terminal. Si el backend
ya estaba ejecutándose cuando la configuraste, detenelo con Ctrl+C y volvé a iniciarlo. El
registro permite crear cuentas locales y, con esa variable configurada, cuentas del CD.
El código no se guarda en el repositorio. Para correr tests, desde `backend/`, ejecutá
`python -m pytest -v`.

**Código de invitación del CD (alternativa sin variable de entorno):** también se puede crear el
archivo `backend/cd_registration_code.txt` con el código en la primera línea (por ejemplo
`dao2026`). El backend lo lee en cada registro, así que no hace falta reiniciarlo. Si la variable
`CD_REGISTRATION_CODE` está configurada, tiene prioridad sobre el archivo. El archivo está en
`.gitignore`: cada integrante tiene el suyo y el código no se sube al repositorio.

Para producción, configurá además `FLASK_SECRET_KEY` con un valor secreto persistente y
serví la aplicación por HTTPS con `FLASK_COOKIE_SECURE=1`. En desarrollo se genera una clave
temporal al iniciar, por lo que las sesiones no sobreviven a un reinicio del servidor.

## Arquitectura

```
backend/
  app.py                    rutas de la API (HTTP -> service -> JSON)
  database/
    conexion.py             ★ SINGLETON: una sola conexión para toda la app
    schema.sql              tablas + triggers que hacen inmutable el historial
    datos_iniciales.py      catálogo, 2 CD, 2 locales y operaciones demo
  dao/                      SQL y persistencia agrupados por dominio
    auth_dao.py             usuarios y datos de sucursal para autenticación
    producto_dao.py, categoria_dao.py, proveedor_dao.py, sucursal_dao.py
    logistica_dao.py        órdenes, remitos, bultos e historial
    stock_dao.py            existencias y movimientos de stock
    ventas_dao.py           ventas, pagos, comprobantes y devoluciones
    reportes_dao.py         consultas de reportes
    observadores_dao.py     alertas y eventos de auditoría
  models/                   entidades y reglas propias del dominio
    observer.py             ★ OBSERVER: Sujeto / Observador / Eventos
    medio_pago.py           medios de pago y sus cálculos
  services/                 reglas de negocio y coordinación de operaciones
    auth_service.py         cuentas locales/CD y contraseñas hasheadas
    catalogo_service.py     validación y ABM del catálogo
    logistica_service.py    solicitudes, armado, despacho y recepción
    stock_service.py        reservas, stock y notificaciones
    reportes_service.py     resumen y reportes de logística, ventas e inventario
    ventas_service.py       ventas, cobros y devoluciones
  tests/                    pruebas de servicios y API
frontend/src/pages/
  Acceso.jsx  Solicitudes.jsx  Logistica.jsx  Stock.jsx  Reportes.jsx  Ventas.jsx  Catalogo.jsx
```

### Responsabilidad de cada capa

- `app.py` registra las rutas HTTP, exige sesión y verifica permisos; delega el trabajo a los
  servicios y convierte sus errores en respuestas HTTP.
- `services/` aplica las reglas de negocio y coordina operaciones que pueden involucrar varias
  entidades o movimientos.
- `dao/` encapsula las consultas SQL y escrituras. Los servicios no ejecutan SQL directamente.
- `models/` representa conceptos del dominio y reglas propias de esos objetos, por ejemplo las
  transiciones válidas de un bulto y el cálculo de cada medio de pago.
- `database/` configura SQLite, transacciones, esquema y carga inicial.

Todos los DAOs comparten la conexión administrada por `BaseDeDatos` (Singleton). Las operaciones
compuestas usan transacciones para confirmar juntas sus escrituras o revertirlas si ocurre un
error.
Al abrir una base de una versión anterior, `BaseDeDatos` aplica migraciones compatibles; por
ejemplo, agrega `proveedor.nombre` y los estados de actividad para sucursales y proveedores.
Los registros existentes quedan activos y los proveedores sin nombre toman su razón social.

## Acceso por sucursal

El registro desde la pantalla de inicio de sesión crea cuentas para la sucursal seleccionada.
Para el CD, exige el código configurado en el servidor. Las contraseñas se guardan hasheadas.

### Roles de local: Administrador y Empleado

| | Administrador | Empleado |
|---|---|---|
| Pestaña **Mi local** (panel con ventas, stock bajo mínimo, órdenes, bultos y equipo) | ✅ | ❌ |
| Aprobar o rechazar cuentas y dar de alta perfiles (eligiendo el rol) | ✅ | ❌ |
| Habilitar productos en el local | ✅ | ❌ (403) |
| Reportes | ✅ | ❌ (403) |
| Ventas, devoluciones, reposición, recepción y stock | ✅ | ✅ |

- **Administrador automático:** al crear un local desde Catálogo, en la misma transacción se crea su
  administrador (correo indicado o `admin.local<id>@cdlocales.local`) con una contraseña temporal que
  se muestra una sola vez al CD. Si falla la creación del administrador, el local tampoco se crea.
  Los locales que ya existían reciben uno al iniciar el backend: sus credenciales se muestran en la
  consola y se guardan en `backend/credenciales_iniciales.txt` (no se sube, está en `.gitignore`).
- **Aprobación:** quien se registra en un local queda `PENDIENTE` (elige si solicita perfil de
  Empleado o Administrador). Si intenta entrar, ve el aviso de cuenta pendiente. El administrador
  la aprueba (confirmando o cambiando el rol) o la rechaza con un motivo.
- **Contraseña temporal:** al aprobar, el sistema genera una contraseña aleatoria (`secrets`) que el
  administrador entrega. Con ella la persona entra, pero el backend bloquea todo
  (`CAMBIO_PASSWORD_OBLIGATORIO`) hasta que elige una propia.
- **Bases existentes:** la migración deja aprobadas las cuentas que ya había; en cada local la más
  antigua pasa a Administrador y el resto a Empleado. En el CD no se usan roles.

Las cuentas locales solo consultan su stock, ventas y (si son administradoras) reportes. Desde Reposición pueden crear
solicitudes para su propia sucursal y elegir cualquier CD como origen; ven las órdenes dirigidas
a su sucursal y las que solicitaron. La sugerencia automática usa únicamente el stock de su
propia sucursal. El CD puede consultar todas las órdenes y gestionar su preparación, armado y
despacho, y ajustar el stock disponible de su propio centro, pero no crear solicitudes ni
confirmar recepciones. El CD solo distribuye: las ventas y devoluciones las registran
únicamente los locales, cada uno en su propia sucursal.

El local destinatario confirma primero la recepción física. Luego inspecciona el remito y el
precinto y elige **Verificar** o **Rechazar**. El stock no cambia al confirmar la recepción:
solo se actualiza cuando finaliza la verificación de todos los bultos del remito, incorporando
únicamente los bultos verificados. La API valida los permisos en el servidor.

El reporte de movimientos permite filtrar ventas, devoluciones y recepciones. Las ventas
muestran su valorización positiva a precio de venta, las devoluciones la valorización negativa
y las recepciones usan el costo unitario guardado al despacho. Si un registro antiguo no tiene
costo guardado, el reporte lo indica como faltante. Ventas y devoluciones incluyen una ventana
emergente con el detalle de productos y precios.
La pantalla de reportes comienza con un resumen ejecutivo filtrable por fecha: el CD ve los
resultados globales y el local solo los de su propia sucursal.

Al iniciar, la base recibe datos de demostración si todavía no fueron cargados: dos CD,
dos locales, seis productos, tres proveedores, stock local, cuatro ventas y una devolución.
La carga tiene una marca de versión y no vuelve a insertar las operaciones ni a reponer el
stock de los locales al reiniciar. En una base que ya contenía datos de versiones anteriores,
se agregan los registros faltantes del catálogo y los datos de demostración una sola vez; no
se borra la información existente. No se crean usuarios de demostración: registrá una cuenta
para el local que quieras probar.

## Reportes

La pantalla comienza con un resumen ejecutivo filtrable por fecha. El CD ve datos globales y
el usuario local ve solo su sucursal. Incluye ventas, ingresos, devoluciones, ingresos netos,
ticket promedio, unidades y producto más vendido; para el CD también indica el local con
mayores ingresos netos. Las fechas futuras y los rangos invertidos se rechazan tanto en la
interfaz como en la API. Debajo se conservan los reportes detallados y sus filtros.

### Reporte gerencial del local

Los locales (solo el Administrador) tienen una pantalla propia (`ReportesLocal.jsx`) que se
alimenta de `GET /api/reportes/local?anio=AAAA` o `?desde=&hasta=`. Se filtra por **año completo**
o por **período** y se recalcula al cambiar el filtro. Tiene 7 secciones: resumen anual (ventas,
facturado, ticket promedio = facturado ÷ ventas, unidades, mes de mayor facturación y de más
ventas, facturación y ticket mensual), medios de pago (importe y %), productos (podio, ranking y
comparación mensual de dos productos), estadística de tickets (media, mediana, desvío, cuartiles,
atípicos por rango intercuartílico, prueba de Jarque-Bera y campana de Gauss solo si la
distribución lo permite, dispersión), stock (libre vs. mínimo, alertas pendientes y permanencia
reconstruida con `movimiento_stock`), devoluciones, órdenes, tránsito y rechazos, y logística
(pedidos, bultos por CD, bultos vs. ventas y relación ventas ÷ bultos). Los gráficos son SVG
propios (`components/Graficos.jsx`), sin librerías. Los cálculos estadísticos y de permanencia
están en `services/analisis.py`. El CD conserva su pantalla de reportes.

## Catálogo, sucursales y proveedores

Desde **Catálogo → Sucursales**, una cuenta CD puede dar de alta locales y otros centros de
distribución. El nombre, la dirección y el tipo son obligatorios; las sucursales activas se
muestran automáticamente en el selector de registro. Desactivar una sucursal conserva sus
existencias y su historial, pero impide iniciar sesión, vender, solicitar reposición, recibir
mercadería o despachar hacia ella. No se puede desactivar un local con bultos en tránsito o
pendientes de verificación, ni el último CD activo.

Los proveedores también se pueden activar o desactivar. Los inactivos no se ofrecen al crear
productos; los productos ya vinculados conservan el proveedor. El código de producto se guarda
en minúsculas y sin espacios; esa misma normalización se usa para rechazar duplicados. No se
puede eliminar un producto mientras tenga stock disponible o reservado en alguna sucursal.

## Qué ya está resuelto (y cómo defenderlo)

**Ciclo de vida del bulto** (`models/bulto.py`): `PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO →
VERIFICADO | RECHAZADO`, con los estados finales `ANULADO` y `PERDIDO`. El local registra primero
la recepción física (`RECIBIDO`) y realiza la verificación del remito y precinto en una segunda
acción. Antes del despacho, un bulto precintado puede reabrirse con motivo; el precinto anterior
queda invalidado y el nuevo intento recibe otro precinto. Un bulto en tránsito solo puede
declararse perdido tras 48 horas.

**Trazabilidad inmutable**: cada cambio inserta una fila en `historial_bulto`. Dos triggers SQL
abortan cualquier `UPDATE` o `DELETE` sobre esa tabla → la inmutabilidad la garantiza la base,
no solo el código.

**Stock no disponible hasta verificar**: al despachar sale del CD; al local **no** entra nada hasta que
*todos* los bultos del remito están en estado final. Entonces el remito pasa a `VERIFICADO` y solo
se suma lo de los bultos verificados. Un bulto con precinto roto o con número distinto queda
`RECHAZADO` y la mercadería regresa al stock del CD. El reporte conserva el valor histórico del
bulto y no trata el rechazo como merma automática.

**Stock auditable**: los movimientos son el registro auditable y el saldo es el valor operativo.
Una discrepancia bloquea el producto hasta registrar una conciliación con motivo. Las reservas
no alteran el saldo físico; al cancelar se liberan en la misma transacción.

**Solicitudes**: se atienden por orden de creación; una solicitud posterior no puede tomar stock
antes de que la anterior haya sido preparada o resuelta. Los productos deben estar activos y
habilitados para el local; las cantidades deben ser enteros positivos. Las solicitudes vencen
a los 30 días, registran un aviso en las 24 horas previas y liberan las reservas al vencer.

**Ventas y costos históricos**: cada línea guarda su precio y costo de ese momento. Las
devoluciones se limitan a 30 días y a las unidades vendidas aún no devueltas, con revalidación
dentro de la transacción.

**Patrones**
| Patrón | Dónde | Qué problema resuelve |
|---|---|---|
| Singleton | `BaseDeDatos` | Todos los services comparten la misma conexión/transacción |
| Observer | `models/observer.py`, `LogisticaService`, `StockService` y observadores | Los sujetos notifican eventos sin conocer las reacciones que ejecutan los observadores |
| Creación de medios de pago | `services/medio_pago_service.py` y creadores concretos | Cada creador construye un medio de pago que comparte la interfaz `IMedioDePago` |

---

## Estado de funcionalidades y documentación

La descripción funcional completa —permisos, solicitudes, recepción, ventas, devoluciones,
reportes y patrones— está en [documentacion/README.md](./documentacion/README.md). El CD
puede administrar sucursales, productos, categorías y proveedores desde Catálogo.

## Interfaz y stock mínimo por sucursal

- **Listados con filtros y paginación en el backend**: ventas, productos, catálogo, stock,
  solicitudes y recepciones aceptan `?pagina=&por_pagina=` y filtros combinables
  (`q` busca parte del texto sin distinguir mayúsculas ni tildes). Responden
  `{ items, total, pagina, paginas }`. Sin `pagina` siguen devolviendo la lista completa.
- **Pantallas**: acciones con íconos y tooltip, "Abrir detalle" expandible, altas y
  operaciones en modales, una sola acción para activar/desactivar, fechas DD/MM/AAAA.
  Nueva pestaña **Productos** para los locales.
- **Stock mínimo**: cada local tiene el suyo (`producto_sucursal.stock_minimo`, lo edita su
  administrador). El de cada CD es la suma, por producto, de los mínimos de los locales
  activos que lo tienen habilitado (vista `minimo_vigente`). Las alertas se recalculan al
  cambiar stock, mínimos, habilitaciones o sucursales, y al iniciar el backend.
- Se quitó "Mantener pendiente" (acción `ESPERAR`): no cambiaba el estado de la orden.
