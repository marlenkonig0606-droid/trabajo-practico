// Campo de fecha que SIEMPRE se ve y se escribe como DD/MM/AAAA, sin importar
// el idioma del navegador (el <input type="date"> nativo usa el del sistema y
// puede mostrar MM/DD/AAAA). Hacia afuera trabaja con 'AAAA-MM-DD' como antes:
// onChange recibe un evento con e.target.value en ese formato ('' si se borra).
// El botón del calendario abre el selector nativo del navegador.
import { useEffect, useRef, useState } from 'react'
import { formatearFecha } from '../utils/fechas.js'

const aTexto = (iso) => (iso ? formatearFecha(iso) : '')

function aISO(texto) {
  const m = texto.match(/^(\d{2})\/(\d{2})\/(\d{4})$/)
  if (!m) return null
  const [, dia, mes, anio] = m
  const fecha = new Date(Number(anio), Number(mes) - 1, Number(dia))
  const valida = fecha.getFullYear() === Number(anio) && fecha.getMonth() === Number(mes) - 1
    && fecha.getDate() === Number(dia)
  return valida ? `${anio}-${mes}-${dia}` : null
}

// Agrega las barras mientras se escribe: "16112026" → "16/11/2026".
function conBarras(texto) {
  const numeros = texto.replace(/\D/g, '').slice(0, 8)
  if (numeros.length <= 2) return numeros
  if (numeros.length <= 4) return `${numeros.slice(0, 2)}/${numeros.slice(2)}`
  return `${numeros.slice(0, 2)}/${numeros.slice(2, 4)}/${numeros.slice(4)}`
}

export default function CampoFecha({ value = '', onChange, min, max, id, disabled, ...resto }) {
  const [texto, setTexto] = useState(aTexto(value))
  const [error, setError] = useState('')
  const selector = useRef(null)
  useEffect(() => { setTexto(aTexto(value)); setError('') }, [value])

  const avisar = (iso) => onChange?.({ target: { value: iso } })
  const escribir = (e) => {
    const nuevo = conBarras(e.target.value)
    setTexto(nuevo)
    if (nuevo === '') { setError(''); avisar(''); return }
    if (nuevo.length < 10) return
    const iso = aISO(nuevo)
    if (!iso) { setError('Fecha inválida'); return }
    if ((min && iso < min) || (max && iso > max)) {
      setError(`Debe estar entre ${min ? formatearFecha(min) : '—'} y ${max ? formatearFecha(max) : '—'}`)
      return
    }
    setError('')
    avisar(iso)
  }
  const abrirCalendario = () => {
    const campo = selector.current
    if (!campo) return
    if (typeof campo.showPicker === 'function') {
      try { campo.showPicker(); return } catch { /* algunos navegadores no lo permiten */ }
    }
    campo.focus()
    campo.click()
  }
  return (
    <span className={`campo-fecha ${error ? 'con-error' : ''}`}>
      <input {...resto} id={id} type="text" inputMode="numeric" placeholder="dd/mm/aaaa"
             value={texto} onChange={escribir} disabled={disabled} maxLength={10}
             onBlur={() => { if (error || (texto && texto.length < 10)) { setTexto(aTexto(value)); setError('') } }}
             aria-invalid={Boolean(error)} title={error || 'Formato día/mes/año'} />
      <button type="button" className="campo-fecha-boton" onClick={abrirCalendario} disabled={disabled}
              aria-label="Abrir calendario" title="Abrir calendario">
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"
             strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M4 6h16v14H4zM4 10h16M8 3v4M16 3v4" /></svg>
      </button>
      <input ref={selector} type="date" className="campo-fecha-nativo" tabIndex={-1} aria-hidden="true"
             value={value} min={min} max={max} onChange={(e) => avisar(e.target.value)} />
      {error && <small className="campo-fecha-error" role="alert">{error}</small>}
    </span>
  )
}
