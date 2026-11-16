// Piezas compartidas por los reportes del local y del centro de distribución:
// filtro de período, secciones numeradas, indicadores y paneles de gráficos.
import { useState } from 'react'

export function fechaLocalHoy() {
  const hoy = new Date()
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`
}

// Estado del filtro: año completo o período libre (desde / hasta).
export function usePeriodoReporte() {
  const anioActual = Number(fechaLocalHoy().slice(0, 4))
  const [modo, setModo] = useState('anio')
  const [anio, setAnio] = useState(anioActual)
  const [fechas, setFechas] = useState({ desde: '', hasta: '' })
  return {
    modo, setModo, anio, setAnio, fechas, setFechas, anioActual,
    filtro: modo === 'anio' ? { anio } : fechas,
    clave: modo === 'anio' ? `a${anio}` : `p${fechas.desde}_${fechas.hasta}`,
    sufijoArchivo: modo === 'anio' ? String(anio)
      : `${fechas.desde || 'inicio'} a ${fechas.hasta || fechaLocalHoy()}`,
  }
}

export function descripcionPeriodo({ modo, anio, fechas: { desde, hasta } }, todo = 'Todo el historial.') {
  if (modo === 'anio') return `Indicadores calculados con todas las operaciones de ${anio}.`
  const f = (x) => x.split('-').reverse().join('/')
  if (desde && hasta) return `Operaciones del ${f(desde)} al ${f(hasta)}.`
  if (desde) return `Operaciones desde el ${f(desde)}.`
  if (hasta) return `Operaciones hasta el ${f(hasta)}.`
  return todo
}

// primeraFecha: fecha del primer registro (la manda el backend). "Todo el
// historial" completa los selectores con esa fecha y la de hoy.
export function FiltroPeriodo({ periodo, anios, primeraFecha }) {
  const hoy = fechaLocalHoy()
  const { modo, setModo, anio, setAnio, fechas, setFechas } = periodo
  const lista = [...new Set([periodo.anioActual, ...(anios ?? [])])].sort((a, b) => b - a)
  const todoElHistorial = () => setFechas({ desde: primeraFecha ?? '', hasta: hoy })
  const elegirPeriodo = () => {
    setModo('periodo')
    if (!fechas.desde && !fechas.hasta) todoElHistorial()
  }
  return (
    <>
      <div className="segmentado" role="tablist" aria-label="Tipo de período">
        <button role="tab" aria-selected={modo === 'anio'} className={modo === 'anio' ? 'activo' : ''}
                onClick={() => setModo('anio')}>Año completo</button>
        <button role="tab" aria-selected={modo === 'periodo'} className={modo === 'periodo' ? 'activo' : ''}
                onClick={elegirPeriodo}>Período</button>
      </div>
      {modo === 'anio' ? (
        <label>Año
          <select value={anio} onChange={(e) => setAnio(Number(e.target.value))}>
            {lista.map((a) => <option key={a} value={a}>{a}</option>)}
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
          <button className="link" onClick={todoElHistorial}>Todo el historial</button>
        </div>
      )}
    </>
  )
}

export function IndiceSecciones({ secciones, prefijo = 'rep' }) {
  return (
    <nav className="reportes-indice" aria-label="Secciones del reporte">
      {secciones.map(([id, titulo], i) => (
        <a key={id} href={`#${prefijo}-${id}`}>{i + 1}. {titulo}</a>
      ))}
    </nav>
  )
}

export function Seccion({ id, numero: n, titulo, descripcion, children, prefijo = 'rep' }) {
  return (
    <section id={`${prefijo}-${id}`} className="tarjeta reporte-seccion">
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

export function Indicadores({ items }) {
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

export function Panel({ titulo, ayuda, children, ancho }) {
  return (
    <div className={`panel-grafico ${ancho ? 'ancho' : ''}`}>
      <h3>{titulo}</h3>
      {ayuda && <p className="ayuda">{ayuda}</p>}
      {children}
    </div>
  )
}
