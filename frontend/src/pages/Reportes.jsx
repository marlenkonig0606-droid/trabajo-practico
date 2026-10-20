import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Reportes({ usuario }) {
  const [rechazados, setRechazados] = useState([])
  const [transito, setTransito] = useState([])
  const [eventos, setEventos] = useState([])
  const [existencias, setExistencias] = useState([])
  const [movimientos, setMovimientos] = useState([])
  const [ventas, setVentas] = useState([])
  const [masVendidos, setMasVendidos] = useState([])
  const [fechas, setFechas] = useState({ desde: '', hasta: '' })
  const [tiposMovimiento, setTiposMovimiento] = useState([
    'VENTA', 'DEVOLUCION', 'RECEPCION',
  ])
  const [movimientoDetalle, setMovimientoDetalle] = useState(null)

  // Reportes que dependen del período: se recargan cada vez que cambian las fechas
  useEffect(() => {
    api.reporteVentas(fechas).then(setVentas)
    api.reporteMasVendidos(fechas).then(setMasVendidos)
  }, [fechas])

  useEffect(() => {
    api.reporteExistencias().then(setExistencias)
    if (usuario.tipo === 'CD') {
      api.reporteRechazados(fechas).then(setRechazados)
      api.reporteTransito().then(setTransito)
      api.eventos().then(setEventos)
    }
  }, [usuario.tipo, fechas])

  useEffect(() => {
    api.reporteMovimientos(tiposMovimiento).then(setMovimientos)
  }, [tiposMovimiento])

  const cambiarTipoMovimiento = (tipo) => {
    setTiposMovimiento((actuales) => actuales.includes(tipo)
      ? actuales.filter((actual) => actual !== tipo)
      : [...actuales, tipo])
  }

  return (
    <section>
      <div className="tarjeta filtro-fechas">
        <h2>Período</h2>
        <label>Desde <input type="date" value={fechas.desde}
          onChange={(e) => setFechas({ ...fechas, desde: e.target.value })} /></label>
        <label>Hasta <input type="date" value={fechas.hasta}
          onChange={(e) => setFechas({ ...fechas, hasta: e.target.value })} /></label>
        <button className="link" onClick={() => setFechas({ desde: '', hasta: '' })}>Todo</button>
        <span className="vacio">
          Aplica a ventas, más vendidos{usuario.tipo === 'CD' ? ' y bultos rechazados' : ''}.
        </span>
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
        <h2>Movimientos</h2>
        <div className="filtros-movimientos" aria-label="Tipos de movimiento">
          {[
            ['VENTA', 'Ventas'],
            ['DEVOLUCION', 'Devoluciones'],
            ['RECEPCION', 'Recepciones'],
          ].map(([tipo, titulo]) => (
            <label key={tipo}>
              <input type="checkbox" checked={tiposMovimiento.includes(tipo)}
                     onChange={() => cambiarTipoMovimiento(tipo)} />
              {titulo}
            </label>
          ))}
        </div>
        <p className="ayuda">
          Las ventas se muestran con valor positivo, las devoluciones con valor negativo y
          las recepciones sin valorización.
        </p>
        <TablaMovimientos filas={movimientos}
                          onVerDetalle={setMovimientoDetalle} />
      </div>
      {movimientoDetalle && (
        <DetalleMovimiento movimiento={movimientoDetalle}
                            onCerrar={() => setMovimientoDetalle(null)} />
      )}
      {usuario.tipo === 'CD' && <div className="tarjeta">
        <h2>Bultos rechazados / merma por precinto</h2>
        <Tabla filas={rechazados} columnas={['bulto_id', 'remito', 'destino', 'motivo', 'unidades', 'merma_valorizada']} />
      </div>}
      {usuario.tipo === 'CD' && <div className="tarjeta">
        <h2>Tiempo promedio de tránsito CD → local</h2>
        <Tabla filas={transito} columnas={['local', 'bultos', 'horas_promedio']} />
      </div>}
      {usuario.tipo === 'CD' && <div className="tarjeta">
        <h2>Registro de eventos logísticos</h2>
        <Tabla filas={eventos} columnas={['fecha', 'evento', 'detalle']} />
      </div>}
    </section>
  )
}

function TablaMovimientos({ filas, onVerDetalle }) {
  if (filas.length === 0) return <p className="vacio">Sin movimientos para mostrar.</p>
  const nombres = {
    VENTA: 'Venta',
    DEVOLUCION: 'Devolución',
    RECEPCION: 'Recepción',
  }
  return (
    <div className="tabla-movimientos">
      <table>
        <thead><tr>
          <th>Fecha</th><th>Sucursal</th><th>Tipo</th><th>Referencia</th>
          <th>Unidades</th><th>Valor</th><th>Detalle</th>
        </tr></thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={`${fila.tipo}-${fila.operacion_id}`}>
              <td>{fila.fecha}</td><td>{fila.sucursal}</td>
              <td>{nombres[fila.tipo] ?? fila.tipo}</td>
              <td>{fila.referencia}</td><td>{fila.unidades}</td>
              <td>{fila.valor == null ? '—' : `${fila.valor < 0 ? '-' : '+'}$${Math.abs(fila.valor).toFixed(2)}`}</td>
              <td>{fila.venta_id && (
                <button className="secundario"
                        onClick={() => onVerDetalle(fila)}>Ver detalle</button>
              )}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DetalleMovimiento({ movimiento, onCerrar }) {
  const [venta, setVenta] = useState(null)
  const [error, setError] = useState('')
  const devolucion = movimiento.tipo === 'DEVOLUCION'
  const items = devolucion
    ? venta?.devoluciones.filter((d) => d.id === movimiento.devolucion_id) ?? []
    : venta?.items ?? []

  useEffect(() => {
    api.venta(movimiento.venta_id)
      .then(setVenta)
      .catch((e) => setError(e.message))
  }, [movimiento.venta_id])

  return (
    <div className="modal-fondo" onClick={onCerrar}>
      <section className="modal-detalle" role="dialog" aria-modal="true"
               aria-labelledby="titulo-detalle" onClick={(e) => e.stopPropagation()}>
        <div className="modal-cabecera">
          <h2 id="titulo-detalle">{devolucion ? 'Detalle de devolución' : 'Detalle de venta'}</h2>
          <button className="secundario" onClick={onCerrar}>Cerrar</button>
        </div>
        {error && <div className="error">{error}</div>}
        {!venta && !error && <p className="vacio">Cargando detalle…</p>}
        {venta && <>
          <p><b>Venta #{venta.id}</b> · {venta.fecha} · {venta.sucursal}</p>
          {devolucion && items[0] && (
            <p>Devolución #{items[0].id} · {items[0].motivo}</p>
          )}
          <table>
            <thead><tr><th>Producto</th><th>Cantidad</th><th>Precio unitario</th><th>Importe</th></tr></thead>
            <tbody>
              {items.map((item, index) => {
                const importe = Number(item.cantidad) * Number(item.precio_unitario)
                return (
                  <tr key={`${item.producto_id}-${index}`}>
                    <td>{item.nombre}</td><td>{item.cantidad}</td>
                    <td>${Number(item.precio_unitario).toFixed(2)}</td>
                    <td>{devolucion ? '-' : ''}${importe.toFixed(2)}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
          <p className="total-detalle">
            {devolucion ? 'Total devuelto' : 'Total de la venta'}:
            {' '}{devolucion ? '-' : ''}${Math.abs(Number(devolucion
              ? items[0]?.total_devolucion ?? 0
              : venta.total)).toFixed(2)}
          </p>
        </>}
      </section>
    </div>
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
