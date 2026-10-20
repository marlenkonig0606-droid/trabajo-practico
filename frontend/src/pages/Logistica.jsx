import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Logistica() {
  const [sucursales, setSucursales] = useState([])
  const [productos, setProductos] = useState([])
  const [ordenes, setOrdenes] = useState([])
  const [error, setError] = useState('')

  const recargar = () => api.ordenes().then(setOrdenes).catch((e) => setError(e.message))

  useEffect(() => {
    api.sucursales().then(setSucursales)
    api.productos().then(setProductos)
    recargar()
  }, [])

  // Envuelve cualquier acción: muestra el error de negocio que manda el backend
  const accion = async (fn) => {
    setError('')
    try { await fn(); await recargar() } catch (e) { setError(e.message) }
  }

  const nombreProducto = (id) => productos.find((p) => p.id === id)?.nombre ?? `#${id}`

  return (
    <section>
      {error && <div className="error" onClick={() => setError('')}>{error}</div>}
      <NuevaOrden sucursales={sucursales} productos={productos}
                  onCrear={(d, items) => accion(() => api.crearOrden(d, items))} />
      <h2>Órdenes de reposición</h2>
      {ordenes.length === 0 && <p className="vacio">Todavía no hay órdenes.</p>}
      {ordenes.map((o) => (
        <Orden key={o.id} orden={o} nombreProducto={nombreProducto} accion={accion} />
      ))}
    </section>
  )
}

function NuevaOrden({ sucursales, productos, onCrear }) {
  const locales = sucursales.filter((s) => s.tipo === 'LOCAL')
  const [destino, setDestino] = useState('')
  const [cantidades, setCantidades] = useState({})

  const crear = () => {
    const items = Object.entries(cantidades)
      .filter(([, c]) => Number(c) > 0)
      .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
    onCrear(Number(destino), items)
    setCantidades({})

  
  }

  return (
    <div className="tarjeta">
      <h2>Nueva orden (CD → local)</h2>
      <label>Destino{' '}
        <select value={destino} onChange={(e) => setDestino(e.target.value)}>
          <option value="">Elegí un local…</option>
          {locales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
        </select>
      </label>
      <div className="grilla">
        {productos.map((p) => (
          <label key={p.id}>{p.nombre}
            <input type="number" min="0" value={cantidades[p.id] ?? ''}
                   onChange={(e) => setCantidades({ ...cantidades, [p.id]: e.target.value })} />
          </label>
        ))}
      </div>
      <button disabled={!destino} onClick={async () => {
        const items = await api.sugerirOrden(destino)
        setCantidades(Object.fromEntries(items.map((i) => [i.producto_id, i.cantidad])))
      }}>Sugerir orden</button>
      <button disabled={!destino} onClick={crear}>Crear orden</button>
    </div>
  )
}

function Orden({ orden, nombreProducto, accion }) {
  const pendientes = orden.items.filter((i) => i.cantidad > i.empaquetado)
  const [aEmpaquetar, setAEmpaquetar] = useState({})

  const armarBulto = () => {
    const items = Object.entries(aEmpaquetar)
      .filter(([, c]) => Number(c) > 0)
      .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
    accion(() => api.crearBulto(orden.id, items))
    setAEmpaquetar({})
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

      {pendientes.length > 0 && (orden.remito_estado ?? 'ABIERTO') === 'ABIERTO' && (
        <div className="armar">
          <em>Armar bulto:</em>
          {pendientes.map((i) => (
            <label key={i.producto_id}>{i.nombre} (máx {i.cantidad - i.empaquetado})
              <input type="number" min="0" value={aEmpaquetar[i.producto_id] ?? ''}
                     onChange={(e) => setAEmpaquetar({ ...aEmpaquetar, [i.producto_id]: e.target.value })} />
            </label>
          ))}
          <button onClick={armarBulto}>Empaquetar</button>
        </div>
      )}

      {orden.bultos.map((b) => (
        <FilaBulto key={b.id} bulto={b} nombreProducto={nombreProducto} accion={accion} />
      ))}
    </div>
  )
}

function FilaBulto({ bulto, nombreProducto, accion }) {
  const [precinto, setPrecinto] = useState('')
  const [intacto, setIntacto] = useState(true)
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
        <input placeholder="N° precinto" value={precinto} onChange={(e) => setPrecinto(e.target.value)} />
        <button onClick={() => accion(() => api.precintar(bulto.id, precinto))}>Precintar</button>
      </>}
      {bulto.estado === 'PRECINTADO' &&
        <button onClick={() => accion(() => api.despachar(bulto.id))}>Despachar</button>}
      {(bulto.estado === 'PREPARADO' || bulto.estado === 'PRECINTADO') &&
        <button onClick={anular}>Anular</button>}
      {bulto.estado === 'EN_TRANSITO' && <>
        <input placeholder="Precinto leído" value={precinto} onChange={(e) => setPrecinto(e.target.value)} />
        <label><input type="checkbox" checked={intacto} onChange={(e) => setIntacto(e.target.checked)} /> intacto</label>
        <button onClick={() => accion(() => api.recibir(bulto.id, precinto, intacto))}>Recibir</button>
      </>}

      <button className="link" onClick={verHistorial}>{historial ? 'ocultar' : 'historial'}</button>
      {historial && (
        <ol className="historial">
          {historial.map((h, i) => <li key={i}>{h.fecha} — <b>{h.estado}</b> {h.observacion}</li>)}
        </ol>
      )}
    </div>
  )
}
