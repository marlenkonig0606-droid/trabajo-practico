import { useEffect, useState } from 'react'
import { api } from '../api.js'

function fechaLocalHoy() {
  const hoy = new Date()
  const anio = hoy.getFullYear()
  const mes = String(hoy.getMonth() + 1).padStart(2, '0')
  const dia = String(hoy.getDate()).padStart(2, '0')
  return `${anio}-${mes}-${dia}`
}

export default function Reportes({ usuario }) {
  const hoy = fechaLocalHoy()
  const [resumen, setResumen] = useState(null)
  const [fechasResumen, setFechasResumen] = useState({ desde: '', hasta: '' })
  const [errorResumen, setErrorResumen] = useState('')
  const [cargandoResumen, setCargandoResumen] = useState(true)
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

  useEffect(() => {
    let activa = true
    setCargandoResumen(true)
    setErrorResumen('')
    api.reporteResumen(fechasResumen)
      .then((datos) => { if (activa) setResumen(datos) })
      .catch((e) => { if (activa) setErrorResumen(e.message) })
      .finally(() => { if (activa) setCargandoResumen(false) })
    return () => { activa = false }
  }, [fechasResumen, usuario.tipo, usuario.sucursal_id])

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
      <div className="tarjeta resumen-reportes">
        <div className="resumen-cabecera">
          <div>
            <h2>Resumen general · {usuario.tipo === 'CD' ? 'todas las sucursales' : usuario.sucursal}</h2>
            <p className="ayuda">
              {usuario.tipo === 'CD'
                ? 'Una vista rápida del rendimiento de todos los locales.'
                : 'Una vista rápida de las ventas y el stock de tu local.'}
            </p>
          </div>
          <div className="filtro-resumen">
            <label>Desde
              <input type="date" value={fechasResumen.desde}
                max={fechasResumen.hasta || hoy}
                onChange={(e) => setFechasResumen({ ...fechasResumen, desde: e.target.value })} />
            </label>
            <label>Hasta
              <input type="date" value={fechasResumen.hasta}
                max={hoy}
                min={fechasResumen.desde || undefined}
                onChange={(e) => setFechasResumen({ ...fechasResumen, hasta: e.target.value })} />
            </label>
            <button className="link" onClick={() => setFechasResumen({ desde: '', hasta: '' })}>
              Todo el período
            </button>
          </div>
        </div>
        {errorResumen && <div className="error">{errorResumen}</div>}
        {cargandoResumen && <p className="vacio">Calculando resumen…</p>}
        {!cargandoResumen && resumen && <>
          <div className="resumen-indicadores">
            <div><span>Ventas</span><strong>{resumen.ventas}</strong></div>
            <div><span>Ingresos por ventas</span><strong>${Number(resumen.ingresos).toFixed(2)}</strong></div>
            <div><span>Devoluciones</span><strong>{resumen.devoluciones} · ${Number(resumen.importe_devuelto).toFixed(2)}</strong></div>
            <div><span>Ingresos netos</span><strong>${Number(resumen.ingresos_netos).toFixed(2)}</strong></div>
          </div>
          {resumen.ventas === 0 && (
            <p className="resumen-mensaje">No hay ventas en el período seleccionado.</p>
          )}
          <div className="resumen-hallazgos">
            {usuario.tipo === 'CD' && (
              <p>
                <b>Local que más vendió:</b>{' '}
                {resumen.local_mas_vendio
                  ? `${resumen.local_mas_vendio.nombre}, con $${Number(resumen.local_mas_vendio.ingresos_netos).toFixed(2)} netos en ${resumen.local_mas_vendio.cantidad_ventas} ventas.`
                  : 'No hay ventas para comparar.'}
              </p>
            )}
            <p>
              <b>Producto más vendido:</b>{' '}
              {resumen.producto_mas_vendido
                ? `${resumen.producto_mas_vendido.producto}, ${resumen.producto_mas_vendido.unidades} unidades netas.`
                : 'No hay unidades netas vendidas en este período.'}
            </p>
            <p>
              <b>Ticket promedio:</b> ${Number(resumen.ticket_promedio).toFixed(2)}.
              {' '}<b>Unidades vendidas:</b> {resumen.unidades_vendidas}.
            </p>
            <p>
              <b>Stock bajo el mínimo actualmente:</b> {resumen.productos_bajo_minimo} referencias.
            </p>
          </div>
        </>}
      </div>
      <div className="tarjeta filtro-fechas">
        <h2>Período</h2>
        <label>Desde <input type="date" value={fechas.desde} max={fechas.hasta || hoy}
          onChange={(e) => setFechas({ ...fechas, desde: e.target.value })} /></label>
        <label>Hasta <input type="date" value={fechas.hasta} max={hoy}
          min={fechas.desde || undefined}
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
        <GraficoMasVendidos filas={masVendidos} />
        <Tabla filas={masVendidos}
               columnas={['codigo', 'producto', 'unidades', 'ingresos', 'costo', 'margen', 'margen_pct']}
               resaltar={(f) => f.margen < 0} />
      </div>
      <div className="tarjeta">
        <h2>Existencias actuales y stock mínimo</h2>
        <GraficoStock filas={existencias} />
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

// ---------- Gráficos de barras (CSS puro, sin librerías) ----------

// Barras horizontales: unidades vendidas por producto (top 8).
// Verde = margen positivo, rojo = el producto se vende a pérdida.
function GraficoMasVendidos({ filas }) {
  const top = filas.filter((f) => f.unidades > 0).slice(0, 8)
  if (top.length === 0) return null
  const maximo = Math.max(...top.map((f) => f.unidades))
  return (
    <div className="grafico" aria-label="Gráfico de productos más vendidos">
      <p className="grafico-titulo">Unidades vendidas por producto</p>
      {top.map((f) => (
        <div className="grafico-fila" key={f.codigo}>
          <span className="grafico-etiqueta" title={f.producto}>{f.producto}</span>
          <div className="grafico-pista">
            <div className={`grafico-barra ${f.margen < 0 ? 'negativa' : ''}`}
                 style={{ width: `${(f.unidades / maximo) * 100}%` }} />
          </div>
          <span className="grafico-valor">
            {f.unidades} u. · {f.margen < 0 ? '-' : ''}${Math.abs(Number(f.margen)).toFixed(0)}
          </span>
        </div>
      ))}
      <p className="grafico-leyenda">
        <span className="muestra" /> margen positivo
        <span className="muestra negativa" /> margen negativo (pérdida)
      </p>
    </div>
  )
}

// Barras de stock libre por producto, con una marca en el stock mínimo.
// Se elige la sucursal porque cada una tiene su propio stock.
function GraficoStock({ filas }) {
  const sucursales = [...new Set(filas.map((f) => f.sucursal))]
  const [sucursal, setSucursal] = useState('')
  const elegida = sucursales.includes(sucursal) ? sucursal : sucursales[0]
  if (!elegida) return null
  const datos = filas.filter((f) => f.sucursal === elegida)
  const maximo = Math.max(1, ...datos.map((f) => Math.max(f.libre, f.stock_minimo)))
  return (
    <div className="grafico" aria-label="Gráfico de stock libre contra stock mínimo">
      <p className="grafico-titulo">
        Stock libre vs. mínimo en{' '}
        {sucursales.length > 1
          ? <select value={elegida} onChange={(e) => setSucursal(e.target.value)}>
              {sucursales.map((s) => <option key={s}>{s}</option>)}
            </select>
          : <b>{elegida}</b>}
      </p>
      {datos.map((f) => {
        const bajo = f.libre < f.stock_minimo
        return (
          <div className="grafico-fila" key={f.codigo}>
            <span className="grafico-etiqueta" title={f.producto}>{f.producto}</span>
            <div className="grafico-pista">
              <div className={`grafico-barra ${bajo ? 'negativa' : ''}`}
                   style={{ width: `${(f.libre / maximo) * 100}%` }} />
              <div className="grafico-minimo" style={{ left: `${(f.stock_minimo / maximo) * 100}%` }}
                   title={`Mínimo: ${f.stock_minimo}`} />
            </div>
            <span className="grafico-valor">{f.libre} / mín. {f.stock_minimo}</span>
          </div>
        )
      })}
      <p className="grafico-leyenda">
        <span className="muestra" /> stock libre suficiente
        <span className="muestra negativa" /> bajo el mínimo
        <span className="muestra-minimo" /> stock mínimo
      </p>
    </div>
  )
}
