import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Stock() {
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal] = useState('')
  const [filas, setFilas] = useState([])

  useEffect(() => { api.sucursales().then((s) => { setSucursales(s); setSucursal(s[0]?.id ?? '') }) }, [])
  useEffect(() => { if (sucursal) api.stock(sucursal).then(setFilas) }, [sucursal])

  return (
    <section className="tarjeta">
      <h2>Stock disponible (vendible)</h2>
      <select value={sucursal} onChange={(e) => setSucursal(e.target.value)}>
        {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre} ({s.tipo})</option>)}
      </select>
      <table>
        <thead><tr><th>Código</th><th>Producto</th><th>Disponible</th><th>Mínimo</th></tr></thead>
        <tbody>
          {filas.map((f) => (
            <tr key={f.producto_id} className={f.disponible < f.stock_minimo ? 'bajo' : ''}>
              <td>{f.codigo}</td><td>{f.nombre}</td><td>{f.disponible}</td><td>{f.stock_minimo}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
