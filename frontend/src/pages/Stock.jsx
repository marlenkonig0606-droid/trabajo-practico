import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Stock({ usuario }) {
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal] = useState('')
  const [filas, setFilas] = useState([])
  const [ediciones, setEdiciones] = useState({})
  const [alertas, setAlertas] = useState([])
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')

  useEffect(() => {
    api.sucursales().then((lista) => {
      setSucursales(lista)
      const propia = lista.find((s) => s.id === usuario.sucursal_id)
      setSucursal(propia?.id ?? '')
    }).catch((e) => setError(e.message))
  }, [usuario.sucursal_id, usuario.tipo])
  useEffect(() => {
    if (!sucursal) return
    api.stock(sucursal).then((lista) => {
      setFilas(lista)
      setEdiciones(Object.fromEntries(lista.map((f) => [f.producto_id, String(f.disponible)])))
    }).catch((e) => setError(e.message))
    api.alertas().then(setAlertas).catch((e) => setError(e.message))
  }, [sucursal])

  const puedeEditar = usuario.tipo === 'CD'
    && Number(sucursal) === usuario.sucursal_id
    && sucursales.find((s) => s.id === Number(sucursal))?.tipo === 'CD'

  const guardarStock = async (productoId) => {
    setError('')
    setMensaje('')
    try {
      const disponible = Number(ediciones[productoId])
      const lista = await api.ajustarStock(Number(sucursal), productoId, disponible)
      setFilas(lista)
      setEdiciones(Object.fromEntries(lista.map((f) => [f.producto_id, String(f.disponible)])))
      setMensaje('Stock actualizado.')
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <>
    {error && <div className="error">{error}</div>}
    {mensaje && <div className="exito">{mensaje}</div>}
    {alertas.length > 0 && (
      <section className="tarjeta alertas">
        <h2>⚠ Productos bajo el stock mínimo ({alertas.length})</h2>
        <ul>
          {alertas.map((a) => (
            <li key={a.id}>
              <b>{a.producto}</b> en {a.sucursal}: quedan {a.libre} libres (mínimo {a.minimo})
              <span className="fecha"> · desde {a.fecha}</span>
            </li>
          ))}
        </ul>
      </section>
    )}
    <section className="tarjeta">
      <h2>Stock disponible (vendible)</h2>
      <select value={sucursal} onChange={(e) => setSucursal(e.target.value)}>
        {sucursales.filter((s) => usuario.tipo === 'CD' || s.id === usuario.sucursal_id)
          .map((s) => <option key={s.id} value={s.id}>{s.nombre} ({s.tipo})</option>)}
      </select>
      <table>
        <thead><tr><th>Código</th><th>Producto</th><th>Precio de venta</th><th>Disponible</th><th>Reservado</th><th>Libre</th><th>Mínimo</th>{puedeEditar && <th>Acción</th>}</tr></thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.producto_id} className={f.libre < f.stock_minimo ? 'bajo' : ''}>
              <td>{f.codigo}</td>
              <td>{f.nombre}</td>
              <td>${Number(f.precio_venta).toFixed(2)}</td>
              <td>{puedeEditar
                ? <input aria-label={`Stock disponible de ${f.nombre}`} type="number"
                         min={f.reservado} step="1" value={ediciones[f.producto_id] ?? ''}
                         onChange={(e) => setEdiciones({
                           ...ediciones, [f.producto_id]: e.target.value,
                         })} />
                : f.disponible}</td>
              <td>{f.reservado}</td><td><b>{f.libre}</b></td><td>{f.stock_minimo}</td>
              {puedeEditar && <td>
                <button disabled={ediciones[f.producto_id] === ''
                  || Number(ediciones[f.producto_id]) === f.disponible
                  || !Number.isInteger(Number(ediciones[f.producto_id]))
                  || Number(ediciones[f.producto_id]) < f.reservado}
                  onClick={() => guardarStock(f.producto_id)}>Guardar</button>
              </td>}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
    </>
  )
}
