# 📦 **Sistema de Ventas e Inventario — Centro de Distribución a Locales**

---

## 🧭 **Introducción**

📘 Trabajo Práctico Integrador de **Desarrollo de Aplicaciones con Objetos** (UTN FRC · 2026) — **Tema 3**.

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
- 📝 **Solicitudes de reposición** iniciadas por los locales, con selección de CD de origen y local de destino.
- 🔎 **Selección de productos y cantidades** al solicitar reposición o registrar ventas.
- 📦 **Empaquetado en bultos** con remito y precinto de seguridad único generado automáticamente.
- 🚚 **Despacho por el CD** y recepción en dos pasos por el local destinatario: primero confirma que recibió físicamente el bulto y después verifica remito y precinto.
- 💲 **Consulta de precio de venta** de los productos en el inventario.
- 🔁 **Ciclo de vida del bulto** con trazabilidad inmutable:
  `Preparado → Precintado → En tránsito → Recibido → Verificado / Rechazado`
- 🛒 **Ventas** de uno o más productos, con medio de pago y comprobante.
- ↩️ **Devoluciones** con impacto en stock y caja.
- 📈 **Reportes** de ventas, productos más vendidos, existencias, movimientos y bultos rechazados.

> El ABM completo de sucursales, productos, categorías y proveedores todavía no está
> implementado en la interfaz; no forma parte de las funcionalidades disponibles actualmente.

---

## 🔐 **Acceso y permisos**

- El registro crea una cuenta asociada a la sucursal elegida. Las contraseñas se almacenan
  hasheadas y la sesión se mantiene en una cookie HTTP segura según la configuración.
- Para registrar una cuenta de CD, el servidor debe tener configurada la variable
  `CD_REGISTRATION_CODE`. El usuario ingresa ese código al registrarse; no se debe guardar
  el código en el repositorio.
- Las cuentas locales pueden consultar únicamente su stock, ventas y reportes. Pueden crear
  solicitudes eligiendo cualquier CD de origen y cualquier local de destino, y consultar las
  solicitudes que hicieron o que tienen como destino su sucursal.
- La sugerencia automática de reposición calcula faltantes usando el stock mínimo del local
  asociado a la cuenta. No se habilita para otros locales.
- El CD consulta las órdenes y sucursales y se ocupa de preparar bultos, generar precintos y
  despachar. No puede crear solicitudes ni confirmar recepciones.
- La pantalla de ventas está disponible para locales; las cuentas CD no registran ventas al
  público. El registro de ventas no muestra un listado de ventas previas.
- Solo el local que figura como destino de la orden puede confirmar la recepción física y
  verificar el remito y el precinto. La API aplica estos permisos además de ocultar o mostrar
  las acciones correspondientes en la interfaz.

---

## 🛡️ **Reglas de Negocio Clave**

- 🔒 La mercadería **no queda disponible para la venta** hasta que el remito se verifica.
- ❌ Un bulto con **precinto roto o que no coincide** se rechaza y no habilita la venta.
- 🧭 La confirmación de recepción física y la verificación son operaciones separadas. El
  estado `RECIBIDO` registra la primera; el stock no cambia en esa etapa.
- 🔢 El precinto se genera automáticamente y es único para cada bulto.
- 📦 Si un remito tiene varios bultos, el stock se actualiza al finalizar la verificación de
  todos: ingresan únicamente las unidades de los bultos verificados.
- 📉 No se puede **vender más** que el stock disponible y verificado.
- 🧾 No se aceptan **devoluciones** de ventas inexistentes ni por más unidades de las vendidas.

### 🛒 Ventas

- Las ventas al público se registran **solo en sucursales de tipo `LOCAL`**. El `CD` abastece a los locales y no vende al público.
- Cada venta debe incluir al menos un producto existente; cada producto puede aparecer una sola vez en la solicitud y su cantidad debe ser un entero positivo.
- El precio de venta vigente se copia al detalle al registrar la venta. Ese precio histórico se usa para calcular devoluciones aunque luego cambie el precio del catálogo.
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
- Cada unidad devuelta se valora al precio unitario histórico de su venta.
- El importe reintegrado se calcula **proporcionalmente al total efectivamente pagado**. Así se distribuyen entre los productos devueltos los descuentos de efectivo y los recargos de crédito. En devoluciones parciales, el redondeo se ajusta contra el importe acumulado previamente reintegrado, para que al devolver todo no se reintegre más ni menos que el pago original.
- Al aceptar una devolución, las unidades regresan al stock del mismo local donde se registró la venta y se registra un movimiento de caja de tipo `EGRESO` por el importe reintegrado. El registro de devolución, el movimiento de caja y la reposición de stock forman una sola transacción.

---

## 📊 **Reportes y Estadísticas**

- 💰 **Ventas e ingresos** por período, local y medio de pago.
- 🏆 **Productos más vendidos** con margen estimado.
- 📋 **Existencias actuales** y productos en stock mínimo.
- 🚨 **Bultos rechazados** y merma valorizada por rotura de precinto.
- ⏱️ **Tiempo promedio de tránsito** CD → local.

---

## 🧩 **Patrones de Diseño**

| Patrón | Dónde se aplica | Para qué |
|--------|-----------------|----------|
| 🔂 **Singleton** | `BaseDeDatos` | Una única conexión compartida por toda la aplicación |
| 👀 **Observer** | `LogisticaService` → `StockObserver` | Al verificar un remito, el stock se actualiza sin acoplar logística con inventario |
| 💳 **Creación delegada** | `CreadorMedioDePago` y sus creadores concretos | Cada creador construye un medio concreto y ventas trabaja con `IMedioDePago` |

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
│   ├── models/         → clases del dominio
│   ├── patrones/       → Observer
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
