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

- 🏬 **ABM de sucursales** (locales y Centro de Distribución).
- 🏷️ **ABM de productos, categorías, precios, stock mínimo y proveedores**, sin duplicados por código / CUIT.
- 📝 **Órdenes de reposición** CD → local, consolidando las necesidades de cada local.
- 📦 **Empaquetado en bultos** con remito de despacho y precinto de seguridad.
- 🚚 **Despacho y recepción** con verificación del precinto.
- 🔁 **Ciclo de vida del bulto** con trazabilidad inmutable:
  `Preparado → Precintado → En tránsito → Recibido → Verificado / Rechazado`
- 🛒 **Ventas** de uno o más productos, con medio de pago y comprobante.
- ↩️ **Devoluciones** con impacto en stock y caja.

---

## 🛡️ **Reglas de Negocio Clave**

- 🔒 La mercadería **no queda disponible para la venta** hasta que el remito se verifica.
- ❌ Un bulto con **precinto roto o que no coincide** se rechaza y no habilita la venta.
- 📉 No se puede **vender más** que el stock disponible y verificado.
- 🧾 No se aceptan **devoluciones** de ventas inexistentes ni por más unidades de las vendidas.

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
| 🏭 **Factory** | `MedioPagoFactory` | Crear el medio de pago correcto (efectivo, tarjeta, transferencia) sin `if/elif` en ventas |

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
│   ├── patrones/       → Observer y Factory
│   ├── services/       → reglas de negocio
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
python app.py            # http://localhost:5000

# Frontend (otra terminal)
cd frontend
npm install
npm run dev              # http://localhost:5173
```
