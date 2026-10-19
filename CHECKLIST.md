# Checklist TP Integrador — Tema 3: CD a Locales
_Actualizado según la consigna (tema3.pdf) y el estado de `main` al 19/10._

## 📋 Procesos obligatorios

### 1. Sucursales y Centro de Distribución
- [x] Listar sucursales (`GET /api/sucursales`)
- [ ] Alta / modificación / baja de sucursales (`POST` / `PUT` / `DELETE /api/sucursales`)
- [ ] Validar nombre duplicado y que siempre exista al menos un CD
- [ ] Pantalla para administrarlas (sumar a `Catalogo.jsx`)

### 2. Productos, categorías, precios, mínimos y proveedores
- [x] ABM de productos, categorías y proveedores (backend + `Catalogo.jsx`)
- [x] Sin duplicados por código de producto / CUIT de proveedor
- [x] Tests (`test_catalogo.py`, `test_productos.py`)

### 3. Consolidar necesidades en orden de reposición
- [x] Crear orden CD → local con origen y destino
- [ ] **Consolidar necesidades**: sugerir la orden con los productos bajo `stock_minimo` del local
- [ ] Botón "Sugerir orden" en Logística

### 4. Empaquetar en contenedores con remito y precinto
- [x] Contenedores, remito y precinto (no se repite)
- [ ] Reservar stock del CD al empaquetar + bloqueo entre usuarios
      (hecho en la rama `mar-bloqueo-observer`, falta pasarlo a SQLAlchemy)

### 5. Despacho · 6. Recepción con verificación de precinto
- [x] Despacho, recepción, Verificado / Rechazado
- [x] Stock entra al local solo cuando el remito está verificado

### 7. Ventas, cobros, comprobante y devoluciones  ⚠ lo más grande que falta
- [ ] Modelos: `Venta`, `DetalleVenta` (con precio del momento), `Pago`, `Comprobante`, `Devolucion`, `DetalleDevolucion`
- [ ] `registrar_venta`: uno o más productos, solo en LOCAL, no más del stock disponible
- [ ] Cobro con medio de pago (usa la Factory)
- [ ] Emisión de comprobante (número correlativo)
- [ ] `registrar_devolucion` con impacto en stock y caja
- [ ] Endpoints `/api/ventas`, `/api/ventas/<id>`, `/api/devoluciones`
- [ ] Pantalla Ventas y devoluciones (hoy es `Pendiente.jsx`)
- [ ] Tests

## ✅ Validaciones de negocio
- [x] Stock disponible en destino solo con remito + contenedor Verificado; precinto roto → Rechazado
- [x] Trazabilidad inmutable de estados (triggers en `conexion.py`)
- [ ] No vender más que el stock disponible y verificado (depende de Ventas)
- [x] Sin productos ni proveedores duplicados
- [ ] No aceptar devoluciones sin venta registrada ni por más de lo vendido (depende de Ventas)

## 🧩 Patrones de diseño (mínimo 2)
- [x] **Singleton**: conexión a la base
- [~] **Observer**: `StockObserver` funciona; falta pasar de `mar-bloqueo-observer` las alertas de stock mínimo y la auditoría
- [ ] **Factory**: completar `TarjetaCredito`, `TarjetaDebito`, `Transferencia` y `MedioPagoFactory.crear` (+ test)

## 📊 Reportes (mínimo 4 no triviales — hay 2)
- [x] Contenedores rechazados / merma por precinto
- [x] Tiempo promedio de tránsito CD → local
- [ ] Ventas e ingresos por período, local y medio de pago (depende de Ventas)
- [ ] Productos más vendidos y margen de ganancia/pérdida (depende de Ventas)
- [ ] Existencias actuales y productos en stock mínimo (**se puede hacer ya**)
- [ ] Movimientos y valorización del inventario (**se puede hacer ya**: tabla de movimientos × precio de costo)
- [ ] Filtro de fechas en la pantalla de Reportes

## 📝 Consideraciones de la consigna
- [ ] Diagrama de clases (entidades, atributos, relaciones)
- [ ] Diagrama de estados del contenedor (lo evalúan "críticamente")
- [ ] Documentar reglas adicionales que definió el grupo (ej.: no se borra un producto con stock)

## 🟡 Mejoras / prolijidad
- [ ] Validar el JSON de entrada (si falta un campo → 400, no 500)
- [ ] Anular contenedor antes de despachar (libera la reserva)
- [ ] Orden "despachada parcial" si quedan contenedores sin despachar
- [ ] Mensajes de éxito en el frontend
- [ ] Sacar del repo `__pycache__` y `.pytest_cache` si se subieron por error

## 🟢 Opcionales (suman, no son obligatorios)
- [ ] Órdenes de compra sugeridas por faltantes
- [ ] Promociones, descuentos y listas de precios
- [ ] Lotes, números de serie o vencimientos
- [ ] Clientes frecuentes / cuenta corriente
- [ ] Inventario físico y conciliación
