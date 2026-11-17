import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'
import SelectorProductos from '../components/SelectorProductos.jsx'
import {
  Avisos, BarraFiltros, BotonIcono, BotonPrincipal, Cargando, EtiquetaEstado, Modal, Vacio,
  useListado,
} from '../components/UI.jsx'
import { formatearFecha, formatearFechaHora, hoyISO, pesos } from '../utils/fechas.js'
import CampoFecha from '../components/CampoFecha.jsx'
import { festejarVenta, lamentarDevolucion } from '../utils/efectos.js'

export const MEDIOS_PAGO = [
  ['EFECTIVO', 'Efectivo'],
  ['TARJETA_DEBITO', 'Tarjeta de débito'],
  ['TARJETA_CREDITO', 'Tarjeta de crédito'],
  ['TRANSFERENCIA', 'Transferencia'],
]
const nombreMedio = (m) => MEDIOS_PAGO.find(([v]) => v === m)?.[1] ?? m
const FILTROS = { desde: '', hasta: '', numero: '', medio_pago: '', producto: '' }

export default function Ventas({ usuario }) {
  const listado = useListado(api.buscarVentas, FILTROS)
  const { filtros, setFiltros } = listado
  const [modal, setModal] = useState(null)          // 'venta' | { devolucion: venta }
  const [abierta, setAbierta] = useState(null)      // id de la venta con el detalle abierto
  const [detalles, setDetalles] = useState({})
  const [nueva, setNueva] = useState(null)          // id recién creado (se resalta)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const hoy = hoyISO()

  const cargarDetalle = async (id) => {
    const venta = await api.venta(id)
    setDetalles((d) => ({ ...d, [id]: venta }))
    return venta
  }

  const alternarDetalle = async (id) => {
    if (abierta === id) { setAbierta(null); return }
    setAbierta(id)
    if (!detalles[id]) await cargarDetalle(id).catch((e) => setError(e.message))
  }

  const ventaRegistrada = (venta) => {
    setModal(null)
    setNueva(venta.id)
    festejarVenta()
    setMensaje(`Venta n.º ${venta.id} registrada por ${pesos(venta.total)}. Comprobante ${venta.comprobante_numero}.`)
    // Se limpian los filtros para que la venta nueva aparezca primera en el listado.
    listado.limpiar()
  }

  const devolucionRegistrada = async (venta, devolucion) => {
    setModal(null)
    lamentarDevolucion()
    setMensaje(`Devolución registrada en la venta n.º ${venta.id}: reintegro de ${pesos(devolucion.total ?? devolucion.reintegro)}. El stock se actualizó.`)
    listado.recargar()
    await cargarDetalle(venta.id).catch(() => {})
  }

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>Ventas · {usuario.sucursal}</h2>
          <p className="ayuda">Buscá ventas, abrí su detalle o registrá devoluciones.</p>
        </div>
        <BotonPrincipal onClick={() => { setMensaje(''); setModal('venta') }}>Registrar venta</BotonPrincipal>
      </header>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />

      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label>Desde
          <CampoFecha value={filtros.desde} max={filtros.hasta || hoy}
                 onChange={(e) => setFiltros({ ...filtros, desde: e.target.value })} /></label>
        <label>Hasta
          <CampoFecha value={filtros.hasta} max={hoy} min={filtros.desde || undefined}
                 onChange={(e) => setFiltros({ ...filtros, hasta: e.target.value })} /></label>
        <label>N.º de venta o comprobante
          <input inputMode="numeric" value={filtros.numero} placeholder="Ej.: 125"
                 onChange={(e) => setFiltros({ ...filtros, numero: e.target.value.replace(/\D/g, '') })} /></label>
        <label>Medio de pago
          <select value={filtros.medio_pago} onChange={(e) => setFiltros({ ...filtros, medio_pago: e.target.value })}>
            <option value="">Todos</option>
            {MEDIOS_PAGO.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select></label>
        <label>Producto
          <input value={filtros.producto} placeholder="Parte del nombre"
                 onChange={(e) => setFiltros({ ...filtros, producto: e.target.value })} /></label>
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando texto="Buscando ventas…" /> :
          listado.items.length === 0 ? <Vacio>No hay ventas para los filtros elegidos.</Vacio> : (
          <table className="tabla-compacta">
            <thead><tr><th>N.º</th><th>Fecha</th><th>Productos</th><th>Medio de pago</th>
              <th className="numero">Total</th><th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>
              {listado.items.map((v) => (
                <Fragment key={v.id}>
                  <tr className={v.id === nueva ? 'resaltada' : ''}>
                    <td><b>#{v.id}</b></td>
                    <td>{formatearFecha(v.fecha)}</td>
                    <td>{v.productos} producto{v.productos === 1 ? '' : 's'} · {v.unidades} u.</td>
                    <td>{nombreMedio(v.medio_pago)}</td>
                    <td className="numero">{pesos(v.total)}</td>
                    <td><EtiquetaEstado estado={v.estado} /></td>
                    <td className="acciones">
                      <BotonIcono icono={abierta === v.id ? 'ocultar' : 'ver'}
                                  etiqueta={abierta === v.id ? 'Cerrar detalle' : 'Abrir detalle'}
                                  activo={abierta === v.id} onClick={() => alternarDetalle(v.id)} />
                      <BotonIcono icono="devolucion" etiqueta="Registrar devolución"
                                  disabled={v.estado === 'DEVUELTA'}
                                  onClick={async () => {
                                    const venta = detalles[v.id] ?? await cargarDetalle(v.id)
                                    setModal({ devolucion: venta })
                                  }} />
                    </td>
                  </tr>
                  {abierta === v.id && (
                    <tr className="fila-detalle"><td colSpan="7">
                      {detalles[v.id] ? <DetalleVenta venta={detalles[v.id]} /> : <Cargando />}
                    </td></tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>

      {modal === 'venta' && (
        <ModalVenta usuario={usuario} onCerrar={() => setModal(null)} onRegistrada={ventaRegistrada} />
      )}
      {modal?.devolucion && (
        <ModalDevolucion venta={modal.devolucion} onCerrar={() => setModal(null)}
                         onRegistrada={(d) => devolucionRegistrada(modal.devolucion, d)} />
      )}
    </section>
  )
}

function DetalleVenta({ venta }) {
  return (
    <div className="detalle">
      <dl className="detalle-datos">
        <div><dt>Fecha y hora</dt><dd>{formatearFechaHora(venta.fecha)}</dd></div>
        <div><dt>Comprobante</dt><dd>{venta.comprobante_numero}</dd></div>
        <div><dt>Medio de pago</dt><dd>{nombreMedio(venta.medio_pago)}
          {venta.cuotas > 1 ? ` · ${venta.cuotas} cuotas` : ''}</dd></div>
        {venta.referencia && <div><dt>Referencia</dt><dd>{venta.referencia}</dd></div>}
        <div><dt>Subtotal</dt><dd>{pesos(venta.subtotal)}</dd></div>
        <div><dt>Total cobrado</dt><dd><b>{pesos(venta.total)}</b></dd></div>
      </dl>
      <table className="tabla-detalle">
        <thead><tr><th>Producto</th><th className="numero">Cantidad</th>
          <th className="numero">Precio unitario</th><th className="numero">Subtotal</th>
          <th className="numero">Devuelto</th></tr></thead>
        <tbody>{venta.items.map((i) => (
          <tr key={i.producto_id}><td>{i.nombre}</td><td className="numero">{i.cantidad}</td>
            <td className="numero">{pesos(i.precio_unitario)}</td>
            <td className="numero">{pesos(i.cantidad * i.precio_unitario)}</td>
            <td className="numero">{i.devuelto || '—'}</td></tr>
        ))}</tbody>
      </table>
      {venta.devoluciones.length > 0 && (
        <div className="detalle-devoluciones">
          <h4>Devoluciones</h4>
          <ul>{venta.devoluciones.map((d, i) => (
            <li key={i}>{formatearFecha(d.fecha)} · {d.cantidad} × {d.nombre} · {d.motivo}</li>
          ))}</ul>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Modal: registrar venta (reutiliza el selector de productos y las validaciones
// del backend; el botón se bloquea mientras guarda para evitar duplicados).
// ---------------------------------------------------------------------------
function ModalVenta({ usuario, onCerrar, onRegistrada }) {
  const [productos, setProductos] = useState([])
  const [medioPago, setMedioPago] = useState('EFECTIVO')
  const [cuotas, setCuotas] = useState('1')
  const [cantidades, setCantidades] = useState({})
  const [referencia, setReferencia] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  useEffect(() => { api.productos().then(setProductos).catch((e) => setError(e.message)) }, [])

  const items = Object.entries(cantidades)
    .filter(([, c]) => Number(c) > 0)
    .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
  const subtotal = items.reduce((s, i) =>
    s + i.cantidad * Number(productos.find((p) => p.id === i.producto_id)?.precio_venta ?? 0), 0)
  // Misma regla que el backend (Factory Method de medios de pago): solo como vista previa.
  const total = medioPago === 'EFECTIVO' ? subtotal * 0.9
    : medioPago === 'TARJETA_CREDITO' ? subtotal * (1 + 0.05 * Number(cuotas || 1)) : subtotal
  const cuotasValidas = medioPago !== 'TARJETA_CREDITO'
    || (Number.isInteger(Number(cuotas)) && Number(cuotas) >= 1)
  const valida = items.length > 0 && cuotasValidas
    && items.every((i) => Number.isInteger(i.cantidad))

  const guardar = async (e) => {
    e.preventDefault()
    if (!valida || guardando) return
    setGuardando(true)
    setError('')
    try {
      const venta = await api.registrarVenta({
        sucursal_id: usuario.sucursal_id,
        items,
        medio_pago: medioPago,
        ...(medioPago === 'TARJETA_CREDITO' ? { cuotas: Number(cuotas) } : {}),
        ...(referencia.trim() ? { referencia: referencia.trim() } : {}),
      })
      onRegistrada(venta)
    } catch (err) {
      setError(err.message)
      setGuardando(false)
    }
  }

  return (
    <Modal titulo="Registrar venta" onCerrar={onCerrar} ancho="ancho">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="grilla">
          <label>Medio de pago
            <select value={medioPago} onChange={(e) => setMedioPago(e.target.value)}>
              {MEDIOS_PAGO.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
            </select></label>
          {medioPago === 'TARJETA_CREDITO' && (
            <label>Cuotas (5 % de recargo por cuota)
              <input type="number" min="1" step="1" value={cuotas} onChange={(e) => setCuotas(e.target.value)} />
            </label>
          )}
          <label>Referencia (opcional)
            <input value={referencia} onChange={(e) => setReferencia(e.target.value)} /></label>
        </div>
        <SelectorProductos productos={productos} cantidades={cantidades} onChange={setCantidades} mostrarPrecio />
        <div className="resumen-modal">
          <span>Subtotal <b>{pesos(subtotal)}</b></span>
          <span>Total a cobrar <b>{pesos(total)}</b>
            {medioPago === 'EFECTIVO' && <small> (10 % de descuento)</small>}</span>
        </div>
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valida || guardando}>
            {guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}

// ---------------------------------------------------------------------------
// Modal: registrar devolución de una venta.
// ---------------------------------------------------------------------------
function ModalDevolucion({ venta, onCerrar, onRegistrada }) {
  const [cantidades, setCantidades] = useState({})
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const items = Object.entries(cantidades)
    .filter(([, c]) => Number(c) > 0)
    .map(([id, c]) => ({ producto_id: Number(id), cantidad: Number(c) }))
  const excedidos = venta.items.filter((i) =>
    Number(cantidades[i.producto_id] || 0) > i.disponible_para_devolver)
  const valida = items.length > 0 && excedidos.length === 0 && motivo.trim()
    && items.every((i) => Number.isInteger(i.cantidad))

  const guardar = async (e) => {
    e.preventDefault()
    if (!valida || guardando) return
    setGuardando(true)
    setError('')
    try {
      onRegistrada(await api.registrarDevolucion({ venta_id: venta.id, items, motivo: motivo.trim() }))
    } catch (err) {
      setError(err.message)
      setGuardando(false)
    }
  }

  return (
    <Modal titulo={`Registrar devolución · venta n.º ${venta.id}`} onCerrar={onCerrar} ancho="ancho">
      <form className="formulario-modal" onSubmit={guardar}>
        <p className="ayuda">Venta del {formatearFecha(venta.fecha)} por {pesos(venta.total)}.
          El reintegro es proporcional a lo cobrado y el stock vuelve al local.</p>
        {error && <div className="error" role="alert">{error}</div>}
        <table className="tabla-detalle">
          <thead><tr><th>Producto</th><th className="numero">Vendido</th>
            <th className="numero">Ya devuelto</th><th className="numero">A devolver</th></tr></thead>
          <tbody>{venta.items.map((i) => (
            <tr key={i.producto_id} className={excedidos.includes(i) ? 'con-error' : ''}>
              <td>{i.nombre}</td><td className="numero">{i.cantidad}</td>
              <td className="numero">{i.devuelto}</td>
              <td className="numero">
                <input type="number" min="0" max={i.disponible_para_devolver} step="1"
                       aria-label={`Cantidad a devolver de ${i.nombre}`}
                       disabled={i.disponible_para_devolver === 0}
                       value={cantidades[i.producto_id] ?? ''}
                       onChange={(e) => setCantidades({ ...cantidades, [i.producto_id]: e.target.value })} />
                <small> máx. {i.disponible_para_devolver}</small>
              </td>
            </tr>
          ))}</tbody>
        </table>
        {excedidos.length > 0 && (
          <div className="error" role="alert">No podés devolver más unidades de las vendidas
            (revisá {excedidos.map((i) => i.nombre).join(', ')}).</div>
        )}
        <label>Motivo
          <input required value={motivo} onChange={(e) => setMotivo(e.target.value)} /></label>
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valida || guardando}>
            {guardando ? 'Guardando…' : 'Guardar devolución'}</button>
        </div>
      </form>
    </Modal>
  )
}
