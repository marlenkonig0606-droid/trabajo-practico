import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Logistica() {
  const [productos, setProductos] = useState([])
  const [ordenes, setOrdenes] = useState([])
  const [error, setError] = useState('')

  const recargar = () => api.ordenes().then(setOrdenes).catch((e) => setError(e.message))

  useEffect(() => {
    api.productos().then(setProductos)
    recargar()
  }, [])

  // Envuelve cualquier acción: muestra el error de negocio que manda el backend
  const accion = async (fn) => {
    setError('')
    try {
      await fn()
      await recargar()
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }

  const nombreProducto = (id) => productos.find((p) => p.id === id)?.nombre ?? `#${id}`

  return (
    <section>
      {error && <div className="error" onClick={() => setError('')}>{error}</div>}
      <h2>Órdenes de reposición</h2>
      {ordenes.length === 0 && <p className="vacio">Todavía no hay órdenes.</p>}
      {ordenes.map((o) => (
        <Orden key={o.id} orden={o} nombreProducto={nombreProducto} accion={accion} />
      ))}
    </section>
  )
}

function Orden({ orden, nombreProducto, accion }) {
  const pendientes = orden.items.filter(
    (i) => Number(i.cantidad) > Number(i.empaquetado || 0),
  )
  const puedeReintentar = orden.estado === 'CERRADA'
    && orden.remito_estado === 'RECHAZADO' && !orden.resolucion
  const permitePreparar = ['PENDIENTE', 'EN_PREPARACION'].includes(orden.estado)
    || puedeReintentar
  const [aEmpaquetar, setAEmpaquetar] = useState({})
  const [empaquetando, setEmpaquetando] = useState(false)

  const armarBulto = async () => {
    const items = Object.entries(aEmpaquetar)
      .filter(([, c]) => Number(c) > 0)
      .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
    setEmpaquetando(true)
    const creado = await accion(() => api.crearBulto(orden.id, items))
    setEmpaquetando(false)
    if (creado) setAEmpaquetar({})
  }

  const resolver = (accionOrden) => {
    const motivo = window.prompt(`Motivo para ${accionOrden.toLowerCase()} la orden #${orden.id}`)
    if (motivo === null) return
    accion(() => api.resolverOrden(orden.id, accionOrden, motivo))
  }

  return (
    <div className="tarjeta">
      <div className="fila-titulo">
        <strong>Orden #{orden.id}</strong>
        <span>{orden.origen} → {orden.destino}</span>
        <span className={`estado ${orden.estado}`}>{orden.estado}</span>
        {orden.remito_numero && <span>Remito {orden.remito_numero} · {orden.remito_estado}</span>}
        {orden.fecha_vencimiento && <span>Vence: {orden.fecha_vencimiento}</span>}
      </div>
      {['PENDIENTE', 'EN_PREPARACION'].includes(orden.estado) && (
        <div className="acciones-formulario">
          <button className="secundario"
            onClick={() => accion(() => api.resolverOrden(orden.id, 'ESPERAR'))}>
            Mantener pendiente
          </button>
          <button className="secundario" onClick={() => resolver('RECHAZAR')}>
            Rechazar solicitud
          </button>
          <button className="peligro" onClick={() => resolver('CANCELAR')}>
            Cancelar solicitud
          </button>
        </div>
      )}

      <table>
        <thead><tr><th>Producto</th><th>Pedido</th><th>Empaquetado</th></tr></thead>
        <tbody>
          {orden.items.map((i) => (
            <tr key={i.producto_id}><td>{i.nombre}</td><td>{i.cantidad}</td><td>{i.empaquetado}</td></tr>
          ))}
        </tbody>
      </table>

      {pendientes.length > 0
        && permitePreparar
        && ((orden.remito_estado ?? 'ABIERTO') === 'ABIERTO' || puedeReintentar) && (
        <div className="armar">
          <div className="armar-cabecera">
            <strong>Preparar bulto</strong>
            <span>{pendientes.length} productos pendientes</span>
          </div>
          <div className="armar-productos">
            {pendientes.map((i) => {
              const maximo = Number(i.cantidad) - Number(i.empaquetado || 0)
              return (
                <label className="producto-empaquetar" key={i.producto_id}>
                  <span>{i.nombre}</span>
                  <small>Pedido {i.cantidad} · pendiente {maximo}</small>
                  <input type="number" min="0" max={maximo} step="1"
                         aria-label={`Cantidad a empaquetar de ${i.nombre}`}
                         value={aEmpaquetar[i.producto_id] ?? ''}
                         onChange={(e) => setAEmpaquetar({
                           ...aEmpaquetar, [i.producto_id]: e.target.value,
                         })} />
                </label>
              )
            })}
          </div>
          <button disabled={empaquetando
            || !Object.values(aEmpaquetar).some((cantidad) => Number(cantidad) > 0)}
            onClick={armarBulto}>
            {empaquetando ? 'Empaquetando…' : 'Empaquetar'}
          </button>
        </div>
      )}

      {orden.bultos.map((b) => (
        <FilaBulto key={b.id} bulto={b} nombreProducto={nombreProducto} accion={accion} />
      ))}
    </div>
  )
}

function FilaBulto({ bulto, nombreProducto, accion }) {
  const [historial, setHistorial] = useState(null)

  const verHistorial = async () =>
    setHistorial(historial ? null : await api.historial(bulto.id))

  const anular = () => {
    const motivo = window.prompt(`Motivo de la anulación del bulto #${bulto.id}`)
    if (motivo === null) return          // canceló el diálogo
    accion(() => api.anular(bulto.id, motivo))
  }

  const reabrir = () => {
    const motivo = window.prompt(`Motivo de reapertura del bulto #${bulto.id}`)
    if (motivo === null) return
    accion(() => api.reabrirBulto(bulto.id, motivo))
  }

  const marcarPerdido = () => {
    const motivo = window.prompt(`Motivo para declarar perdido el bulto #${bulto.id}`)
    if (motivo === null) return
    accion(() => api.marcarPerdido(bulto.id, motivo))
  }

  return (
    <div className="bulto">
      <span>Bulto #{bulto.id}</span>
      <span className={`estado ${bulto.estado}`}>{bulto.estado}</span>
      <span className="items">
        {bulto.items.map((i) => `${i.cantidad} × ${nombreProducto(i.producto_id)}`).join(', ')}
      </span>
      {bulto.precinto && <span>🔒 {bulto.precinto}</span>}

      {bulto.estado === 'PREPARADO' && <>
        <button onClick={() => accion(() => api.precintar(bulto.id))}>Generar precinto</button>
      </>}
      {bulto.estado === 'PRECINTADO' && <>
        <button onClick={() => accion(() => api.despachar(bulto.id))}>Despachar</button>
        <button className="secundario" onClick={reabrir}>Reabrir y cambiar precinto</button>
      </>}
      {bulto.estado === 'EN_TRANSITO' &&
        <button className="peligro" onClick={marcarPerdido}>Declarar perdido</button>}
      {(bulto.estado === 'PREPARADO' || bulto.estado === 'PRECINTADO') &&
        <button onClick={anular}>Anular</button>}
      {bulto.estado === 'EN_TRANSITO' && (
        <span className="ayuda">En tránsito · pendiente de recepción y verificación del local</span>
      )}

      <button className="link" onClick={verHistorial}>{historial ? 'ocultar' : 'historial'}</button>
      {historial && (
        <ol className="historial">
          {historial.map((h, i) => <li key={i}>{h.fecha} — <b>{h.estado}</b> {h.observacion}</li>)}
        </ol>
      )}
    </div>
  )
}
