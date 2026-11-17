import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'
import {
  Avisos, BarraFiltros, BotonIcono, Cargando, EtiquetaEstado, Vacio, nombreEstado,
  useConfirmacion, useListado,
} from '../components/UI.jsx'
import { formatearFecha, formatearFechaHora, hoyISO } from '../utils/fechas.js'
import CampoFecha from '../components/CampoFecha.jsx'

const ESTADOS_ORDEN = ['PENDIENTE', 'EN_PREPARACION', 'DESPACHADA', 'CERRADA']
const FILTROS = { numero: '', destino_id: '', estado_orden: '', desde: '', hasta: '' }

// Solicitudes de reposición que recibe el CD: listado compacto con filtros,
// paginación y el detalle (productos, preparación de bultos) a pedido.
export default function Logistica() {
  const listado = useListado(api.buscarOrdenes, FILTROS)
  const { filtros, setFiltros } = listado
  const [locales, setLocales] = useState([])
  const [abierta, setAbierta] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [dialogo, confirmar] = useConfirmacion()
  const hoy = hoyISO()

  useEffect(() => {
    api.sucursales().then((l) => setLocales(l.filter((s) => s.tipo === 'LOCAL'))).catch(() => {})
  }, [])

  // Ejecuta una acción, muestra el error de negocio del backend y refresca el listado
  const accion = async (fn, texto) => {
    setError('')
    setMensaje('')
    try {
      await fn()
      if (texto) setMensaje(texto)
      listado.recargar()
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }

  const resolver = async (orden, accionOrden) => {
    const verbo = accionOrden === 'RECHAZAR' ? 'Rechazar' : 'Cancelar'
    const motivo = await confirmar({
      titulo: `${verbo} la solicitud #${orden.id}`, pedirMotivo: true, peligro: true,
      mensaje: 'Los bultos preparados o precintados se anulan y se libera la reserva de stock.',
      textoAceptar: verbo,
    })
    if (motivo) accion(() => api.resolverOrden(orden.id, accionOrden, motivo),
      `Solicitud #${orden.id} ${accionOrden === 'RECHAZAR' ? 'rechazada' : 'cancelada'}.`)
  }

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>Solicitudes de reposición</h2>
          <p className="ayuda">Abrí el detalle de una solicitud para ver sus productos y preparar los bultos.</p>
        </div>
      </header>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />
      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label>N.º de solicitud
          <input inputMode="numeric" value={filtros.numero}
                 onChange={(e) => setFiltros({ ...filtros, numero: e.target.value.replace(/\D/g, '') })} /></label>
        <label>Local
          <select value={filtros.destino_id} onChange={(e) => setFiltros({ ...filtros, destino_id: e.target.value })}>
            <option value="">Todos</option>
            {locales.map((l) => <option key={l.id} value={l.id}>{l.nombre}</option>)}
          </select></label>
        <label>Estado
          <select value={filtros.estado_orden} onChange={(e) => setFiltros({ ...filtros, estado_orden: e.target.value })}>
            <option value="">Todos</option>
            {ESTADOS_ORDEN.map((e) => <option key={e} value={e}>{nombreEstado(e)}</option>)}
          </select></label>
        <label>Desde
          <CampoFecha value={filtros.desde} max={filtros.hasta || hoy}
                 onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} /></label>
        <label>Hasta
          <CampoFecha value={filtros.hasta} max={hoy} min={filtros.desde || undefined}
                 onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} /></label>
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio>No hay solicitudes para los filtros elegidos.</Vacio> : (
          <table className="tabla-compacta">
            <thead><tr><th>N.º</th><th>Local solicitante</th><th>Fecha</th>
              <th>Productos</th><th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((o) => {
              const resoluble = ['PENDIENTE', 'EN_PREPARACION'].includes(o.estado)
              return (
                <Fragment key={o.id}>
                  <tr>
                    <td><b>#{o.id}</b></td>
                    <td>{o.destino}<small className="codigo"> desde {o.origen}</small></td>
                    <td>{formatearFecha(o.fecha)}</td>
                    <td>{o.cantidad_productos} producto{o.cantidad_productos === 1 ? '' : 's'} · {o.unidades} u.</td>
                    <td><EtiquetaEstado estado={o.bultos?.some((b) => b.estado === 'PERDIDO')
                      ? 'PERDIDO' : o.estado} />
                      {o.resolucion && <small className="codigo"> {o.resolucion.toLowerCase()}</small>}</td>
                    <td className="acciones">
                      <BotonIcono icono={abierta === o.id ? 'ocultar' : 'ver'}
                                  etiqueta={abierta === o.id ? 'Cerrar detalle' : 'Ver detalle'}
                                  activo={abierta === o.id} onClick={() => setAbierta(abierta === o.id ? null : o.id)} />
                      {resoluble && <>
                        <BotonIcono icono="rechazar" etiqueta="Rechazar solicitud" tono="peligro"
                                    onClick={() => resolver(o, 'RECHAZAR')} />
                      </>}
                    </td>
                  </tr>
                  {abierta === o.id && (
                    <tr className="fila-detalle"><td colSpan="6">
                      <DetalleOrden orden={o} accion={accion} confirmar={confirmar} />
                    </td></tr>
                  )}
                </Fragment>
              )
            })}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>
      {dialogo}
    </section>
  )
}

function DetalleOrden({ orden, accion, confirmar }) {
  const pendientes = orden.items.filter((i) => Number(i.cantidad) > Number(i.empaquetado || 0))
  const puedeReintentar = orden.estado === 'CERRADA'
    && orden.remito_estado === 'RECHAZADO' && !orden.resolucion
  const permitePreparar = ['PENDIENTE', 'EN_PREPARACION'].includes(orden.estado) || puedeReintentar
  const [aEmpaquetar, setAEmpaquetar] = useState({})
  const [empaquetando, setEmpaquetando] = useState(false)
  const nombreProducto = (id) => orden.items.find((i) => i.producto_id === id)?.nombre ?? `#${id}`

  const armarBulto = async () => {
    const items = Object.entries(aEmpaquetar)
      .filter(([, c]) => Number(c) > 0)
      .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
    setEmpaquetando(true)
    const creado = await accion(() => api.crearBulto(orden.id, items), 'Bulto armado: el stock quedó reservado.')
    setEmpaquetando(false)
    if (creado) setAEmpaquetar({})
  }

  return (
    <div className="detalle">
      <dl className="detalle-datos">
        <div><dt>Origen</dt><dd>{orden.origen}</dd></div>
        <div><dt>Destino</dt><dd>{orden.destino}</dd></div>
        <div><dt>Fecha</dt><dd>{formatearFechaHora(orden.fecha)}</dd></div>
        {orden.fecha_vencimiento && <div><dt>Vence</dt><dd>{formatearFecha(orden.fecha_vencimiento)}</dd></div>}
        {orden.remito_numero && <div><dt>Remito</dt><dd>{orden.remito_numero} · {nombreEstado(orden.remito_estado)}</dd></div>}
        {orden.resolucion && <div><dt>Resolución</dt><dd>{orden.resolucion}: {orden.motivo_resolucion}</dd></div>}
      </dl>
      <table className="tabla-detalle">
        <thead><tr><th>Producto</th><th className="numero">Pedido</th><th className="numero">Empaquetado</th></tr></thead>
        <tbody>{orden.items.map((i) => (
          <tr key={i.producto_id}><td>{i.nombre}</td><td className="numero">{i.cantidad}</td>
            <td className="numero">{i.empaquetado}</td></tr>
        ))}</tbody>
      </table>

      {pendientes.length > 0 && permitePreparar
        && ((orden.remito_estado ?? 'ABIERTO') === 'ABIERTO' || puedeReintentar) && (
        <div className="armar">
          <div className="armar-cabecera"><strong>Preparar bulto</strong>
            <span>{pendientes.length} productos pendientes</span></div>
          <div className="armar-productos">
            {pendientes.map((i) => {
              const maximo = Number(i.cantidad) - Number(i.empaquetado || 0)
              return (
                <label className="producto-empaquetar" key={i.producto_id}>
                  <span>{i.nombre}</span><small>Pedido {i.cantidad} · pendiente {maximo}</small>
                  <input type="number" min="0" max={maximo} step="1"
                         aria-label={`Cantidad a empaquetar de ${i.nombre}`}
                         value={aEmpaquetar[i.producto_id] ?? ''}
                         onChange={(e) => setAEmpaquetar({ ...aEmpaquetar, [i.producto_id]: e.target.value })} />
                </label>
              )
            })}
          </div>
          <button disabled={empaquetando || !Object.values(aEmpaquetar).some((c) => Number(c) > 0)}
                  onClick={armarBulto}>{empaquetando ? 'Empaquetando…' : 'Empaquetar'}</button>
        </div>
      )}

      {orden.bultos.length > 0 && <h4>Bultos</h4>}
      {orden.bultos.map((b) => (
        <FilaBulto key={b.id} bulto={b} nombreProducto={nombreProducto} accion={accion} confirmar={confirmar} />
      ))}
    </div>
  )
}

function FilaBulto({ bulto, nombreProducto, accion, confirmar }) {
  const [historial, setHistorial] = useState(null)
  const conMotivo = async (titulo, fn, texto, peligro = true) => {
    const motivo = await confirmar({ titulo, pedirMotivo: true, peligro })
    if (motivo) accion(() => fn(motivo), texto)
  }
  return (
    <div className="bulto">
      <span><b>Bulto #{bulto.id}</b></span>
      <EtiquetaEstado estado={bulto.estado} />
      <span className="items">{bulto.items.map((i) => `${i.cantidad} × ${nombreProducto(i.producto_id)}`).join(', ')}</span>
      {bulto.precinto && <span>🔒 {bulto.precinto}</span>}
      {bulto.fecha_despacho && <span className="ayuda">Despachado {formatearFecha(bulto.fecha_despacho)}</span>}
      <span className="acciones">
        {bulto.estado === 'PREPARADO' && (
          <BotonIcono icono="precinto" etiqueta="Generar precinto"
                      onClick={() => accion(() => api.precintar(bulto.id), `Bulto #${bulto.id} precintado.`)} />
        )}
        {bulto.estado === 'PRECINTADO' && <>
          <BotonIcono icono="despachar" etiqueta="Despachar" tono="exito"
                      onClick={() => accion(() => api.despachar(bulto.id), `Bulto #${bulto.id} despachado.`)} />
          <BotonIcono icono="reabrir" etiqueta="Reabrir y cambiar precinto"
                      onClick={() => conMotivo(`Reabrir el bulto #${bulto.id}`,
                        (m) => api.reabrirBulto(bulto.id, m), 'Bulto reabierto.', false)} />
        </>}
        {['PREPARADO', 'PRECINTADO'].includes(bulto.estado) && (
          <BotonIcono icono="anular" etiqueta="Anular bulto" tono="peligro"
                      onClick={() => conMotivo(`Anular el bulto #${bulto.id}`,
                        (m) => api.anular(bulto.id, m), 'Bulto anulado: se liberó la reserva.')} />
        )}
        {bulto.estado === 'EN_TRANSITO' && (
          <BotonIcono icono="perdido" etiqueta="Declarar perdido" tono="peligro"
                      onClick={() => conMotivo(`Declarar perdido el bulto #${bulto.id}`,
                        (m) => api.marcarPerdido(bulto.id, m), 'Bulto declarado perdido.')} />
        )}
        <BotonIcono icono="historial" etiqueta={historial ? 'Ocultar historial' : 'Ver historial'}
                    activo={Boolean(historial)}
                    onClick={async () => setHistorial(historial ? null : await api.historial(bulto.id))} />
      </span>
      {historial && (
        <ol className="historial">
          {historial.map((h, i) => <li key={i}>{formatearFechaHora(h.fecha)} — <b>{nombreEstado(h.estado)}</b> {h.observacion}</li>)}
        </ol>
      )}
    </div>
  )
}
