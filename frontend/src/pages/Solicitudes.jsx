import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'
import SelectorProductos from '../components/SelectorProductos.jsx'
import {
  Avisos, BarraFiltros, BotonIcono, BotonPrincipal, Cargando, EtiquetaEstado, Modal, Vacio,
  nombreEstado, useConfirmacion, useListado,
} from '../components/UI.jsx'
import { formatearFecha, formatearFechaHora, hoyISO } from '../utils/fechas.js'
import CampoFecha from '../components/CampoFecha.jsx'

// Reposición del local: solicitudes al CD y recepción de los bultos que llegan.
export default function Solicitudes({ usuario }) {
  const [vista, setVista] = useState('solicitudes')
  const [modal, setModal] = useState(false)
  const [notificaciones, setNotificaciones] = useState([])
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [version, setVersion] = useState(0)     // fuerza recargar ambos listados

  useEffect(() => { api.notificaciones().then(setNotificaciones).catch(() => {}) }, [version])

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>Reposición · {usuario.sucursal}</h2>
          <p className="ayuda">Pedí mercadería al CD y confirmá y verificá los bultos que te envían.</p>
        </div>
        <BotonPrincipal onClick={() => { setMensaje(''); setModal(true) }}>Nueva solicitud</BotonPrincipal>
      </header>
      <Avisos error={error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />
      {notificaciones.filter((n) => !n.leida).slice(0, 3).map((n) => (
        <div className="aviso-info" key={n.id}>{formatearFecha(n.fecha)} · {n.mensaje}</div>
      ))}
      <div className="catalogo-tabs" role="tablist">
        <button role="tab" aria-selected={vista === 'solicitudes'} className={vista === 'solicitudes' ? 'activo' : ''}
                onClick={() => setVista('solicitudes')}>Solicitudes</button>
        <button role="tab" aria-selected={vista === 'recepciones'} className={vista === 'recepciones' ? 'activo' : ''}
                onClick={() => setVista('recepciones')}>Recepciones</button>
      </div>
      {vista === 'solicitudes'
        ? <ListadoSolicitudes key={`s${version}`} onMensaje={setMensaje} onError={setError} />
        : <ListadoRecepciones key={`r${version}`} onMensaje={setMensaje} onError={setError}
                              onCambio={() => setVersion((v) => v + 1)} />}
      {modal && (
        <ModalSolicitud usuario={usuario} onCerrar={() => setModal(false)}
                        onEnviada={(orden) => {
                          setModal(false)
                          setVista('solicitudes')
                          setVersion((v) => v + 1)
                          setMensaje(`Solicitud #${orden.id} enviada al centro de distribución.`)
                        }} />
      )}
    </section>
  )
}

function ListadoSolicitudes({ onMensaje, onError }) {
  const listado = useListado(api.buscarOrdenes, { numero: '', estado_orden: '', desde: '', hasta: '' })
  const { filtros, setFiltros } = listado
  const [abierta, setAbierta] = useState(null)
  const [dialogo, confirmar] = useConfirmacion()
  const hoy = hoyISO()

  const cancelar = async (orden) => {
    const motivo = await confirmar({ titulo: `Cancelar la solicitud #${orden.id}`, pedirMotivo: true,
      peligro: true, textoAceptar: 'Cancelar solicitud',
      mensaje: 'Si el CD ya preparó bultos, se anulan y se libera la reserva.' })
    if (!motivo) return
    try {
      await api.resolverOrden(orden.id, 'CANCELAR', motivo)
      onMensaje(`Solicitud #${orden.id} cancelada.`)
      listado.recargar()
    } catch (e) { onError(e.message) }
  }

  return (
    <>
      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label>N.º de solicitud
          <input inputMode="numeric" value={filtros.numero}
                 onChange={(e) => setFiltros({ ...filtros, numero: e.target.value.replace(/\D/g, '') })} /></label>
        <label>Estado
          <select value={filtros.estado_orden} onChange={(e) => setFiltros({ ...filtros, estado_orden: e.target.value })}>
            <option value="">Todos</option>
            {['PENDIENTE', 'EN_PREPARACION', 'DESPACHADA', 'CERRADA'].map((e) =>
              <option key={e} value={e}>{nombreEstado(e)}</option>)}
          </select></label>
        <label>Desde
          <CampoFecha value={filtros.desde} max={filtros.hasta || hoy}
                 onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} /></label>
        <label>Hasta
          <CampoFecha value={filtros.hasta} max={hoy} min={filtros.desde || undefined}
                 onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} /></label>
      </BarraFiltros>
      {listado.error && <div className="error">{listado.error}</div>}
      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio>Todavía no hay solicitudes con esos filtros.</Vacio> : (
          <table className="tabla-compacta">
            <thead><tr><th>N.º</th><th>Centro de distribución</th><th>Fecha</th><th>Productos</th>
              <th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((o) => (
              <Fragment key={o.id}>
                <tr>
                  <td><b>#{o.id}</b></td><td>{o.origen}</td><td>{formatearFecha(o.fecha)}</td>
                  <td>{o.cantidad_productos} producto{o.cantidad_productos === 1 ? '' : 's'} · {o.unidades} u.</td>
                  <td><EtiquetaEstado estado={o.estado} />
                    {o.resolucion && <small className="codigo"> {o.resolucion.toLowerCase()}</small>}</td>
                  <td className="acciones">
                    <BotonIcono icono={abierta === o.id ? 'ocultar' : 'ver'}
                                etiqueta={abierta === o.id ? 'Cerrar detalle' : 'Ver detalle'}
                                activo={abierta === o.id} onClick={() => setAbierta(abierta === o.id ? null : o.id)} />
                    {['PENDIENTE', 'EN_PREPARACION'].includes(o.estado) && (
                      <BotonIcono icono="anular" etiqueta="Cancelar solicitud" tono="peligro"
                                  onClick={() => cancelar(o)} />
                    )}
                  </td>
                </tr>
                {abierta === o.id && (
                  <tr className="fila-detalle"><td colSpan="6">
                    <div className="detalle">
                      <dl className="detalle-datos">
                        <div><dt>Fecha</dt><dd>{formatearFechaHora(o.fecha)}</dd></div>
                        {o.remito_numero && <div><dt>Remito</dt><dd>{o.remito_numero} · {nombreEstado(o.remito_estado)}</dd></div>}
                        {o.resolucion && <div><dt>Resolución</dt><dd>{o.resolucion}: {o.motivo_resolucion}</dd></div>}
                        <div><dt>Bultos</dt><dd>{o.bultos.length || 'Ninguno todavía'}</dd></div>
                      </dl>
                      <table className="tabla-detalle">
                        <thead><tr><th>Producto</th><th className="numero">Solicitado</th>
                          <th className="numero">Enviado</th></tr></thead>
                        <tbody>{o.items.map((i) => (
                          <tr key={i.producto_id}><td>{i.nombre}</td><td className="numero">{i.cantidad}</td>
                            <td className="numero">{i.empaquetado}</td></tr>
                        ))}</tbody>
                      </table>
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>
      {dialogo}
    </>
  )
}

function ListadoRecepciones({ onMensaje, onError, onCambio }) {
  const listado = useListado(api.buscarRecepciones, { numero: '', estado_bulto: '' })
  const { filtros, setFiltros } = listado
  const [abierto, setAbierto] = useState(null)
  const [ocupado, setOcupado] = useState(null)
  const [dialogo, confirmar] = useConfirmacion()

  const ejecutar = async (bulto, fn, texto) => {
    setOcupado(bulto.id)
    try {
      await fn()
      onMensaje(texto)
      onCambio()
    } catch (e) { onError(e.message) } finally { setOcupado(null) }
  }
  const rechazar = async (b) => {
    const motivo = await confirmar({ titulo: `Rechazar el bulto #${b.id}`, pedirMotivo: true, peligro: true,
      textoAceptar: 'Rechazar', mensaje: 'La mercadería vuelve al CD y no se suma a tu stock.' })
    if (motivo) ejecutar(b, () => api.verificarRecepcion(b.id, false, motivo),
      `Bulto #${b.id} rechazado: la mercadería vuelve al CD.`)
  }

  return (
    <>
      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label>N.º de bulto o solicitud
          <input inputMode="numeric" value={filtros.numero}
                 onChange={(e) => setFiltros({ ...filtros, numero: e.target.value.replace(/\D/g, '') })} /></label>
        <label>Estado
          <select value={filtros.estado_bulto} onChange={(e) => setFiltros({ ...filtros, estado_bulto: e.target.value })}>
            <option value="">Todos</option>
            {['EN_TRANSITO', 'RECIBIDO', 'VERIFICADO', 'RECHAZADO', 'PERDIDO'].map((e) =>
              <option key={e} value={e}>{nombreEstado(e)}</option>)}
          </select></label>
      </BarraFiltros>
      {listado.error && <div className="error">{listado.error}</div>}
      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio>No hay bultos enviados a tu local con esos filtros.</Vacio> : (
          <table className="tabla-compacta">
            <thead><tr><th>Bulto</th><th>Solicitud</th><th>Desde</th><th>Despachado</th>
              <th>Unidades</th><th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((b) => (
              <Fragment key={b.id}>
                <tr>
                  <td><b>#{b.id}</b></td><td>#{b.orden_id}</td><td>{b.origen}</td>
                  <td>{formatearFecha(b.fecha_despacho)}</td><td>{b.unidades} u.</td>
                  <td><EtiquetaEstado estado={b.estado} /></td>
                  <td className="acciones">
                    <BotonIcono icono={abierto === b.id ? 'ocultar' : 'ver'}
                                etiqueta={abierto === b.id ? 'Cerrar detalle' : 'Ver detalle'}
                                activo={abierto === b.id} onClick={() => setAbierto(abierto === b.id ? null : b.id)} />
                    {b.estado === 'EN_TRANSITO' && (
                      <BotonIcono icono="recibir" etiqueta="Confirmar recepción" tono="exito"
                                  disabled={ocupado === b.id}
                                  onClick={() => ejecutar(b, () => api.recibir(b.id),
                                    `Bulto #${b.id} recibido. Ahora verificá el precinto.`)} />
                    )}
                    {b.estado === 'RECIBIDO' && <>
                      <BotonIcono icono="aprobar" etiqueta="Verificar (precinto y mercadería correctos)"
                                  tono="exito" disabled={ocupado === b.id}
                                  onClick={() => ejecutar(b, () => api.verificarRecepcion(b.id, true),
                                    `Bulto #${b.id} verificado. El stock se suma al verificar todo el remito.`)} />
                      <BotonIcono icono="rechazar" etiqueta="Rechazar bulto" tono="peligro"
                                  disabled={ocupado === b.id} onClick={() => rechazar(b)} />
                    </>}
                  </td>
                </tr>
                {abierto === b.id && (
                  <tr className="fila-detalle"><td colSpan="7">
                    <div className="detalle">
                      <dl className="detalle-datos">
                        <div><dt>Precinto esperado</dt><dd>{b.precinto ?? '—'}</dd></div>
                        <div><dt>Remito</dt><dd>{b.remito_numero ?? '—'}</dd></div>
                        <div><dt>Despachado</dt><dd>{formatearFechaHora(b.fecha_despacho)}</dd></div>
                        <div><dt>Recibido</dt><dd>{formatearFechaHora(b.fecha_recepcion)}</dd></div>
                      </dl>
                      <table className="tabla-detalle">
                        <thead><tr><th>Producto</th><th className="numero">Cantidad</th></tr></thead>
                        <tbody>{b.items.map((i) => (
                          <tr key={i.producto_id}><td>{i.nombre}</td><td className="numero">{i.cantidad}</td></tr>
                        ))}</tbody>
                      </table>
                    </div>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>
      {dialogo}
    </>
  )
}

function ModalSolicitud({ usuario, onCerrar, onEnviada }) {
  const [productos, setProductos] = useState([])
  const [centros, setCentros] = useState([])
  const [origenId, setOrigenId] = useState('')
  const [cantidades, setCantidades] = useState({})
  const [error, setError] = useState('')
  const [aviso, setAviso] = useState('')
  const [enviando, setEnviando] = useState(false)

  useEffect(() => {
    Promise.all([api.productos(), api.sucursales()]).then(([p, s]) => {
      setProductos(p)
      const cds = s.filter((x) => x.tipo === 'CD')
      setCentros(cds)
      if (cds.length) setOrigenId(String(cds[0].id))
    }).catch((e) => setError(e.message))
  }, [])

  const items = Object.entries(cantidades).filter(([, c]) => Number(c) > 0)
    .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))

  const sugerir = async () => {
    setError('')
    try {
      const sugerencia = await api.sugerirOrden(usuario.sucursal_id)
      setCantidades(Object.fromEntries(sugerencia.map((i) => [i.producto_id, String(i.cantidad)])))
      setAviso(sugerencia.length ? `Se completaron ${sugerencia.length} productos según tu stock mínimo.`
        : 'Tu stock disponible ya alcanza los mínimos del local.')
    } catch (e) { setError(e.message) }
  }

  const enviar = async (e) => {
    e.preventDefault()
    if (!items.length || !origenId || enviando) return
    setEnviando(true)
    setError('')
    try {
      onEnviada(await api.solicitarOrden(Number(origenId), usuario.sucursal_id, items))
    } catch (err) { setError(err.message); setEnviando(false) }
  }

  return (
    <Modal titulo="Nueva solicitud de reposición" onCerrar={onCerrar} ancho="ancho">
      <form className="formulario-modal" onSubmit={enviar}>
        {error && <div className="error" role="alert">{error}</div>}
        {aviso && <div className="aviso-info">{aviso}</div>}
        <div className="grilla">
          <label>Centro de distribución de origen
            <select required value={origenId} onChange={(e) => setOrigenId(e.target.value)}>
              {centros.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select></label>
          <div className="destino-propio"><span>Destino</span><strong>{usuario.sucursal}</strong></div>
        </div>
        <SelectorProductos productos={productos} cantidades={cantidades} onChange={setCantidades} />
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={sugerir}>Sugerir según stock mínimo</button>
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!items.length || !origenId || enviando}>
            {enviando ? 'Enviando…' : 'Enviar solicitud'}</button>
        </div>
      </form>
    </Modal>
  )
}
