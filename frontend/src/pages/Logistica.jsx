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

  return (
    <div className="tarjeta">
      <div className="fila-titulo">
        <strong>Orden #{orden.id}</strong>
        <span>{orden.origen} → {orden.destino}</span>
        <span className={`estado ${orden.estado}`}>{orden.estado}</span>
        {orden.remito_numero && <span>Remito {orden.remito_numero} · {orden.remito_estado}</span>}
      </div>

      <table>
        <thead><tr><th>Producto</th><th>Pedido</th><th>Empaquetado</th></tr></thead>
        <tbody>
          {orden.items.map((i) => (
            <tr key={i.producto_id}><td>{i.nombre}</td><td>{i.cantidad}</td><td>{i.empaquetado}</td></tr>
          ))}
        </tbody>
      </table>

      {pendientes.length > 0
        && ['PENDIENTE', 'EN_PREPARACION'].includes(orden.estado)
        && (orden.remito_estado ?? 'ABIERTO') === 'ABIERTO' && (
        <div className="armar">
          <em>Armar bulto:</em>
          {pendientes.map((i) => (
            <label key={i.producto_id}>
              {i.nombre} (máx {Number(i.cantidad) - Number(i.empaquetado || 0)})
              <input type="number" min="0" value={aEmpaquetar[i.producto_id] ?? ''}
                     onChange={(e) => setAEmpaquetar({ ...aEmpaquetar, [i.producto_id]: e.target.value })} />
            </label>
          ))}
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
      {bulto.estado === 'PRECINTADO' &&
        <button onClick={() => accion(() => api.despachar(bulto.id))}>Despachar</button>}
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
