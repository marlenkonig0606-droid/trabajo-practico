# Checklist TP Integrador — CD a Locales

## 🔴 Obligatorio (pide la consigna)

### Proceso 1 y 2 — ABM de catálogo
- [ ] Clases `Categoria` y `Proveedor` en `models/`
- [ ] `services/catalogo_service.py` con alta / modificación / baja
- [ ] Endpoints POST / PUT / DELETE para sucursales, categorías, proveedores y productos
- [ ] Validar producto duplicado por `codigo` → `ReglaNegocioError`
- [ ] Validar proveedor duplicado por `cuit` → `ReglaNegocioError`
- [ ] Decidir qué pasa al borrar algo que ya se usó (¿baja lógica con `activo = 0`?)
- [ ] Validar precios y stock mínimo >= 0, precio_venta >= precio_costo (o justificar si no)

### Proceso 3 — Consolidar necesidades
- [ ] `LogisticaService.sugerir_orden(local_id)`: productos bajo `stock_minimo`
- [ ] Botón "Sugerir" en la pantalla de Logística

### Patrón Factory
- [ ] `TarjetaCredito` (recargo por cuotas), `TarjetaDebito`, `Transferencia`
- [ ] Completar `MedioPagoFactory.crear`
- [ ] Test: tipo de pago inexistente lanza error

### Proceso 7 — Ventas y devoluciones
- [ ] Tablas: `venta`, `detalle_venta` (precio del momento), `pago`, `comprobante`, `devolucion`, `detalle_devolucion`
- [ ] `registrar_venta`: solo en LOCAL, no vender más del stock disponible
- [ ] Generar comprobante
- [ ] `registrar_devolucion`: la venta tiene que existir, no devolver más de lo vendido (contando devoluciones anteriores)
- [ ] Devolución repone stock y registra egreso de caja
- [ ] Endpoints `/api/ventas` y `/api/devoluciones`
- [ ] Tests: venta sin stock, venta en el CD, devolución de venta inexistente, devolución excesiva

### Reportes (mínimo 4 — hay 2)
- [x] Contenedores rechazados / merma por precinto
- [x] Tiempo promedio de tránsito CD → local
- [ ] Ventas e ingresos por período, local y medio de pago
- [ ] Productos más vendidos con margen estimado
- [ ] Existencias y productos en stock mínimo

### Frontend
- [ ] Pantalla Catálogo (ABM)
- [ ] Pantalla Ventas y devoluciones
- [ ] Agregar los reportes nuevos (con filtro de fechas)

## 🟡 Para mejorar (lo que ya está hecho)

- [ ] Validar el JSON de entrada en `app.py`: hoy, si falta `destino_id`, da error 500 en lugar de 400
- [ ] Orden pasa a DESPACHADA con el primer contenedor aunque queden contenedores sin despachar → ¿estado "DESPACHADA_PARCIAL"?
- [ ] No hay forma de cancelar una orden ni anular un contenedor antes de despachar
- [ ] El CD se toma como "el primero que encuentre" (`LIMIT 1`): si hubiera dos CD habría que elegirlo
- [ ] Una sola conexión SQLite compartida entre hilos de Flask: alcanza para el TP, pero saber explicarlo en la defensa
- [ ] Mostrar mensaje de éxito en el frontend (hoy solo muestra errores)
- [ ] Segundo Observer: `AlertaStockMinimoObserver` (suma puntos por usar el patrón de verdad)

## 🟢 Opcional / suma en la defensa
- [ ] Gráfico de barras de ventas por mes (como el repo de referencia)
- [ ] Login con roles (encargado de CD / vendedor de local)
- [ ] Exportar reportes a PDF
- [ ] Diagrama de clases y de estados del contenedor para la presentación
- [ ] Subirlo a GitHub (el `.gitignore` ya está)

## 📚 Para vos (entender antes de seguir)
- [ ] Responder las 3 preguntas del Paso 1 del README
- [ ] Responder las 3 preguntas del ABM
- [ ] Poder explicar Singleton, Observer y Factory con TU código
- [ ] Borrar `Documentos\tp-cd-locales.zip`
