import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Reportes() {
  const [rechazados, setRechazados] = useState([])
  const [transito, setTransito] = useState([])
  const [eventos, setEventos] = useState([])
  const [existencias, setExistencias] = useState([])
  const [movimientos, setMovimientos] = useState([])
  const [ventas, setVentas] = useState([])
  const [masVendidos, setMasVendidos] = useState([])
  const [fechas, setFechas] = useState({ desde: '', hasta: '' })

  // Reportes que dependen del período: se recargan cada vez que cambian las fechas
  useEffect(() => {
    api.reporteRechazados(fechas).then(setRechazados)
    api.reporteVentas(fechas).then(setVentas)
    api.reporteMasVendidos(fechas).then(setMasVendidos)
  }, [fechas])

  useEffect(() => {
    api.reporteTransito().then(setTransito)
    api.eventos().then(setEventos)
    api.reporteExistencias().then(setExistencias)
    api.reporteMovimientos().then(setMovimientos)
  }, [])

  return (
    <section>
      <div className="tarjeta filtro-fechas">
        <h2>Período</h2>
        <label>Desde <input type="date" value={fechas.desde}
          onChange={(e) => setFechas({ ...fechas, desde: e.target.value })} /></label>
        <label>Hasta <input type="date" value={fechas.hasta}
          onChange={(e) => setFechas({ ...fechas, hasta: e.target.value })} /></label>
        <button className="link" onClick={() => setFechas({ desde: '', hasta: '' })}>Todo</button>
        <span className="vacio">Aplica a ventas, más vendidos y bultos rechazados.</span>
      </div>
      <div className="tarjeta">
        <h2>Ventas e ingresos por día, local y medio de pago</h2>
        <Tabla filas={ventas} columnas={['dia', 'local', 'medio_pago', 'ventas', 'ingresos', 'ticket_promedio']} />
      </div>
      <div className="tarjeta">
        <h2>Productos más vendidos y margen</h2>
        <Tabla filas={masVendidos}
               columnas={['codigo', 'producto', 'unidades', 'ingresos', 'costo', 'margen', 'margen_pct']}
               resaltar={(f) => f.margen < 0} />
      </div>
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
