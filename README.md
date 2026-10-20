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
El código no se guarda en el repositorio. Para correr tests: `python -m pytest -v` desde
`backend/`.

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
    auth_service.py         cuentas locales/CD y contraseñas hasheadas
    logistica_service.py    procesos 3-6 completos
    stock_service.py        stock + StockObserver
    reportes_service.py     reportes de logística, ventas e inventario
    ventas_service.py       ventas, cobros y devoluciones
  tests/                    pruebas de servicios y API
frontend/src/pages/
  Acceso.jsx ✅  Solicitudes.jsx ✅  Logistica.jsx ✅  Stock.jsx ✅  Reportes.jsx ✅  Ventas.jsx ✅
```

## Acceso por sucursal

El registro desde la pantalla de inicio de sesión crea cuentas para la sucursal seleccionada.
Para el CD, exige el código configurado en el servidor. Las contraseñas se guardan hasheadas.

Las cuentas locales solo consultan su stock, ventas y reportes. Desde Reposición pueden crear
solicitudes eligiendo cualquier CD de origen y local de destino; ven las órdenes dirigidas a
su sucursal y las que solicitaron. La sugerencia automática usa únicamente el stock de su
propia sucursal. El CD puede consultar todas las órdenes y gestionar su preparación, armado y
despacho, pero no crear solicitudes ni confirmar recepciones.

El local destinatario confirma primero la recepción física y luego verifica el remito y el
precinto. El stock no cambia al confirmar la recepción: solo se actualiza cuando finaliza la
verificación de todos los bultos del remito, incorporando únicamente los bultos verificados.
Si el precinto no coincide o está roto, el bulto se rechaza y no se incorpora. La API valida
los permisos en el servidor.

En producción, configurá `FLASK_SECRET_KEY` con un valor secreto persistente y serví la
aplicación por HTTPS con `FLASK_COOKIE_SECURE=1`. En desarrollo local, la app genera una
clave temporal al iniciarse.

## Qué ya está resuelto (y cómo defenderlo)

**Ciclo de vida del bulto** (`models/bulto.py`): `PREPARADO → PRECINTADO → EN_TRANSITO → RECIBIDO →
VERIFICADO | RECHAZADO`. El local registra primero la recepción física (`RECIBIDO`) y realiza
la verificación del remito y precinto en una segunda acción. Las transiciones válidas están en
una tabla (`TRANSICIONES`) y el propio objeto rechaza saltos (`cambiar_estado`). No se puede
despachar sin precintar, ni recibir dos veces.

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

## Estado de funcionalidades y documentación

La descripción funcional completa —permisos, solicitudes, recepción, ventas, devoluciones,
reportes y patrones— está en [documentacion/README.md](./documentacion/README.md). El ABM de
sucursales, productos, categorías y proveedores sigue pendiente; la pantalla Catálogo es
todavía un marcador de posición.
