import { Fragment, useState } from 'react'
import { api } from '../api.js'
import {
  AlternarEstado, Avisos, BarraFiltros, BotonIcono, Cargando, Estado, Modal, Vacio,
  useConfirmacion, useListado,
} from '../components/UI.jsx'
import { pesos } from '../utils/fechas.js'

// Pestaña "Productos" del local: buscador parcial, paginación y, para el
// administrador, habilitar/deshabilitar y su stock mínimo propio.
export default function ProductosLocal({ usuario }) {
  const esAdmin = usuario.rol === 'ADMINISTRADOR'
  const listado = useListado(
    (f) => api.buscarProductosSucursal(usuario.sucursal_id, f), { q: '', habilitado: '' })
  const { filtros, setFiltros } = listado
  const [abierto, setAbierto] = useState(null)
  const [editando, setEditando] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(null)
  const [dialogo, confirmar] = useConfirmacion()

  const cambiarHabilitacion = async (p) => {
    const habilitar = !p.habilitado
    if (!habilitar && !await confirmar({
      titulo: `Deshabilitar ${p.nombre}`, peligro: true, textoAceptar: 'Deshabilitar',
      mensaje: 'Dejará de aparecer para vender y para solicitar al CD. Para deshabilitarlo no tiene que tener stock ni bultos pendientes.',
    })) return
    setOcupado(p.id)
    setError('')
    try {
      await api.cambiarHabilitacionProducto(usuario.sucursal_id, p.id, habilitar)
      setMensaje(`${p.nombre} ${habilitar ? 'habilitado' : 'deshabilitado'} en el local.`)
      listado.recargar()
    } catch (e) { setError(e.message) } finally { setOcupado(null) }
  }

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>Productos · {usuario.sucursal}</h2>
          <p className="ayuda">{esAdmin
            ? 'Habilitá los productos que vende el local y configurá su stock mínimo (es propio de este local).'
            : 'Productos del catálogo y su disponibilidad en el local.'}</p>
        </div>
      </header>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />
      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label className="campo-ancho">Buscar producto
          <input type="search" value={filtros.q} placeholder="Nombre, código o categoría (parcial)"
                 onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} /></label>
        <label>Estado en el local
          <select value={filtros.habilitado} onChange={(e) => setFiltros({ ...filtros, habilitado: e.target.value })}>
            <option value="">Todos</option><option value="1">Habilitados</option>
            <option value="0">Deshabilitados</option>
          </select></label>
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio /> : (
          <table className="tabla-compacta">
            <thead><tr><th>Producto</th><th>Categoría</th><th className="numero">Precio</th>
              <th className="numero">Stock libre</th><th className="numero">Mínimo del local</th>
              <th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((p) => (
              <Fragment key={p.id}>
                <tr className={p.habilitado && p.libre < p.stock_minimo_local ? 'bajo' : ''}>
                  <td><b>{p.nombre}</b><small className="codigo"> {p.codigo}</small></td>
                  <td>{p.categoria ?? '—'}</td>
                  <td className="numero">{pesos(p.precio_venta)}</td>
                  <td className="numero">{p.libre}</td>
                  <td className="numero">{p.stock_minimo_local}</td>
                  <td><Estado activo={Boolean(p.habilitado)} textos={['Habilitado', 'Deshabilitado']} /></td>
                  <td className="acciones">
                    <BotonIcono icono={abierto === p.id ? 'ocultar' : 'ver'}
                                etiqueta={abierto === p.id ? 'Cerrar detalle' : 'Abrir detalle'}
                                activo={abierto === p.id} onClick={() => setAbierto(abierto === p.id ? null : p.id)} />
                    {esAdmin && <>
                      <BotonIcono icono="minimo" etiqueta="Editar stock mínimo del local"
                                  onClick={() => setEditando(p)} />
                      <AlternarEstado activo={Boolean(p.habilitado)} verbos={['Deshabilitar', 'Habilitar']}
                                      disabled={ocupado === p.id} onCambiar={() => cambiarHabilitacion(p)} />
                    </>}
                  </td>
                </tr>
                {abierto === p.id && (
                  <tr className="fila-detalle"><td colSpan="7">
                    <dl className="detalle-datos">
                      <div><dt>Código</dt><dd>{p.codigo}</dd></div>
                      <div><dt>Categoría</dt><dd>{p.categoria ?? '—'}</dd></div>
                      <div><dt>Proveedor</dt><dd>{p.proveedor ?? '—'}</dd></div>
                      <div><dt>Precio de venta</dt><dd>{pesos(p.precio_venta)}</dd></div>
                      <div><dt>Stock libre en el local</dt><dd>{p.libre}</dd></div>
                      <div><dt>Mínimo del local</dt><dd>{p.stock_minimo_local}</dd></div>
                      <div><dt>Mínimo por defecto del catálogo</dt><dd>{p.stock_minimo}</dd></div>
                    </dl>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>
      {editando && (
        <ModalMinimo producto={editando} sucursalId={usuario.sucursal_id}
                     onCerrar={() => setEditando(null)}
                     onGuardado={(p) => {
                       setEditando(null)
                       setMensaje(`Stock mínimo de ${p.nombre} en el local: ${p.stock_minimo_local}. El mínimo del CD se recalculó.`)
                       listado.recargar()
                     }} />
      )}
      {dialogo}
    </section>
  )
}

function ModalMinimo({ producto, sucursalId, onCerrar, onGuardado }) {
  const [valor, setValor] = useState(String(producto.stock_minimo_local))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const valido = valor !== '' && Number.isInteger(Number(valor)) && Number(valor) >= 0
  const guardar = async (e) => {
    e.preventDefault()
    if (!valido || guardando) return
    setGuardando(true)
    try {
      onGuardado(await api.cambiarMinimoLocal(sucursalId, producto.id, Number(valor)))
    } catch (err) { setError(err.message); setGuardando(false) }
  }
  return (
    <Modal titulo={`Stock mínimo · ${producto.nombre}`} onCerrar={onCerrar} ancho="chico">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        <p className="ayuda">Es el mínimo de <b>este local</b>: no cambia el de los otros locales.
          El mínimo de los centros de distribución es la suma de los mínimos de todos los locales
          y se actualiza solo. Si el stock libre queda por debajo, se genera una alerta.</p>
        <label>Stock mínimo
          <input type="number" min="0" step="1" required value={valor}
                 onChange={(e) => setValor(e.target.value)} /></label>
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valido || guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}
