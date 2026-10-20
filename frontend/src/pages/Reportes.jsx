import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Reportes() {
  const [rechazados, setRechazados] = useState([])
  const [transito, setTransito] = useState([])
  const [eventos, setEventos] = useState([])
  const [existencias, setExistencias] = useState([])
  const [movimientos, setMovimientos] = useState([])

  useEffect(() => {
    api.reporteRechazados().then(setRechazados)
    api.reporteTransito().then(setTransito)
    api.eventos().then(setEventos)
    api.reporteExistencias().then(setExistencias)
    api.reporteMovimientos().then(setMovimientos)
  }, [])

  return (
    <section>
      <div className="tarjeta">
        <h2>Existencias actuales y stock mínimo</h2>
        <Tabla filas={existencias}
               columnas={['sucursal', 'codigo', 'producto', 'disponible', 'reservado', 'libre', 'stock_minimo', 'estado']}
               resaltar={(f) => f.estado === 'BAJO MÍNIMO'} />
      </div>
      <div className="tarjeta">
        <h2>Movimientos y valorización del inventario (a precio de costo)</h2>
        <Tabla filas={movimientos}
               columnas={['sucursal', 'motivo', 'movimientos', 'entradas', 'salidas', 'valor_neto']} />
      </div>
      <div className="tarjeta">
        <h2>Bultos rechazados / merma por precinto</h2>
        <Tabla filas={rechazados} columnas={['bulto_id', 'remito', 'destino', 'motivo', 'unidades', 'merma_valorizada']} />
      </div>
      <div className="tarjeta">
        <h2>Tiempo promedio de tránsito CD → local</h2>
        <Tabla filas={transito} columnas={['local', 'bultos', 'horas_promedio']} />
      </div>
      <div className="tarjeta">
        <h2>Registro de eventos logísticos</h2>
        <Tabla filas={eventos} columnas={['fecha', 'evento', 'detalle']} />
      </div>
      <p className="vacio">TODO: ventas por período/local/medio de pago, más vendidos con margen.</p>
    </section>
  )
}

function Tabla({ filas, columnas, resaltar }) {
  if (filas.length === 0) return <p className="vacio">Sin datos.</p>
  return (
    <table>
      <thead><tr>{columnas.map((c) => <th key={c}>{c.replaceAll('_', ' ')}</th>)}</tr></thead>
      <tbody>{filas.map((f, i) => <tr key={i} className={resaltar?.(f) ? 'bajo' : ''}>{columnas.map((c) => <td key={c}>{f[c]}</td>)}</tr>)}</tbody>
    </table>
  )
}
