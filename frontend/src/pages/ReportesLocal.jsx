import { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import { formatearFecha, formatearFechaHora } from '../utils/fechas.js'
import {
  BarrasAgrupadas, BarrasHorizontales, BarrasVerticales, COLORES, Dispersion, Dona,
  CampanaGauss, Histograma, Leyenda, Linea, PALETA, Podio, SinDatos, StockVsMinimo,
  nombreMes, numero, pesos,
} from '../components/Graficos.jsx'

const SECCIONES = [
  ['resumen', 'Resumen general'],
  ['ventas', 'Análisis de ventas'],
  ['productos', 'Productos'],
  ['estadistica', 'Estadística'],
  ['stock', 'Stock'],
  ['devoluciones', 'Devoluciones y operaciones'],
  ['logistica', 'Logística y reposición'],
]
const NOMBRE_MEDIO = {
  EFECTIVO: 'Efectivo',
  TARJETA_DEBITO: 'Tarjeta de débito',
  TARJETA_CREDITO: 'Tarjeta de crédito',
  TRANSFERENCIA: 'Transferencia',
}

function fechaLocalHoy() {
  const hoy = new Date()
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`
}

// Reporte gerencial del local: todos los datos salen de GET /api/reportes/local.
export default function ReportesLocal({ usuario }) {
  const hoy = fechaLocalHoy()
  const anioActual = Number(hoy.slice(0, 4))
  const [modo, setModo] = useState('anio')
  const [anio, setAnio] = useState(anioActual)
  const [fechas, setFechas] = useState({ desde: '', hasta: '' })
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  // Se recalcula todo cada vez que cambia el filtro.
  useEffect(() => {
    let activa = true
    setCargando(true)
    setError('')
    const filtro = modo === 'anio' ? { anio } : fechas
    api.reporteLocal(filtro)
      .then((d) => { if (activa) setDatos(d) })
      .catch((e) => { if (activa) setError(e.message) })
      .finally(() => { if (activa) setCargando(false) })
    return () => { activa = false }
  }, [modo, anio, fechas.desde, fechas.hasta])

  const anios = useMemo(() => [...new Set([anioActual, ...(datos?.anios_disponibles ?? [])])]
    .sort((a, b) => b - a), [datos, anioActual])

  return (
    <section className="reportes-local">
      <div className="tarjeta reportes-cabecera">
        <div>
          <h2>Reportes · {usuario.sucursal}</h2>
          <p className="ayuda">{descripcionPeriodo(modo, anio, fechas)}</p>
        </div>
        <div className="reportes-filtros">
          <div className="segmentado" role="tablist" aria-label="Tipo de período">
            <button role="tab" aria-selected={modo === 'anio'} className={modo === 'anio' ? 'activo' : ''}
                    onClick={() => setModo('anio')}>Año completo</button>
            <button role="tab" aria-selected={modo === 'periodo'} className={modo === 'periodo' ? 'activo' : ''}
                    onClick={() => setModo('periodo')}>Período</button>
          </div>
          {modo === 'anio' ? (
            <label>Año
              <select value={anio} onChange={(e) => setAnio(Number(e.target.value))}>
                {anios.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </label>
          ) : (
            <div className="filtro-resumen">
              <label>Desde
                <input type="date" value={fechas.desde} max={fechas.hasta || hoy}
                       onChange={(e) => setFechas({ ...fechas, desde: e.target.value })} />
              </label>
              <label>Hasta
                <input type="date" value={fechas.hasta} max={hoy} min={fechas.desde || undefined}
                       onChange={(e) => setFechas({ ...fechas, hasta: e.target.value })} />
              </label>
              <button className="link" onClick={() => setFechas({ desde: '', hasta: '' })}>
                Todo el historial</button>
            </div>
          )}
        </div>
        <nav className="reportes-indice" aria-label="Secciones del reporte">
          {SECCIONES.map(([id, titulo], i) => (
            <a key={id} href={`#rep-${id}`}>{i + 1}. {titulo}</a>
          ))}
        </nav>
      </div>

      {error && <div className="error" role="alert">{error}</div>}
      {!datos && cargando && <p className="vacio">Calculando reportes…</p>}
      {datos && (
        <div className={cargando ? 'reportes-actualizando' : ''}>
          <ResumenGeneral d={datos} />
          <AnalisisVentas d={datos} />
          <AnalisisProductos d={datos} />
          <AnalisisEstadistico e={datos.estadistica} />
          <ReporteStock s={datos.stock} />
          <DevolucionesOperaciones d={datos} />
          <LogisticaReposicion d={datos} />
        </div>
      )}
    </section>
  )
}

function descripcionPeriodo(modo, anio, { desde, hasta }) {
  if (modo === 'anio') return `Indicadores calculados con todas las operaciones de ${anio}.`
  const f = (x) => x.split('-').reverse().join('/')
  if (desde && hasta) return `Operaciones del ${f(desde)} al ${f(hasta)}.`
  if (desde) return `Operaciones desde el ${f(desde)}.`
  if (hasta) return `Operaciones hasta el ${f(hasta)}.`
  return 'Todo el historial del local.'
}

function Seccion({ id, numero: n, titulo, descripcion, children }) {
  return (
    <section id={`rep-${id}`} className="tarjeta reporte-seccion">
      <header className="reporte-seccion-cabecera">
        <span className="reporte-numero">{n}</span>
        <div>
          <h2>{titulo}</h2>
          {descripcion && <p className="ayuda">{descripcion}</p>}
        </div>
      </header>
      {children}
    </section>
  )
}

function Indicadores({ items }) {
  return (
    <div className="kpis">
      {items.map((it) => (
        <div key={it.titulo} className={`kpi ${it.tono ?? ''}`}>
          <span>{it.titulo}</span>
          <strong>{it.valor}</strong>
          {it.detalle && <small>{it.detalle}</small>}
        </div>
      ))}
    </div>
  )
}

function Panel({ titulo, ayuda, children, ancho }) {
  return (
    <div className={`panel-grafico ${ancho ? 'ancho' : ''}`}>
      <h3>{titulo}</h3>
      {ayuda && <p className="ayuda">{ayuda}</p>}
      {children}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 1. Resumen general
// ---------------------------------------------------------------------------
function ResumenGeneral({ d }) {
  const r = d.resumen
  const conAnio = new Set(d.periodo.meses.map((m) => m.slice(0, 4))).size > 1
  const mensual = r.mensual.map((m) => ({ ...m, etiqueta: nombreMes(m.mes, conAnio) }))
  return (
    <Seccion id="resumen" numero="1" titulo="Resumen general de ventas"
             descripcion="Volumen comercial del local y su evolución mes a mes.">
      <Indicadores items={[
        { titulo: 'Ventas', valor: numero(r.ventas) },
        { titulo: 'Total facturado', valor: pesos(r.facturado) },
        { titulo: 'Ticket promedio', valor: r.ticket_promedio == null ? 'Sin ventas' : pesos(r.ticket_promedio),
          detalle: 'facturado ÷ ventas' },
        { titulo: 'Productos vendidos', valor: `${numero(r.unidades)} u.` },
        { titulo: 'Mes de mayor facturación', tono: 'destacado',
          valor: r.mes_mayor_facturacion ? nombreMes(r.mes_mayor_facturacion.mes) : '—',
          detalle: r.mes_mayor_facturacion ? pesos(r.mes_mayor_facturacion.facturado) : 'sin ventas' },
        { titulo: 'Mes con más ventas', tono: 'destacado',
          valor: r.mes_mayor_ventas ? nombreMes(r.mes_mayor_ventas.mes) : '—',
          detalle: r.mes_mayor_ventas ? `${r.mes_mayor_ventas.ventas} ventas` : 'sin ventas' },
      ]} />
      <div className="paneles">
        <Panel titulo="Facturación y cantidad de ventas por mes" ancho
               ayuda="Barras: facturación (verde el mes más alto, naranja el más bajo). Línea amarilla: cantidad de ventas.">
          <BarrasVerticales formato={pesos} formatoLinea={(v) => `${v} ventas`}
                            datos={mensual.map((m) => ({
                              etiqueta: m.etiqueta, valor: m.facturado, linea: m.ventas,
                              detalle: `${m.ventas} ventas`,
                            }))} />
          <Leyenda items={[
            { texto: 'Facturación', color: COLORES.principal },
            { texto: 'Mes más alto', color: COLORES.exito },
            { texto: 'Mes más bajo', color: COLORES.secundario },
            { texto: 'Cantidad de ventas (eje derecho)', color: COLORES.amarillo, linea: true },
          ]} />
        </Panel>
        <Panel titulo="Ticket promedio mensual" ancho
               ayuda="¿Los clientes gastan más o menos por compra según el mes? La línea punteada es el promedio de los meses. Los meses sin ventas no tienen ticket.">
          <Linea formato={pesos} datos={mensual.map((m) => ({
            etiqueta: m.etiqueta, valor: m.ticket_promedio,
          }))} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 2. Análisis de ventas
// ---------------------------------------------------------------------------
function AnalisisVentas({ d }) {
  const r = d.resumen
  const medios = d.medios_pago
  return (
    <Seccion id="ventas" numero="2" titulo="Análisis de ventas"
             descripcion="Cuánto ingresa por cada medio de pago en el período.">
      <Indicadores items={[
        { titulo: 'Operaciones', valor: numero(r.ventas) },
        { titulo: 'Total facturado', valor: pesos(r.facturado) },
        { titulo: 'Ticket promedio', valor: r.ticket_promedio == null ? 'Sin ventas' : pesos(r.ticket_promedio) },
      ]} />
      <div className="paneles">
        <Panel titulo="Ingresos por medio de pago">
          <Dona formato={pesos} centro={medios.length ? { valor: pesos(r.facturado), texto: 'facturado' } : null}
                datos={medios.map((m) => ({
                  etiqueta: NOMBRE_MEDIO[m.medio_pago] ?? m.medio_pago, valor: m.ingresos,
                }))} />
        </Panel>
        <Panel titulo="Operaciones y ticket por medio de pago">
          {medios.length === 0 ? <SinDatos /> : (
            <BarrasHorizontales formato={(v) => `${v} ventas`}
                                datos={medios.map((m, i) => ({
                                  etiqueta: NOMBRE_MEDIO[m.medio_pago] ?? m.medio_pago,
                                  valor: m.ventas, color: PALETA[i % PALETA.length],
                                  detalle: `ticket ${pesos(m.ingresos / m.ventas)} · ${numero(m.porcentaje, 1)} %`,
                                }))} />
          )}
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 3. Análisis de productos
// ---------------------------------------------------------------------------
function AnalisisProductos({ d }) {
  const ranking = d.productos.ranking
  const [verTodos, setVerTodos] = useState(false)
  const productos = useMemo(() => {
    const vistos = new Map()
    d.productos.por_mes.forEach((f) => vistos.set(f.producto_id, f.producto))
    return [...vistos].map(([id, nombre]) => ({ id, nombre }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre))
  }, [d])
  const [elegidos, setElegidos] = useState([])
  // Por defecto se comparan los dos más vendidos.
  useEffect(() => {
    const ids = productos.map((p) => p.id)
    if (elegidos.length && elegidos.every((id) => ids.includes(id))) return
    const top = ranking.slice(0, 2)
      .map((r) => productos.find((p) => p.nombre === r.producto)?.id).filter(Boolean)
    setElegidos(top.length ? top : ids.slice(0, 1))
  }, [productos])

  const conAnio = new Set(d.periodo.meses.map((m) => m.slice(0, 4))).size > 1
  const series = elegidos.filter(Boolean).map((id, i) => ({
    nombre: productos.find((p) => p.id === id)?.nombre ?? '',
    color: i === 0 ? COLORES.principal : COLORES.secundario,
    valores: d.periodo.meses.map((mes) => d.productos.por_mes
      .find((f) => f.producto_id === id && f.mes === mes)?.unidades ?? 0),
  }))
  const lista = verTodos ? ranking : ranking.slice(0, 10)

  return (
    <Seccion id="productos" numero="3" titulo="Análisis de productos"
             descripcion="Unidades netas vendidas (se descuentan las devoluciones del período).">
      <div className="paneles">
        <Panel titulo="Podio de los más vendidos">
          <Podio formato={(v) => `${numero(v)} u.`}
                 puestos={ranking.slice(0, 3).map((p) => ({ etiqueta: p.producto, valor: p.unidades }))} />
        </Panel>
        <Panel titulo="Ranking de productos">
          <BarrasHorizontales formato={(v) => `${numero(v)} u.`}
                              datos={lista.map((p) => ({ etiqueta: p.producto, valor: p.unidades,
                                detalle: pesos(p.ingresos) }))} />
          {ranking.length > 10 && (
            <button className="link" onClick={() => setVerTodos(!verTodos)}>
              {verTodos ? 'Ver solo los 10 primeros' : `Ver los ${ranking.length} productos`}
            </button>
          )}
        </Panel>
        <Panel titulo="Comparación mensual de productos" ancho
               ayuda="Elegí uno o dos productos para comparar las unidades vendidas en cada mes.">
          <div className="comparador">
            {[0, 1].map((i) => (
              <label key={i}>{i === 0 ? 'Producto' : 'Comparar con'}
                <select value={elegidos[i] ?? ''} onChange={(e) => {
                  const nuevos = [...elegidos]
                  nuevos[i] = e.target.value ? Number(e.target.value) : undefined
                  setElegidos(nuevos.filter((x, j) => j === 0 || x !== nuevos[0]))
                }}>
                  {i === 1 && <option value="">Ninguno</option>}
                  {productos.filter((p) => i === 0 || p.id !== elegidos[0]).map((p) => (
                    <option key={p.id} value={p.id}>{p.nombre}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <BarrasAgrupadas formato={(v) => `${v} u.`} series={series}
                           categorias={d.periodo.meses.map((m) => nombreMes(m, conAnio))} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 4. Análisis estadístico de tickets
// ---------------------------------------------------------------------------
function AnalisisEstadistico({ e }) {
  const [ejeX, setEjeX] = useState('fecha')
  if (!e.suficiente) {
    return (
      <Seccion id="estadistica" numero="4" titulo="Análisis estadístico de tickets">
        <SinDatos>{e.mensaje}</SinDatos>
      </Seccion>
    )
  }
  const puntos = e.puntos.map((p) => ({
    x: ejeX === 'fecha' ? new Date(p.fecha.replace(' ', 'T')).getTime() : p.unidades,
    y: p.total,
    atipico: p.atipico,
    titulo: `Venta #${p.id} · ${formatearFecha(p.fecha)} · ${pesos(p.total)} · ${p.unidades} u.`,
  }))
  return (
    <Seccion id="estadistica" numero="4" titulo="Análisis estadístico de tickets"
             descripcion="Cómo se distribuye el importe de cada venta. Atípicos: fuera de Q1 − 1,5·RIC y Q3 + 1,5·RIC (criterio de Tukey).">
      <Indicadores items={[
        { titulo: 'Ticket medio', valor: pesos(e.media) },
        { titulo: 'Mediana', valor: pesos(e.mediana), detalle: 'la mitad de las ventas está por debajo' },
        { titulo: 'Desvío estándar', valor: pesos(e.desvio),
          detalle: `coef. de variación ${numero(e.coef_variacion, 1)} %` },
        { titulo: 'Concentración (Q1 – Q3)', valor: `${pesos(e.q1)} – ${pesos(e.q3)}`,
          detalle: 'el 50 % central de los tickets' },
        { titulo: 'Tickets atípicos altos', valor: e.atipicos_altos, tono: e.atipicos_altos ? 'aviso' : '',
          detalle: `más de ${pesos(e.limite_atipico_alto)}` },
        { titulo: 'Tickets atípicos bajos', valor: e.atipicos_bajos,
          detalle: e.limite_atipico_bajo > 0 ? `menos de ${pesos(e.limite_atipico_bajo)}`
            : 'el límite inferior es negativo: no hay bajos posibles' },
      ]} />
      <div className={`diagnostico ${e.aproximacion_normal ? 'ok' : 'no'}`}>
        <b>{e.aproximacion_normal ? 'Distribución aproximadamente normal' : 'Distribución no normal'}</b>
        <span>{e.diagnostico}</span>
        <small>Asimetría {numero(e.asimetria, 2)} · curtosis (exceso) {numero(e.curtosis, 2)} ·
          {' '}{e.n} tickets · mínimo {pesos(e.minimo)} · máximo {pesos(e.maximo)}</small>
      </div>
      <div className="paneles">
        <Panel titulo="Distribución de los tickets · campana de Gauss" ancho
               ayuda={e.central
                 ? `Histograma de ${e.central.n} tickets (se dejan aparte los ${e.central.excluidos} atípicos, que estiran el eje y no dejan ver la forma). La curva amarilla es la normal con la misma media y desvío; las franjas violetas marcan μ ± 1σ y μ ± 2σ.`
                 : 'Histograma de los tickets del período.'}>
          {e.central ? <>
            <CampanaGauss clases={e.central.histograma} curva={e.central.curva_normal}
                          media={e.central.media} desvio={e.central.desvio} />
            <Leyenda items={[
              { texto: 'Ventas por rango de importe', color: COLORES.principal },
              { texto: 'Curva normal de referencia', color: COLORES.amarillo, linea: true },
              { texto: 'Media (μ)', color: COLORES.exito, linea: true },
              { texto: 'μ ± 1σ / ± 2σ', color: '#a78bfa' },
            ]} />
            <p className={`diagnostico-curva ${e.central.ajusta_normal ? 'ok' : 'no'}`}>
              {e.central.ajusta_normal
                ? `La campana ajusta bien a estos tickets (Jarque-Bera ${numero(e.central.jarque_bera, 2)} ≤ 5,99): se puede usar la media ± desvío para describirlos.`
                : `La campana es solo una referencia: los tickets no siguen exactamente una normal (Jarque-Bera ${numero(e.central.jarque_bera, 2)} > 5,99, asimetría ${numero(e.central.asimetria, 2)}). Por eso conviene mirar también la mediana y los cuartiles.`}
            </p>
          </> : (
            <Histograma clases={e.histograma} curva={e.curva_normal} media={e.media}
                        limiteAlto={e.limite_atipico_alto} />
          )}
        </Panel>
        <Panel titulo="Dispersión de los tickets">
          <div className="segmentado chico">
            <button className={ejeX === 'fecha' ? 'activo' : ''} onClick={() => setEjeX('fecha')}>
              Fecha vs. importe</button>
            <button className={ejeX === 'unidades' ? 'activo' : ''} onClick={() => setEjeX('unidades')}>
              Productos vs. importe</button>
          </div>
          <Dispersion puntos={puntos} esFecha={ejeX === 'fecha'} limiteAlto={e.limite_atipico_alto}
                      etiquetaX={ejeX === 'fecha' ? 'Fecha de la venta' : 'Productos en el ticket (unidades)'} />
          <Leyenda items={[
            { texto: 'Venta', color: COLORES.principal },
            { texto: 'Venta atípica', color: COLORES.secundario },
          ]} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 5. Stock
// ---------------------------------------------------------------------------
function ReporteStock({ s }) {
  const p = s.permanencia
  const bajos = s.existencias.filter((f) => f.estado === 'BAJO').length
  const cerca = s.existencias.filter((f) => f.estado === 'CERCA').length
  return (
    <Seccion id="stock" numero="5" titulo="Análisis de stock"
             descripcion="El stock libre y las alertas son el inventario a la fecha de hoy; la permanencia se reconstruye con los movimientos del período.">
      <Indicadores items={[
        { titulo: 'Bajo el mínimo', valor: bajos, tono: bajos ? 'alerta' : '' },
        { titulo: 'Cerca del mínimo', valor: cerca, tono: cerca ? 'aviso' : '',
          detalle: 'menos de 1,5 veces el mínimo' },
        { titulo: 'Alertas pendientes', valor: s.alertas.length },
      ]} />
      <div className="paneles">
        <Panel titulo="Stock libre vs. stock mínimo">
          <StockVsMinimo filas={s.existencias} />
          <Leyenda items={[
            { texto: 'Suficiente', color: COLORES.principal },
            { texto: 'Cerca del mínimo', color: COLORES.amarillo },
            { texto: 'Bajo el mínimo', color: COLORES.alerta },
            { texto: 'Stock mínimo', color: COLORES.secundario, linea: true },
          ]} />
        </Panel>
        <Panel titulo="Alertas de stock mínimo pendientes">
          {s.alertas.length === 0 ? <SinDatos>No hay alertas pendientes.</SinDatos> : (
            <table>
              <thead><tr><th>Producto</th><th>Disponible</th><th>Mínimo</th><th>Faltan</th></tr></thead>
              <tbody>{s.alertas.map((a) => (
                <tr key={a.producto} className="bajo"><td>{a.producto}</td><td>{a.libre}</td>
                  <td>{a.minimo}</td><td><b>{a.faltante}</b></td></tr>
              ))}</tbody>
            </table>
          )}
        </Panel>
        <Panel titulo="Tiempo de permanencia en stock" ancho
               ayuda={`Se reconstruye con el historial de movimientos${p.historial_desde ? ` (registrado desde el ${p.historial_desde ? formatearFecha(p.historial_desde) : ''})` : ''}: un período empieza cuando el producto ingresa con stock en cero y termina cuando se agota. El sistema no registra lotes, así que se mide el tiempo con stock disponible, no el de cada unidad.`}>
          {p.periodos.length === 0 ? (
            <SinDatos>No hay movimientos de stock suficientes para reconstruir la permanencia en este período.</SinDatos>
          ) : (
            <div className="paneles interno">
              <div>
                <h4>Mayor permanencia (días seguidos con stock)</h4>
                <BarrasHorizontales formato={(v) => `${numero(v, 1)} días`}
                                    datos={p.por_producto.slice(0, 8).map((f) => ({
                                      etiqueta: f.producto, valor: f.dias_maximos,
                                      detalle: `${f.periodos} período${f.periodos === 1 ? '' : 's'}`,
                                    }))} />
              </div>
              <div>
                <h4>Se agotan más rápido (promedio hasta agotarse)</h4>
                {p.se_agotan_rapido.length === 0
                  ? <SinDatos>Ningún producto se agotó en el período.</SinDatos>
                  : <BarrasHorizontales color={COLORES.secundario} formato={(v) => `${numero(v, 1)} días`}
                                        datos={p.se_agotan_rapido.slice(0, 8).map((f) => ({
                                          etiqueta: f.producto, valor: f.promedio_dias_hasta_agotar,
                                          detalle: `${f.agotamientos} vez${f.agotamientos === 1 ? '' : 'es'}`,
                                        }))} />}
              </div>
              <details className="detalle-periodos">
                <summary>Ver los períodos ({p.periodos.length})</summary>
                <table>
                  <thead><tr><th>Producto</th><th>Ingreso</th><th>Salida</th><th>Días</th></tr></thead>
                  <tbody>{p.periodos.slice(0, 50).map((f, i) => (
                    <tr key={i}><td>{f.producto}</td><td>{formatearFechaHora(f.ingreso)}</td>
                      <td>{f.sigue_en_stock ? 'Sigue en stock' : formatearFechaHora(f.salida)}</td><td>{numero(f.dias, 1)}</td></tr>
                  ))}</tbody>
                </table>
              </details>
            </div>
          )}
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 6. Devoluciones y operaciones
// ---------------------------------------------------------------------------
function DevolucionesOperaciones({ d }) {
  const dev = d.devoluciones
  const o = d.ordenes
  const rech = d.rechazos
  const conAnio = new Set(d.periodo.meses.map((m) => m.slice(0, 4))).size > 1
  const estados = [
    ['Pendientes', o.pendientes, COLORES.amarillo],
    ['En tránsito', o.en_transito, COLORES.principal],
    ['Entregadas', o.entregadas, COLORES.exito],
    ['Canceladas', o.canceladas, COLORES.texto],
    ['Rechazadas', o.rechazadas, COLORES.alerta],
    ['Vencidas', o.vencidas, COLORES.secundario],
  ].filter(([, v]) => v > 0)
  return (
    <Seccion id="devoluciones" numero="6" titulo="Devoluciones y operaciones">
      <div className="paneles">
        <Panel titulo="Devoluciones por producto"
               ayuda={`${numero(dev.unidades)} unidades devueltas por ${pesos(dev.importe)} en el período.`}>
          <BarrasHorizontales color={COLORES.alerta} formato={(v) => `${v} u.`}
                              datos={dev.por_producto.map((f) => ({
                                etiqueta: f.producto, valor: f.unidades,
                                detalle: `${f.devoluciones} devoluc. · ${pesos(f.importe)}`,
                              }))} />
        </Panel>
        <Panel titulo="Estado de mis órdenes"
               ayuda={`${o.total} órdenes pedidas en el período. Tiempo de tránsito: desde el despacho del CD hasta la recepción en el local.`}>
          <Indicadores items={[
            { titulo: 'Tránsito promedio', valor: o.transito_horas_promedio == null ? 'Sin datos'
              : `${numero(o.transito_horas_promedio, 1)} h`,
              detalle: o.transito_horas_promedio == null ? 'no se recibieron bultos'
                : `≈ ${numero(o.transito_horas_promedio / 24, 1)} días · ${o.bultos_medidos} bultos` },
          ]} />
          <Dona formato={(v) => `${v} orden${v === 1 ? '' : 'es'}`}
                datos={estados.map(([etiqueta, valor, color]) => ({ etiqueta, valor, color }))} />
        </Panel>
        <Panel titulo="Bultos rechazados" ancho
               ayuda="Bultos que el local rechazó al verificarlos (por la fecha del rechazo).">
          <Indicadores items={[
            { titulo: 'Bultos rechazados', valor: rech.cantidad, tono: rech.cantidad ? 'alerta' : '' },
            { titulo: 'Unidades rechazadas', valor: numero(rech.unidades) },
          ]} />
          {rech.cantidad === 0 ? <SinDatos>No hubo rechazos en el período.</SinDatos> : (
            <div className="paneles interno">
              <div><h4>Por producto</h4>
                <BarrasHorizontales color={COLORES.alerta} formato={(v) => `${v} u.`}
                                    datos={rech.por_producto.map((f) => ({
                                      etiqueta: f.producto, valor: f.unidades,
                                      detalle: `${f.bultos} bulto${f.bultos === 1 ? '' : 's'}` }))} /></div>
              <div><h4>Por centro de distribución</h4>
                <Dona formato={(v) => `${v} bulto${v === 1 ? '' : 's'}`}
                      datos={rech.por_cd.map((f) => ({ etiqueta: f.cd, valor: f.bultos }))} /></div>
              <div className="ancho"><h4>Evolución de los rechazos</h4>
                <BarrasVerticales color={COLORES.alerta} destacarExtremos={false} alto={180}
                                  formato={(v) => `${v} bulto${v === 1 ? '' : 's'}`}
                                  datos={rech.por_mes.map((m) => ({ etiqueta: nombreMes(m.mes, conAnio), valor: m.bultos }))} /></div>
            </div>
          )}
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 7. Logística y reposición
// ---------------------------------------------------------------------------
function LogisticaReposicion({ d }) {
  const l = d.logistica
  const conAnio = new Set(d.periodo.meses.map((m) => m.slice(0, 4))).size > 1
  const vendidas = d.resumen.unidades
  return (
    <Seccion id="logistica" numero="7" titulo="Logística y reposición"
             descripcion="Pedidos y bultos solicitados por el local (por la fecha del pedido; los bultos anulados no se cuentan).">
      <Indicadores items={[
        { titulo: 'Pedidos de reposición', valor: l.pedidos },
        { titulo: 'Bultos solicitados', valor: l.bultos, detalle: `${numero(l.unidades)} unidades` },
        { titulo: 'Ventas por cada bulto', tono: 'destacado',
          valor: l.ventas_por_bulto == null ? 'No disponible' : numero(l.ventas_por_bulto, 1),
          detalle: l.ventas_por_bulto == null ? 'no hubo bultos en el período'
            : `1 bulto cada ${numero(l.ventas_por_bulto, 1)} ventas (${l.ventas} ÷ ${l.bultos})` },
        { titulo: 'Reposición vs. demanda',
          valor: vendidas ? `${numero((l.unidades / vendidas) * 100, 0)} %` : 'No disponible',
          detalle: vendidas ? `${numero(l.unidades)} u. pedidas / ${numero(vendidas)} u. vendidas` : 'sin ventas' },
      ]} />
      <div className="paneles">
        <Panel titulo="Bultos por centro de distribución">
          <Dona formato={(v) => `${v} bulto${v === 1 ? '' : 's'}`}
                centro={l.bultos ? { valor: l.bultos, texto: 'bultos' } : null}
                datos={l.por_cd.filter((f) => f.bultos).map((f) => ({ etiqueta: f.cd, valor: f.bultos }))} />
        </Panel>
        <Panel titulo="Detalle por centro de distribución">
          {l.por_cd.length === 0 ? <SinDatos>No hubo pedidos en el período.</SinDatos> : (
            <table>
              <thead><tr><th>Centro</th><th>Pedidos</th><th>Bultos</th><th>Unidades</th><th>% bultos</th></tr></thead>
              <tbody>{l.por_cd.map((f) => (
                <tr key={f.cd}><td>{f.cd}</td><td>{f.pedidos}</td><td>{f.bultos}</td>
                  <td>{numero(f.unidades)}</td><td>{numero(f.porcentaje_bultos, 1)} %</td></tr>
              ))}</tbody>
            </table>
          )}
        </Panel>
        <Panel titulo="Bultos solicitados vs. ventas por mes" ancho
               ayuda="Barras: ventas del mes. Línea: bultos pedidos (eje derecho). Permite ver si la reposición acompaña la demanda.">
          <BarrasVerticales destacarExtremos={false} formato={(v) => `${v} ventas`}
                            formatoLinea={(v) => `${v} bultos`}
                            datos={l.mensual.map((m) => ({
                              etiqueta: nombreMes(m.mes, conAnio), valor: m.ventas, linea: m.bultos,
                              detalle: `${m.pedidos} pedidos`,
                            }))} />
          <Leyenda items={[
            { texto: 'Ventas', color: COLORES.principal },
            { texto: 'Bultos solicitados (eje derecho)', color: COLORES.amarillo, linea: true },
          ]} />
        </Panel>
      </div>
    </Seccion>
  )
}
