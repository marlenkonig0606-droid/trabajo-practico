import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Reportes() {
  const [rechazados, setRechazados] = useState([])
  const [transito, setTransito] = useState([])

  useEffect(() => {
    api.reporteRechazados().then(setRechazados)
    api.reporteTransito().then(setTransito)
  }, [])

  return (
    <section>
      <div className="tarjeta">
        <h2>Contenedores rechazados / merma por precinto</h2>
        <Tabla filas={rechazados} columnas={['contenedor_id', 'remito', 'destino', 'motivo', 'unidades', 'merma_valorizada']} />
      </div>
      <div className="tarjeta">
        <h2>Tiempo promedio de tránsito CD → local</h2>
        <Tabla filas={transito} columnas={['local', 'contenedores', 'horas_promedio']} />
      </div>
      <p className="vacio">TODO: ventas por período/local/medio de pago, más vendidos con margen, stock mínimo.</p>
    </section>
  )
}

function Tabla({ filas, columnas }) {
  if (filas.length === 0) return <p className="vacio">Sin datos.</p>
  return (
    <table>
      <thead><tr>{columnas.map((c) => <th key={c}>{c.replaceAll('_', ' ')}</th>)}</tr></thead>
      <tbody>{filas.map((f, i) => <tr key={i}>{columnas.map((c) => <td key={c}>{f[c]}</td>)}</tr>)}</tbody>
    </table>
  )
}
