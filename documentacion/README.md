# 📦 **Sistema de Ventas e Inventario — Centro de Distribución a Locales**

---

## 🧭 **Introducción**

📘 Trabajo Práctico Integrador de **Desarrollo de Aplicaciones con Objetos** (UTN FRC · 2026) — **Tema 3**.

📄 Consigna completa: [consigna-tema3.pdf](consigna-tema3.pdf)

📑 Trabajo práctico integrador: [Trabajo práctico integrador (1).pdf](Trabajo%20pr%C3%A1ctico%20integrador%20(1).pdf) · DER editable: [der.drawio](der.drawio)

El sistema gestiona una cadena de locales que se abastecen desde un **Centro de Distribución (CD)**: desde la orden de reposición y el armado de bultos precintados, pasando por el despacho y la verificación en el local, hasta la venta al público y las devoluciones.

---

## 👥 **Integrantes del Proyecto**

| Legajo | Apellido y Nombre |
|--------|-------------------|
| 408567 | Konig Soria, Marlén Sofía |
| 408519 | Rey Laje, Facundo |
| 408683 | Tresca, Lucía Isabel |

---

## ⚙️ **Funcionalidades Principales**

- 🔐 **Registro e inicio de sesión** para usuarios asociados a una sucursal; el alta de cuentas CD requiere un código de invitación configurado por el servidor.
- 📊 **Stock por sucursal**, ventas, devoluciones y reportes con permisos según el tipo de cuenta.
- 📝 **Solicitudes de reposición** iniciadas por los locales para su propia sucursal, con selección de CD de origen.
- 🔎 **Selección de productos y cantidades** al solicitar reposición o registrar ventas.
- 📦 **Empaquetado en bultos** con remito y precinto de seguridad único generado automáticamente.
- 🚚 **Despacho por el CD** y recepción en dos pasos por el local destinatario: primero confirma que recibió físicamente el bulto y después verifica remito y precinto.
- 💲 **Consulta de precio de venta** de los productos en el inventario.
- 🔁 **Ciclo de vida del bulto** con trazabilidad inmutable:
  `Preparado → Precintado → En tránsito → Recibido → Verificado / Rechazado`
- 🛒 **Ventas** de uno o más productos, con medio de pago y comprobante.
- ↩️ **Devoluciones** con impacto en stock y caja.
- 📈 **Reportes** de ventas, productos más vendidos, existencias, movimientos filtrables por tipo y bultos rechazados.

> El ABM de sucursales, productos, categorías y proveedores está disponible para cuentas CD.

---

## 🏢 **Catálogo, sucursales y proveedores**

- Una cuenta CD puede crear locales y centros de distribución desde **Catálogo → Sucursales**.
  Nombre, dirección y tipo son obligatorios; las sucursales activas aparecen en el selector de
  registro de cuentas.
- La baja de una sucursal es una desactivación lógica: se conservan el stock y el historial.
  Una sucursal inactiva no admite inicio de sesión ni nuevas ventas, solicitudes, recepciones o
  despachos hacia ella. No se puede desactivar un local con bultos en tránsito o pendientes de
  verificación, ni el último CD activo.
- Los proveedores pueden activarse y desactivarse. Los inactivos no se pueden asignar a
  productos nuevos; los productos ya asociados conservan ese vínculo.
- Los códigos de producto se normalizan a minúsculas y sin espacios antes de guardarse y
  compararse. No se permite eliminar un producto mientras tenga stock disponible o reservado
  en alguna sucursal.

---

## 🔐 **Acceso y permisos**

- El registro crea una cuenta asociada a la sucursal elegida. Las contraseñas se almacenan
  hasheadas y la sesión se mantiene en una cookie HTTP segura según la configuración.
- Para registrar una cuenta de CD, el servidor debe tener configurada la variable
  `CD_REGISTRATION_CODE`. El usuario ingresa ese código al registrarse; no se debe guardar
  el código en el repositorio.
- Las cuentas locales pueden consultar únicamente su stock, ventas y reportes. Pueden crear
  solicitudes para su propia sucursal, eligiendo cualquier CD de origen, y consultar las
  solicitudes que hicieron o que tienen como destino su sucursal.
- La sugerencia automática de reposición calcula faltantes usando el stock mínimo del local
  asociado a la cuenta, descontando las reposiciones abiertas sin contarlas como stock
  disponible. No se habilita para otros locales.
- El CD consulta las órdenes y sucursales y se ocupa de preparar bultos, generar precintos y
  despachar. También puede ajustar el stock disponible de su propio CD, sin reducirlo por
  debajo de las unidades reservadas. No puede crear solicitudes ni confirmar recepciones.
- La pantalla de ventas está disponible para locales; las cuentas CD no registran ventas al
  público. El registro de ventas no muestra un listado de ventas previas.
- Solo el local que figura como destino de la orden puede confirmar la recepción física y
  elegir entre **Verificar** y **Rechazar** después de inspeccionar el remito y el precinto.
  La API aplica estos permisos además de ocultar o mostrar las acciones correspondientes en
  la interfaz.

---

## 🛡️ **Reglas de Negocio Clave**

- 🔒 La mercadería **no queda disponible para la venta** hasta que el remito se verifica.
- ❌ Un bulto con **precinto roto o que no coincide** se rechaza; la mercadería vuelve al CD,
  no se convierte automáticamente en merma.
- 🧭 La confirmación de recepción física y la verificación son operaciones separadas. El
  estado `RECIBIDO` registra la primera; el stock no cambia en esa etapa.
- 🔢 El precinto se genera automáticamente y es único para cada bulto.
- 📝 La decisión de verificación del remito y precinto se registra con las acciones
  **Verificar** y **Rechazar** del local destinatario.
- 📦 Si un remito tiene varios bultos, el stock se actualiza al finalizar la verificación de
  todos: ingresan únicamente las unidades de los bultos verificados.
- 🔢 Los bultos se preparan en orden de solicitud. Si un bulto precintado debe modificarse,
  primero se reabre con motivo y se invalida el precinto anterior.
- ⏳ Las órdenes vencen a los 30 días; el sistema deja un aviso en las 24 horas previas y libera
  las reservas al vencer. Un bulto puede declararse perdido tras 48 horas en tránsito.
- 📉 No se puede **vender más** que el stock disponible y verificado.
- 🧮 Una diferencia entre saldo y movimientos bloquea el producto hasta conciliarlo con un
  ajuste registrado y motivo explícito.
- 🧾 No se aceptan **devoluciones** de ventas inexistentes ni por más unidades de las vendidas.

### 🛒 Ventas

- Las ventas al público se registran **solo en sucursales de tipo `LOCAL`**. El `CD` abastece a los locales y no vende al público.
- Cada venta debe incluir al menos un producto existente; cada producto puede aparecer una sola vez en la solicitud y su cantidad debe ser un entero positivo.
- El producto debe estar activo, habilitado en el local y tener un precio de venta mayor que cero.
- El precio de venta vigente se copia al detalle al registrar la venta. Ese precio histórico se usa para calcular devoluciones aunque luego cambie el precio del catálogo.
- El costo vigente también se copia a la venta y se conserva en sus movimientos; cambios futuros del catálogo no revalorizan operaciones pasadas.
- El stock se descuenta del local dentro de la misma transacción que registra los detalles, el pago y el comprobante. Si una validación falla, la venta completa se revierte.
- El comprobante recibe un número correlativo. Cada venta registra un único pago; **no se admiten pagos divididos entre varios medios** en esta versión.

### 💳 Medios de pago

- **Efectivo:** aplica un descuento del 10% sobre el subtotal.
- **Tarjeta de crédito:** aplica un recargo del 5% por cada cuota. Si no se especifican cuotas, se toma una cuota; la cantidad debe ser un entero positivo.
- **Tarjeta de débito y transferencia:** no aplican descuento ni recargo.
- El tipo de medio de pago debe ser uno de los admitidos por el sistema; uno desconocido se rechaza.

### ↩️ Devoluciones y caja

- Una devolución debe referirse a una venta existente, incluir al menos un producto de esa venta y tener un motivo no vacío.
- La suma de las cantidades devueltas en todas las devoluciones de una venta no puede superar las cantidades vendidas. Se permiten devoluciones parciales en varias operaciones.
- Las devoluciones solo se permiten hasta 30 días después de la venta; el límite de cantidades se comprueba dentro de la transacción.
- Cada unidad devuelta se valora al precio unitario histórico de su venta.
- El importe reintegrado se calcula **proporcionalmente al total efectivamente pagado**. Así se distribuyen entre los productos devueltos los descuentos de efectivo y los recargos de crédito. En devoluciones parciales, el redondeo se ajusta contra el importe acumulado previamente reintegrado, para que al devolver todo no se reintegre más ni menos que el pago original.
- Al aceptar una devolución, las unidades regresan al stock del mismo local donde se registró la venta y se registra un movimiento de caja de tipo `EGRESO` por el importe reintegrado. El registro de devolución, el movimiento de caja y la reposición de stock forman una sola transacción.

---

## 📊 **Reportes y Estadísticas**

- 🧾 **Resumen ejecutivo** al inicio de la pantalla, filtrable por fecha: el CD ve datos de todos los locales y cada local ve únicamente los suyos.
- 💰 **Ventas e ingresos** por período, local y medio de pago.
- 🏆 **Productos más vendidos** con margen calculado mediante costos históricos; los costos faltantes no se estiman con el catálogo actual.
- 📋 **Existencias actuales**, tránsito, recepción pendiente y diferencias entre saldo y movimientos.
- 🚨 **Bultos rechazados** con valorización histórica, sin clasificarlos automáticamente como merma.
- ⏱️ **Tiempo promedio de entregas verificadas** CD → local y alertas de bultos sin verificar a las 24/48 horas.

El reporte de movimientos permite seleccionar ventas, devoluciones y recepciones. Las ventas
se valorizan positivamente por el precio histórico; las devoluciones, negativamente; y
las recepciones por el costo histórico del despacho. Cada venta y devolución tiene un botón para abrir
una ventana con su detalle de productos y precios.

---

## 🧩 **Patrones de Diseño**

| Patrón | Dónde se aplica | Para qué |
|--------|-----------------|----------|
| 🔂 **Singleton** | `BaseDeDatos` | Una única conexión compartida por toda la aplicación |
| 👀 **Observer** | `models/observer.py`, `LogisticaService`, `StockService` y observadores | Los sujetos notifican eventos sin conocer qué componentes reaccionan |
| 💳 **Creación de medios de pago** | `services/medio_pago_service.py` y creadores concretos | Cada creador construye un medio concreto con la interfaz común `IMedioDePago` |

## 🏗️ **Capas y responsabilidades**

La aplicación separa las responsabilidades para que las rutas HTTP, las reglas de negocio y
las consultas a SQLite no estén mezcladas:

1. **`app.py` (API Flask):** define las rutas, exige sesión, comprueba permisos y traduce las
   respuestas y errores a HTTP/JSON.
2. **`services/` (negocio):** valida reglas y coordina operaciones, por ejemplo registrar una
   venta junto con su pago, comprobante y descuento de stock.
3. **`dao/` (persistencia):** concentra las consultas y escrituras SQL agrupadas por dominio.
   Los servicios y las rutas no ejecutan SQL directamente.
4. **`models/` (dominio):** representa entidades y comportamientos propios, como los estados
   permitidos de un bulto y el cálculo de un medio de pago.
5. **`database/` (infraestructura):** administra la conexión SQLite, el esquema, las
   transacciones y la carga de datos iniciales.

Los DAOs usan la instancia compartida de `BaseDeDatos`. Cuando una operación tiene varias
escrituras relacionadas, se ejecutan dentro de una transacción para confirmarlas juntas o
revertirlas ante un error.

### DAOs por área

| DAO | Datos que encapsula |
|-----|---------------------|
| `AuthDAO` | Usuarios y sucursales para el registro y autenticación |
| `ProductoDAO`, `CategoriaDAO`, `ProveedorDAO`, `SucursalDAO` | ABM del catálogo |
| `LogisticaDAO` | Órdenes, remitos, bultos e historial |
| `StockDAO` | Existencias, reservas y movimientos |
| `VentasDAO` | Ventas, detalles, pagos, comprobantes y devoluciones |
| `ReportesDAO` | Consultas agregadas para los informes |
| `ObservadoresDAO` | Alertas de stock y eventos de auditoría |

El servicio conserva la regla del negocio; el DAO conoce el SQL necesario para leer o guardar
los datos. La interfaz Flask llama al servicio, no al DAO directamente.

## 🧪 **Datos de demostración**

Al iniciar la aplicación se cargan dos CD, dos locales, tres proveedores, seis productos,
stock para los locales, cuatro ventas y una devolución. La carga se ejecuta una sola vez por
base de datos para no duplicar operaciones ni reponer stock de demostración en cada reinicio.
En bases preexistentes, agrega los registros de demostración que falten como conjunto inicial
sin borrar las operaciones existentes; una marca `demo-v1` evita volver a ejecutar esa carga.
No se generan usuarios ni contraseñas de prueba: registrá una cuenta en el local que quieras
probar. Para crear una cuenta CD sigue siendo necesario configurar el código de invitación.

La aplicación tiene una opción interna para omitir la carga de demostración al crearla, usada
por las pruebas automatizadas para mantener sus bases aisladas.

## 📈 **Resumen ejecutivo**

El primer bloque de Reportes se puede filtrar por fechas `Desde` y `Hasta`. En una cuenta CD
el resumen abarca todos los locales e indica cuál obtuvo mayores ingresos netos; en una cuenta
local se limita a su sucursal. Presenta ventas, ingresos, devoluciones, ingresos netos, ticket
promedio, unidades, producto más vendido y referencias bajo el mínimo actual. La API valida
fechas con formato ISO (`AAAA-MM-DD`), rechaza fechas futuras y no permite un inicio posterior
al fin del rango. Los reportes detallados que siguen mantienen sus propios controles.

---

## 🛠️ **Tecnologías**

| Capa | Tecnología |
|------|------------|
| 🐍 Backend | **Python 3** + **Flask** (API REST) |
| 🗄️ Base de datos | **SQLite** |
| ⚛️ Frontend | **React** + **Vite** |
| 🧪 Testing | **pytest** |
| 💻 Entorno | Visual Studio Code |

---

## 🗂️ **Estructura del Proyecto**

```
tp-cd-locales/
├── backend/
│   ├── app.py          → rutas de la API
│   ├── database/       → conexión (Singleton), esquema y datos iniciales
│   ├── dao/            → acceso a datos por dominio
│   ├── models/         → clases del dominio y contratos Observer
│   ├── services/       → reglas de negocio y creadores de medios de pago
│   └── tests/          → pruebas automáticas
├── frontend/           → interfaz en React
└── documentacion/      → este archivo
```

---

## ▶️ **Cómo Ejecutarlo**

```bash
# Backend
cd backend
pip install -r requirements.txt
$env:CD_REGISTRATION_CODE = "configurar-un-codigo-local"
python app.py            # http://localhost:5000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev              # http://localhost:5173
```

La variable debe configurarse en la terminal del backend antes de iniciar Flask. Para
producción, usar un código de invitación privado y configurar también `FLASK_SECRET_KEY` con
un valor secreto persistente; habilitar `FLASK_COOKIE_SECURE=1` al servir sobre HTTPS.
Las pruebas backend se ejecutan desde `backend/` con `python -m pytest -v`.
