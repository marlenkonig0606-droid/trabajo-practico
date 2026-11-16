// Componentes de interfaz compartidos por todas las pantallas:
// íconos con tooltip, modales, filtros, paginación, estados y confirmaciones.
import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

// ---------------------------------------------------------------------------
// Íconos (SVG de trazo, 24x24). Un único set para que todo se vea igual.
// ---------------------------------------------------------------------------
const TRAZOS = {
  editar: 'M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4',
  eliminar: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v6M14 11v6',
  buscar: 'M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4',
  ver: 'M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z',
  ocultar: 'M3 3l18 18M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3.2 4.2M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7c1.6 0 3-.4 4.3-1M9.9 9.9a3 3 0 0 0 4.2 4.2',
  agregar: 'M12 5v14M5 12h14',
  descargar: 'M12 4v11M7 10l5 5 5-5M5 20h14',
  encender: 'M12 3v8M6.4 6.4a8 8 0 1 0 11.2 0',
  devolucion: 'M9 14L4 9l5-5M4 9h11a5 5 0 0 1 0 10h-4',
  limpiar: 'M6 6l12 12M18 6L6 18',
  cerrar: 'M6 6l12 12M18 6L6 18',
  precinto: 'M7 11V8a5 5 0 0 1 10 0v3M5 11h14v10H5zM12 15v2',
  despachar: 'M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM17 19a2 2 0 1 0 0-4 2 2 0 0 0 0 4z',
  reabrir: 'M7 11V8a5 5 0 0 1 9.6-2M5 11h14v10H5z',
  anular: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM5.6 5.6l12.8 12.8',
  perdido: 'M12 3l10 18H2L12 3zM12 10v5M12 18h.01',
  historial: 'M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 3',
  recibir: 'M4 13l3 7h10l3-7M12 3v10M8 9l4 4 4-4',
  aprobar: 'M5 12l5 5L20 7',
  rechazar: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM9 9l6 6M15 9l-6 6',
  caja: 'M3 7l9-4 9 4v10l-9 4-9-4V7zM3 7l9 4 9-4M12 11v10',
  sugerir: 'M9 18h6M10 21h4M12 3a6 6 0 0 0-3.5 10.9V16h7v-2.1A6 6 0 0 0 12 3z',
  anterior: 'M15 6l-6 6 6 6',
  siguiente: 'M9 6l6 6-6 6',
  primera: 'M17 6l-6 6 6 6M7 6v12',
  ultima: 'M7 6l6 6-6 6M17 6v12',
  minimo: 'M4 19h16M4 15h7M4 11h11M4 7h4',
}

export function Icono({ nombre, tamano = 18 }) {
  return (
    <svg className="icono" viewBox="0 0 24 24" width={tamano} height={tamano}
         fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"
         strokeLinejoin="round" aria-hidden="true" focusable="false">
      <path d={TRAZOS[nombre] ?? TRAZOS.ver} />
    </svg>
  )
}

// Botón de solo ícono: SIEMPRE con aria-label (lectores de pantalla) y tooltip.
export function BotonIcono({ icono, etiqueta, onClick, tono = '', disabled = false,
  activo = false, type = 'button' }) {
  return (
    <button type={type} className={`boton-icono ${tono} ${activo ? 'activo' : ''}`}
            aria-label={etiqueta} data-tooltip={etiqueta} onClick={onClick}
            disabled={disabled}>
      <Icono nombre={icono} />
    </button>
  )
}

// Botón principal con ícono + texto ("+ Registrar venta", "+ Nuevo producto"…)
export function BotonPrincipal({ icono = 'agregar', children, onClick, disabled, type = 'button',
  tono = '' }) {
  return (
    <button type={type} className={`boton-principal ${tono}`} onClick={onClick} disabled={disabled}>
      <Icono nombre={icono} /> <span>{children}</span>
    </button>
  )
}

// ---------------------------------------------------------------------------
// Reporte en PDF: el botón genera el archivo y lo descarga directamente
// (utils/exportarPdf.js). "objetivo" es un ref al contenedor del reporte.
// ---------------------------------------------------------------------------
export function BotonDescargarPdf({ objetivo, nombreArchivo, disabled }) {
  const [generando, setGenerando] = useState(false)
  const [error, setError] = useState('')
  const descargar = async () => {
    if (!objetivo.current) return
    setGenerando(true)
    setError('')
    try {
      const { exportarPdf } = await import('../utils/exportarPdf.js')
      await exportarPdf(objetivo.current, nombreArchivo)
    } catch (e) {
      console.error(e)
      setError('No se pudo generar el PDF. Probá de nuevo.')
    } finally {
      setGenerando(false)
    }
  }
  return (
    <span className="boton-pdf-contenedor">
      <BotonPrincipal icono="descargar" tono={`boton-pdf ${generando ? 'generando' : ''}`}
                      onClick={descargar} disabled={disabled || generando}>
        {generando ? 'Generando PDF…' : 'Descargar PDF'}
      </BotonPrincipal>
      {error && <small className="error-pdf" role="alert">{error}</small>}
    </span>
  )
}

// Encabezado que SOLO aparece en el PDF.
export function EncabezadoImpresion({ titulo, subtitulo, usuario }) {
  const ahora = new Date()
  const dos = (n) => String(n).padStart(2, '0')
  const generado = `${dos(ahora.getDate())}/${dos(ahora.getMonth() + 1)}/${ahora.getFullYear()} `
    + `${dos(ahora.getHours())}:${dos(ahora.getMinutes())}`
  return (
    <div className="solo-impresion encabezado-impresion">
      <div>
        <strong>CD a Locales · {titulo}</strong>
        {subtitulo && <span>{subtitulo}</span>}
      </div>
      <div className="encabezado-impresion-meta">
        <span>Generado el {generado}</span>
        {usuario && <span>por {usuario.email}</span>}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Estado y acción contextual de habilitar/deshabilitar (una sola acción).
// ---------------------------------------------------------------------------
export function Estado({ activo, textos = ['Activo', 'Inactivo'] }) {
  return <span className={`insignia-estado ${activo ? 'si' : 'no'}`}>
    {activo ? textos[0] : textos[1]}</span>
}

export function AlternarEstado({ activo, onCambiar, disabled, verbos = ['Desactivar', 'Activar'] }) {
  const etiqueta = activo ? verbos[0] : verbos[1]
  return <BotonIcono icono="encender" etiqueta={etiqueta} tono={activo ? 'peligro' : 'exito'}
                     onClick={onCambiar} disabled={disabled} />
}

// Etiqueta de estado de negocio (órdenes, bultos, ventas…)
const NOMBRES_ESTADO = {
  PENDIENTE: 'Pendiente', EN_PREPARACION: 'En preparación', DESPACHADA: 'Despachada',
  CERRADA: 'Cerrada', PREPARADO: 'Preparado', PRECINTADO: 'Precintado',
  EN_TRANSITO: 'En tránsito', RECIBIDO: 'Recibido', VERIFICADO: 'Verificado',
  RECHAZADO: 'Rechazado', PERDIDO: 'Perdido', ANULADO: 'Anulado',
  COMPLETADA: 'Completada', DEVOLUCION_PARCIAL: 'Devolución parcial', DEVUELTA: 'Devuelta',
  ABIERTO: 'Abierto',
}
export const nombreEstado = (estado) => NOMBRES_ESTADO[estado] ?? estado
export function EtiquetaEstado({ estado }) {
  return <span className={`estado ${estado}`}>{nombreEstado(estado)}</span>
}

// ---------------------------------------------------------------------------
// Modal accesible: Escape o clic afuera para cerrar, foco al abrir.
// ---------------------------------------------------------------------------
export function Modal({ titulo, onCerrar, children, pie, ancho = 'normal' }) {
  const caja = useRef(null)
  useEffect(() => {
    const anterior = document.activeElement
    caja.current?.querySelector('input, select, textarea, button:not(.modal-cerrar)')?.focus()
    const tecla = (e) => { if (e.key === 'Escape') onCerrar() }
    document.addEventListener('keydown', tecla)
    document.body.classList.add('con-modal')
    return () => {
      document.removeEventListener('keydown', tecla)
      document.body.classList.remove('con-modal')
      anterior?.focus?.()
    }
  }, [])
  // Portal: el modal se dibuja directo en <body>, así ningún contenedor de la
  // página (con su propio contexto de apilamiento) puede quedar por encima.
  return createPortal(
    <div className="modal-fondo" onMouseDown={(e) => { if (e.target === e.currentTarget) onCerrar() }}>
      <div className={`modal ${ancho}`} role="dialog" aria-modal="true" aria-label={titulo} ref={caja}>
        <header className="modal-cabecera">
          <h2>{titulo}</h2>
          <button type="button" className="boton-icono modal-cerrar" aria-label="Cerrar"
                  data-tooltip="Cerrar" onClick={onCerrar}><Icono nombre="cerrar" /></button>
        </header>
        <div className="modal-cuerpo">{children}</div>
        {pie && <footer className="modal-pie">{pie}</footer>}
      </div>
    </div>,
    document.body,
  )
}

// Confirmación (y pedido de motivo) en un modal, en lugar de window.confirm/prompt.
// Uso: const [dialogo, confirmar] = useConfirmacion()
//      const motivo = await confirmar({ titulo, mensaje, pedirMotivo: true })
export function useConfirmacion() {
  const [pedido, setPedido] = useState(null)
  const confirmar = useCallback((opciones) => new Promise((resolver) => {
    setPedido({ ...opciones, resolver })
  }), [])
  const cerrar = (valor) => { pedido.resolver(valor); setPedido(null) }
  const dialogo = pedido ? <DialogoConfirmacion pedido={pedido} onCerrar={cerrar} /> : null
  return [dialogo, confirmar]
}

function DialogoConfirmacion({ pedido, onCerrar }) {
  const [motivo, setMotivo] = useState('')
  const listo = !pedido.pedirMotivo || motivo.trim()
  const aceptar = (e) => { e.preventDefault(); if (listo) onCerrar(pedido.pedirMotivo ? motivo.trim() : true) }
  return (
    <Modal titulo={pedido.titulo ?? 'Confirmar'} onCerrar={() => onCerrar(null)} ancho="chico">
      <form onSubmit={aceptar} className="formulario-modal">
        {pedido.mensaje && <p>{pedido.mensaje}</p>}
        {pedido.pedirMotivo && (
          <label>{pedido.etiquetaMotivo ?? 'Motivo'}
            <textarea rows="3" required value={motivo} onChange={(e) => setMotivo(e.target.value)} />
          </label>
        )}
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={() => onCerrar(null)}>Volver</button>
          <button type="submit" className={pedido.peligro ? 'peligro' : ''} disabled={!listo}>
            {pedido.textoAceptar ?? 'Confirmar'}</button>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Filtros y paginación
// ---------------------------------------------------------------------------
export function BarraFiltros({ children, onBuscar, onLimpiar, acciones, cargando }) {
  return (
    <form className="barra-filtros" onSubmit={(e) => { e.preventDefault(); onBuscar() }}>
      <div className="barra-filtros-campos">{children}</div>
      <div className="barra-filtros-botones">
        <button type="submit" className="boton-buscar" disabled={cargando}>
          <Icono nombre="buscar" /> <span>Buscar</span></button>
        <BotonIcono icono="limpiar" etiqueta="Limpiar filtros" tono="secundario" onClick={onLimpiar} />
        {acciones}
      </div>
    </form>
  )
}

export function Paginacion({ datos, onPagina, onPorPagina }) {
  if (!datos) return null
  const { pagina, paginas, total, por_pagina: porPagina } = datos
  const desde = total === 0 ? 0 : (pagina - 1) * porPagina + 1
  const hasta = Math.min(total, pagina * porPagina)
  return (
    <nav className="paginacion" aria-label="Paginación">
      <span className="paginacion-total">
        {total === 0 ? 'Sin resultados' : `${desde}–${hasta} de ${total} resultado${total === 1 ? '' : 's'}`}
      </span>
      <div className="paginacion-controles">
        <BotonIcono icono="primera" etiqueta="Primera página" disabled={pagina <= 1} onClick={() => onPagina(1)} />
        <BotonIcono icono="anterior" etiqueta="Página anterior" disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)} />
        <span className="paginacion-actual" aria-current="page">Página {pagina} de {paginas}</span>
        <BotonIcono icono="siguiente" etiqueta="Página siguiente" disabled={pagina >= paginas} onClick={() => onPagina(pagina + 1)} />
        <BotonIcono icono="ultima" etiqueta="Última página" disabled={pagina >= paginas} onClick={() => onPagina(paginas)} />
        {onPorPagina && (
          <label className="paginacion-tamano">Por página
            <select value={porPagina} onChange={(e) => onPorPagina(Number(e.target.value))}>
              {[5, 10, 20, 50].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </label>
        )}
      </div>
    </nav>
  )
}

// Maneja filtros + página de un listado del backend.
// - "filtros" es lo que el usuario está escribiendo; "aplicados" lo que se buscó.
// - Buscar o cambiar el tamaño vuelve a la página 1.
export function useListado(buscar, filtrosIniciales, dependencias = []) {
  const [filtros, setFiltros] = useState(filtrosIniciales)
  const [aplicados, setAplicados] = useState(filtrosIniciales)
  const [pagina, setPagina] = useState(1)
  const [porPagina, setPorPagina] = useState(10)
  const [datos, setDatos] = useState(null)
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)

  useEffect(() => {
    let activa = true
    setCargando(true)
    setError('')
    buscar({ ...aplicados, pagina, por_pagina: porPagina })
      .then((respuesta) => {
        if (!activa) return
        // Si la página quedó vacía (ej. después de un cambio), volver a la última válida
        if (respuesta.items.length === 0 && respuesta.pagina > 1 && respuesta.total > 0) {
          setPagina(respuesta.paginas)
        } else setDatos(respuesta)
      })
      .catch((e) => { if (activa) setError(e.message) })
      .finally(() => { if (activa) setCargando(false) })
    return () => { activa = false }
  }, [aplicados, pagina, porPagina, version, ...dependencias])

  return {
    filtros, setFiltros, datos, cargando, error,
    items: datos?.items ?? [],
    aplicar: () => { setPagina(1); setAplicados({ ...filtros }); setVersion((v) => v + 1) },
    limpiar: () => { setFiltros(filtrosIniciales); setAplicados(filtrosIniciales); setPagina(1); setVersion((v) => v + 1) },
    recargar: () => setVersion((v) => v + 1),
    irAPagina: setPagina,
    cambiarPorPagina: (n) => { setPorPagina(n); setPagina(1) },
    paginacion: (props = {}) => (
      <Paginacion datos={datos} onPagina={setPagina}
                  onPorPagina={(n) => { setPorPagina(n); setPagina(1) }} {...props} />
    ),
  }
}

// Mensajes de éxito/error que se cierran con un clic
export function Avisos({ error, mensaje, onCerrar }) {
  return <>
    {error && <div className="error" role="alert" onClick={onCerrar}>{error}</div>}
    {mensaje && <div className="exito" role="status" onClick={onCerrar}>{mensaje}</div>}
  </>
}

export function Cargando({ texto = 'Cargando…' }) {
  return <p className="cargando" role="status"><span className="spinner" aria-hidden="true" />{texto}</p>
}

export function Vacio({ children = 'No hay resultados para los filtros elegidos.' }) {
  return <p className="vacio-listado">{children}</p>
}
