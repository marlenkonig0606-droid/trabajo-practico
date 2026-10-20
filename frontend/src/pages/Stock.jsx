import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Stock() {
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal] = useState('')
  const [filas, setFilas] = useState([])
  const [alertas, setAlertas] = useState([])

  useEffect(() => { api.sucursales().then((s) => { setSucursales(s); setSucursal(s[0]?.id ?? '') }) }, [])
  useEffect(() => { if (sucursal) api.stock(sucursal).then(setFilas) }, [sucursal])
  useEffect(() => { api.alertas().then(setAlertas) }, [sucursal])

  return (
    <>
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
        {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre} ({s.tipo})</option>)}
      </select>
      <table>
        <thead><tr><th>Código</th><th>Producto</th><th>Precio de venta</th><th>Disponible</th><th>Reservado</th><th>Libre</th><th>Mínimo</th></tr></thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.producto_id} className={f.libre < f.stock_minimo ? 'bajo' : ''}>
              <td>{f.codigo}</td><td>{f.nombre}</td><td>${Number(f.precio_venta).toFixed(2)}</td><td>{f.disponible}</td><td>{f.reservado}</td><td><b>{f.libre}</b></td><td>{f.stock_minimo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
    </>
  )
}
