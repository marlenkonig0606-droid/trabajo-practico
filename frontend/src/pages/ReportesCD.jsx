import { useEffect, useMemo, useRef, useState } from 'react'
import { api } from '../api.js'
import {
  BarrasAgrupadas, BarrasHorizontales, BarrasResultado, COLORES, Dona, Leyenda, LineasMultiples,
  MapaCalor, PALETA, Podio, SinDatos, nombreMes, numero, pesos,
} from '../components/Graficos.jsx'
import {
  FiltroPeriodo, IndiceSecciones, Indicadores, Panel, Seccion, descripcionPeriodo,
  usePeriodoReporte,
} from '../components/Reporte.jsx'
import { BotonDescargarPdf, EncabezadoImpresion } from '../components/UI.jsx'
import Reportes from './Reportes.jsx'
import ReportesLocal from './ReportesLocal.jsx'

const SECCIONES = [
  ['resultado', 'Ganancia o pérdida'],
  ['locales', 'Ventas por local'],
  ['producto-local', 'Ventas por producto y local'],
  ['top', 'Top 10 productos'],
  ['pedidos', 'Pedidos de los locales'],
  ['estacionalidad', 'Estacionalidad'],
]
const PREFIJO = 'repcd'

// Pantalla "Reportes" del centro de distribución.
// Arriba se elige QUÉ ver:
//  - "red": el reporte del CD (toda la red de locales), GET /api/reportes/cd
//  - un local: la MISMA plantilla que ve el administrador de ese local
//  - "operativo": las tablas de control (movimientos, bultos, eventos…)
export default function ReportesCD({ usuario }) {
  const periodo = usePeriodoReporte()
  const [vista, setVista] = useState('red')
  const [locales, setLocales] = useState([])

  useEffect(() => {
    api.sucursales().then((lista) => setLocales(
      lista.filter((s) => s.tipo === 'LOCAL').sort((a, b) => a.nombre.localeCompare(b.nombre))))
  }, [])

  const selector = (
    <label className="vista-reporte">Ver reporte de
      <select value={vista} onChange={(e) => setVista(e.target.value)}>
        <option value="red">{usuario.sucursal} · todos los locales</option>
        {locales.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
        <option value="operativo">Detalle operativo (tablas)</option>
      </select>
    </label>
  )

  if (vista === 'operativo') {
    return (
      <>
        <div className="tarjeta reportes-filtros">{selector}</div>
        <Reportes usuario={usuario} />
      </>
    )
  }
  if (vista !== 'red') {
    const local = locales.find((l) => String(l.id) === String(vista))
    if (local) {
      return <ReportesLocal key={local.id} usuario={usuario} periodo={periodo}
                            sucursal={{ id: local.id, nombre: local.nombre }} selectorVista={selector} />
    }
  }
  return <ReporteRed usuario={usuario} periodo={periodo} selector={selector} />
}

function ReporteRed({ usuario, periodo, selector }) {
  const reporteRef = useRef(null)
  const [soloPropios, setSoloPropios] = useState(false)
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    let activa = true
    setCargando(true)
    setError('')
    api.reporteCd({ ...periodo.filtro, pedidos: soloPropios ? 'propios' : undefined })
      .then((d) => { if (activa) setDatos(d) })
      .catch((e) => { if (activa) setError(e.message) })
      .finally(() => { if (activa) setCargando(false) })
    return () => { activa = false }
  }, [periodo.clave, soloPropios])

  const descripcion = descripcionPeriodo(periodo, 'Todo el historial de la red.')
  return (
    <section className="reportes-local reportes-cd" ref={reporteRef}>
      <EncabezadoImpresion titulo={`Reporte del centro de distribución · ${usuario.sucursal}`}
                           subtitulo={`${descripcion} Ventas de todos los locales.`} usuario={usuario} />
      <div className="tarjeta reportes-cabecera">
        <div className="reportes-titulo">
          <div>
            <h2>Reportes · {usuario.sucursal}</h2>
            <p className="ayuda">{descripcion} Incluye las ventas de todos los locales activos.</p>
          </div>
          <BotonDescargarPdf objetivo={reporteRef} disabled={!datos || cargando}
                             nombreArchivo={`Reporte ${usuario.sucursal} ${periodo.sufijoArchivo}`} />
        </div>
        <div className="reportes-filtros">
          {selector}
          <FiltroPeriodo periodo={periodo} anios={datos?.anios_disponibles} />
        </div>
        <IndiceSecciones secciones={SECCIONES} prefijo={PREFIJO} />
      </div>

      {error && <div className="error" role="alert">{error}</div>}
      {!datos && cargando && <p className="vacio">Calculando reportes…</p>}
      {datos && (
        <div className={cargando ? 'reportes-actualizando' : ''}>
          <Resultado d={datos} />
          <VentasPorLocal d={datos} />
          <ProductoPorLocal d={datos} />
          <TopProductos d={datos} />
          <Pedidos d={datos} cd={usuario.sucursal} soloPropios={soloPropios}
                   onSoloPropios={setSoloPropios} />
          <Estacionalidad d={datos} />
        </div>
      )}
    </section>
  )
}

const conAnio = (d) => new Set(d.periodo.meses.map((m) => m.slice(0, 4))).size > 1
const colorLocal = (i) => PALETA[i % PALETA.length]

// ---------------------------------------------------------------------------
// 1. Ganancia o pérdida (arriba de todo)
// ---------------------------------------------------------------------------
function Resultado({ d }) {
  const r = d.resultado
  const ganancia = r.es_ganancia
  const meses = r.mensual.map((m) => ({
    etiqueta: nombreMes(m.mes, conAnio(d)), valor: m.resultado,
    detalle: `ingresos ${pesos(m.ingresos)} · costo ${pesos(m.costo)}`,
  }))
  const mesesEnPerdida = r.mensual.filter((m) => m.resultado < 0).length
  return (
    <Seccion prefijo={PREFIJO} id="resultado" numero="1" titulo="Ganancia o pérdida de la red"
             descripcion="Ventas netas de devoluciones menos el costo de la mercadería vendida y la mercadería perdida en tránsito.">
      <div className="resultado-red">
        <div className={`resultado-cifra ${ganancia ? 'ganancia' : 'perdida'}`}>
          <span>{ganancia ? 'Ganancia total' : 'Pérdida total'}</span>
          <strong>{ganancia ? '' : '-'}{pesos(Math.abs(r.resultado))}</strong>
          <small>
            {r.margen_pct == null ? 'Sin ventas en el período'
              : `Margen ${numero(r.margen_pct, 1)} % sobre las ventas netas`}
          </small>
        </div>
        <dl className="resultado-cuentas">
          <div><dt>Ventas</dt><dd>{pesos(r.ingresos_brutos)}</dd></div>
          <div><dt>− Devoluciones</dt><dd className="negativo">-{pesos(r.devoluciones)}</dd></div>
          <div><dt>= Ventas netas</dt><dd>{pesos(r.ingresos_netos)}</dd></div>
          <div><dt>− Costo de la mercadería vendida</dt><dd className="negativo">-{pesos(r.costo_vendido)}</dd></div>
          <div><dt>− Mercadería perdida en tránsito ({r.bultos_perdidos} bultos)</dt>
            <dd className="negativo">-{pesos(r.perdidas_transito)}</dd></div>
          <div className="total"><dt>{ganancia ? 'Ganancia' : 'Pérdida'}</dt>
            <dd className={ganancia ? '' : 'negativo'}>{ganancia ? '' : '-'}{pesos(Math.abs(r.resultado))}</dd></div>
        </dl>
      </div>
      <div className="paneles interno">
        <Panel titulo="Resultado mes a mes" ancho
               ayuda={mesesEnPerdida
                 ? `Verde: el mes dejó ganancia. Rojo: pérdida (${mesesEnPerdida} ${mesesEnPerdida === 1 ? 'mes' : 'meses'}).`
                 : 'Verde: el mes dejó ganancia. Si algún mes diera pérdida, se vería en rojo hacia abajo.'}>
          <BarrasResultado datos={meses} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 2. Ventas por local
// ---------------------------------------------------------------------------
function VentasPorLocal({ d }) {
  const filas = d.ventas_por_local
  const lider = filas[0]
  return (
    <Seccion prefijo={PREFIJO} id="locales" numero="2" titulo="Ventas por local"
             descripcion="Facturación neta (descontadas las devoluciones), tickets y ganancia de cada local.">
      <Indicadores items={filas.map((f) => ({
        titulo: f.local, tono: f === lider && f.facturado > 0 ? 'destacado' : '',
        valor: pesos(f.facturado),
        detalle: `${numero(f.ventas)} ventas · ticket ${f.ticket_promedio == null ? '—' : pesos(f.ticket_promedio)} · ganancia ${pesos(f.ganancia)}`,
      }))} />
      <div className="paneles">
        <Panel titulo="Participación en la facturación">
          <Dona formato={pesos}
                centro={{ valor: pesos(d.resultado.ingresos_netos), texto: 'ventas netas' }}
                datos={filas.map((f, i) => ({ etiqueta: f.local, valor: f.facturado, color: colorLocal(i) }))} />
        </Panel>
        <Panel titulo="Comparación de locales">
          <table className="tabla-reporte">
            <thead><tr><th>Local</th><th className="num">Ventas</th><th className="num">Unidades</th>
              <th className="num">Facturado</th><th className="num">Ganancia</th><th className="num">%</th></tr></thead>
            <tbody>{filas.map((f) => (
              <tr key={f.local}><td>{f.local}</td><td className="num">{numero(f.ventas)}</td>
                <td className="num">{numero(f.unidades)}</td><td className="num">{pesos(f.facturado)}</td>
                <td className="num">{pesos(f.ganancia)}</td><td className="num">{numero(f.participacion, 1)} %</td></tr>
            ))}</tbody>
          </table>
        </Panel>
        <Panel titulo="Facturación mensual por local" ancho>
          <BarrasAgrupadas formato={pesos}
                           categorias={d.periodo.meses.map((m) => nombreMes(m, conAnio(d)))}
                           series={filas.map((f, i) => ({
                             nombre: f.local, color: colorLocal(i),
                             valores: d.periodo.meses.map((m) => f.mensual.find((x) => x.mes === m)?.facturado ?? 0),
                           }))} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 3. Ventas por producto y local
// ---------------------------------------------------------------------------
function ProductoPorLocal({ d }) {
  const [medida, setMedida] = useState('unidades')
  const { por_local: productos, locales } = d.productos
  const formato = medida === 'unidades' ? (v) => `${numero(v)} u.` : pesos
  return (
    <Seccion prefijo={PREFIJO} id="producto-local" numero="3" titulo="Ventas por producto y local"
             descripcion="Qué vende cada local de cada producto (netas de devoluciones).">
      <div className="segmentado chico" role="tablist" aria-label="Medida">
        {[['unidades', 'Unidades'], ['ingresos', 'Facturación']].map(([id, texto]) => (
          <button key={id} role="tab" aria-selected={medida === id}
                  className={medida === id ? 'activo' : ''} onClick={() => setMedida(id)}>{texto}</button>
        ))}
      </div>
      <div className="paneles">
        <Panel titulo={`${medida === 'unidades' ? 'Unidades' : 'Facturación'} por producto en cada local`} ancho>
          <BarrasAgrupadas formato={formato} categorias={productos.map((p) => p.producto)}
                           series={locales.map((l, i) => ({
                             nombre: l, color: colorLocal(i),
                             valores: productos.map((p) => p.por_local.find((x) => x.local === l)?.[medida] ?? 0),
                           }))} />
        </Panel>
        <Panel titulo="Detalle" ancho>
          {productos.length === 0 ? <SinDatos /> : (
            <table className="tabla-reporte">
              <thead><tr><th>Producto</th>
                {locales.map((l) => <th key={l} className="num">{l}</th>)}
                <th className="num">Total</th></tr></thead>
              <tbody>{productos.map((p) => (
                <tr key={p.producto}><td>{p.producto}</td>
                  {locales.map((l) => {
                    const v = p.por_local.find((x) => x.local === l)
                    return <td key={l} className="num">{v ? formato(v[medida]) : '—'}</td>
                  })}
                  <td className="num"><strong>{formato(p[medida])}</strong></td></tr>
              ))}</tbody>
            </table>
          )}
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 4. Top 10 productos más vendidos
// ---------------------------------------------------------------------------
function TopProductos({ d }) {
  const top = d.productos.top
  return (
    <Seccion prefijo={PREFIJO} id="top" numero="4" titulo="Top 10 productos más vendidos"
             descripcion="Ranking de la red por unidades netas vendidas.">
      <div className="paneles">
        <Panel titulo="Podio">
          <Podio formato={(v) => `${numero(v)} u.`}
                 puestos={top.slice(0, 3).map((p) => ({ etiqueta: p.producto, valor: p.unidades }))} />
        </Panel>
        <Panel titulo="Ranking">
          <BarrasHorizontales formato={(v) => `${numero(v)} u.`}
                              datos={top.map((p, i) => ({
                                etiqueta: p.producto, valor: p.unidades,
                                color: i < 3 ? COLORES.amarillo : COLORES.principal,
                                detalle: `${pesos(p.ingresos)} · ganancia ${pesos(p.ganancia)}`,
                              }))} />
        </Panel>
      </div>
    </Seccion>
  )
}

// ---------------------------------------------------------------------------
// 5. Pedidos de reposición
// ---------------------------------------------------------------------------
function Pedidos({ d, cd, soloPropios, onSoloPropios }) {
  const p = d.pedidos
  return (
    <Seccion prefijo={PREFIJO} id="pedidos" numero="5" titulo="Pedidos de los locales"
             descripcion="Órdenes de reposición hechas en el período. Completo: el local recibió y verificó todo lo que pidió.">
      <div className="segmentado chico" role="tablist" aria-label="Pedidos de qué CD">
        <button role="tab" aria-selected={!soloPropios} className={!soloPropios ? 'activo' : ''}
                onClick={() => onSoloPropios(false)}>Todos los CD</button>
        <button role="tab" aria-selected={soloPropios} className={soloPropios ? 'activo' : ''}
                onClick={() => onSoloPropios(true)}>Solo {cd}</button>
      </div>
      <Indicadores items={[
        { titulo: 'Pedidos', valor: numero(p.total), detalle: soloPropios ? `atendidos por ${cd}` : 'de todos los CD' },
        { titulo: 'Completos', valor: numero(p.completos), tono: 'destacado' },
        { titulo: 'Incompletos', valor: numero(p.incompletos), tono: p.incompletos ? 'alerta' : '',
          detalle: p.unidades_faltantes ? `${numero(p.unidades_faltantes)} unidades no llegaron` : null },
        { titulo: 'En curso', valor: numero(p.en_curso), detalle: 'todavía no terminaron' },
        { titulo: 'Cumplimiento', valor: p.cumplimiento_pct == null ? '—' : `${numero(p.cumplimiento_pct, 1)} %`,
          tono: p.cumplimiento_pct != null && p.cumplimiento_pct < 90 ? 'aviso' : '',
          detalle: 'completos ÷ pedidos terminados' },
      ]} />
      <div className="paneles">
        <Panel titulo="Pedidos por local">
          <Dona centro={{ valor: numero(p.total), texto: 'pedidos' }}
                datos={p.por_local.map((f, i) => ({ etiqueta: f.local, valor: f.pedidos, color: colorLocal(i) }))} />
        </Panel>
        <Panel titulo="Completos vs. incompletos">
          <Dona centro={{ valor: p.cumplimiento_pct == null ? '—' : `${numero(p.cumplimiento_pct, 0)} %`, texto: 'completos' }}
                datos={[
                  { etiqueta: 'Completos', valor: p.completos, color: COLORES.exito },
                  { etiqueta: 'Incompletos', valor: p.incompletos, color: COLORES.alerta },
                  { etiqueta: 'En curso', valor: p.en_curso, color: COLORES.violeta },
                ].filter((x) => x.valor > 0)} />
        </Panel>
        <Panel titulo="Completos e incompletos por local">
          <CumplimientoPorLocal filas={p.por_local} />
          <Leyenda items={[
            { texto: 'Completos', color: COLORES.exito },
            { texto: 'Incompletos', color: COLORES.alerta },
            { texto: 'En curso', color: COLORES.violeta },
          ]} />
        </Panel>
        <Panel titulo="¿Por qué quedaron incompletos?"
               ayuda="Con faltantes: el local rechazó algún bulto o se perdió en el viaje.">
          {p.causas.length === 0 ? <SinDatos>Ningún pedido quedó incompleto en el período.</SinDatos> : (
            <BarrasHorizontales color={COLORES.alerta} formato={(v) => `${v} ${v === 1 ? 'pedido' : 'pedidos'}`}
                                datos={p.causas.map((c) => ({ etiqueta: c.causa, valor: c.pedidos }))} />
          )}
        </Panel>
      </div>
    </Seccion>
  )
}

// Una barra apilada por local: qué parte de sus pedidos llegó completa.
function CumplimientoPorLocal({ filas }) {
  const conPedidos = filas.filter((f) => f.pedidos > 0)
  if (!conPedidos.length) return <SinDatos />
  const partes = [['completos', COLORES.exito], ['incompletos', COLORES.alerta], ['en_curso', COLORES.violeta]]
  return (
    <div className="apiladas">
      {conPedidos.map((f) => (
        <div key={f.local} className="apilada-fila">
          <span className="apilada-etiqueta">{f.local}</span>
          <div className="apilada-barra">
            {partes.map(([clave, color]) => f[clave] > 0 && (
              <div key={clave} style={{ width: `${(f[clave] / f.pedidos) * 100}%`, background: color }}
                   title={`${f.local} · ${clave.replace('_', ' ')}: ${f[clave]} pedidos`}>
                {f[clave] / f.pedidos >= 0.08 ? f[clave] : ''}
              </div>
            ))}
          </div>
          <span className="apilada-valor">
            {f.cumplimiento_pct == null ? '—' : `${numero(f.cumplimiento_pct, 1)} %`}
          </span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// 6. Estacionalidad
// ---------------------------------------------------------------------------
function Estacionalidad({ d }) {
  const e = d.estacionalidad
  const columnas = e.meses.map((m) => nombreMes(m, conAnio(d)))
  const [elegidos, setElegidos] = useState(null)
  const visibles = useMemo(() => elegidos ?? e.productos.slice(0, 4).map((p) => p.producto),
    [elegidos, e.productos])
  const alternar = (nombre) => setElegidos(visibles.includes(nombre)
    ? visibles.filter((x) => x !== nombre) : [...visibles, nombre])
  return (
    <Seccion prefijo={PREFIJO} id="estacionalidad" numero="6" titulo="Estacionalidad de los productos"
             descripcion="Unidades vendidas por mes en toda la red: en qué meses se vende más cada producto.">
      <div className="paneles">
        <Panel titulo="Unidades por mes" ancho ayuda="Tocá un producto para mostrarlo u ocultarlo.">
          <div className="comparador">
            {e.productos.map((p) => (
              <label key={p.producto} className="vista-check">
                <input type="checkbox" checked={visibles.includes(p.producto)}
                       onChange={() => alternar(p.producto)} /> {p.producto}
              </label>
            ))}
          </div>
          <LineasMultiples categorias={columnas} formato={(v) => `${numero(v)} u.`}
                           series={e.productos.map((p, i) => ({ ...p, color: PALETA[i % PALETA.length] }))
                             .filter((p) => visibles.includes(p.producto))
                             .map((p) => ({ nombre: p.producto, color: p.color, valores: p.valores }))} />
        </Panel>
        <Panel titulo="Mapa de calor" ancho
               ayuda="Cada fila es un producto: más oscuro = mes con más ventas de ESE producto. El borde amarillo marca su mejor mes.">
          <MapaCalor columnas={columnas}
                     filas={e.productos.map((p) => ({ nombre: p.producto, valores: p.valores }))} />
        </Panel>
        <Panel titulo="Mejor y peor mes de cada producto" ancho>
          {e.productos.length === 0 ? <SinDatos /> : (
            <table className="tabla-reporte">
              <thead><tr><th>Producto</th><th className="num">Total</th><th className="num">Promedio por mes</th>
                <th>Mejor mes</th><th>Peor mes</th><th className="num">Pico vs. promedio</th></tr></thead>
              <tbody>{e.productos.map((p) => (
                <tr key={p.producto}><td>{p.producto}</td><td className="num">{numero(p.total)} u.</td>
                  <td className="num">{numero(p.promedio_mensual, 1)} u.</td>
                  <td>{p.mes_pico ? nombreMes(p.mes_pico) : '—'}</td>
                  <td>{p.mes_valle ? nombreMes(p.mes_valle) : '—'}</td>
                  <td className="num">{p.indice_pico == null ? '—' : `+${numero((p.indice_pico - 1) * 100, 0)} %`}</td></tr>
              ))}</tbody>
            </table>
          )}
        </Panel>
      </div>
    </Seccion>
  )
}
