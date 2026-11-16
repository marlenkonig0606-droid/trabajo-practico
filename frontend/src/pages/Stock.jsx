import { Fragment, useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import {
  AlternarEstado, Avisos, BarraFiltros, BotonIcono, Cargando, Estado, Modal, Vacio,
  useConfirmacion, useListado,
} from '../components/UI.jsx'
import { formatearFecha, pesos } from '../utils/fechas.js'

// Pantalla única de PRODUCTOS Y STOCK.
// - Local: sus productos con el stock, el mínimo propio y (si es administrador)
//   habilitar/deshabilitar y editar el mínimo.
// - CD: el stock de cualquier sucursal y el ajuste del stock de su propio CD.
// Filtros: texto, categoría, proveedor, situación y (en el local) estado.
export default function Stock({ usuario }) {
  const esCD = usuario.tipo === 'CD'
  const esAdminLocal = !esCD && usuario.rol === 'ADMINISTRADOR'
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal] = useState(usuario.sucursal_id)
  const [opciones, setOpciones] = useState([])
  const [alertas, setAlertas] = useState([])
  const [verAlertas, setVerAlertas] = useState(true)
  const [abierto, setAbierto] = useState(null)
  const [ajustando, setAjustando] = useState(null)
  const [editandoMinimo, setEditandoMinimo] = useState(null)
  const [ocupado, setOcupado] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [dialogo, confirmar] = useConfirmacion()

  const listado = useListado((f) => api.buscarStock(sucursal, f),
    { q: '', situacion: '', proveedor_id: '', categoria_id: '', habilitado: '' }, [sucursal])
  const { filtros, setFiltros } = listado

  useEffect(() => {
    api.sucursales().then(setSucursales).catch((e) => setError(e.message))
  }, [])
  // Las opciones de categoría y proveedor salen de los mismos productos de la sucursal.
  useEffect(() => {
    api.buscarStock(sucursal, {}).then(setOpciones).catch(() => {})
  }, [sucursal])
  const cargarAlertas = () => api.alertas().then(setAlertas).catch((e) => setError(e.message))
  useEffect(() => { cargarAlertas() }, [])

  const categorias = useMemo(() => distintos(opciones, 'categoria_id', 'categoria'), [opciones])
  const proveedores = useMemo(() => distintos(opciones, 'proveedor_id', 'proveedor'), [opciones])

  const tipoSucursal = sucursales.find((s) => s.id === Number(sucursal))?.tipo
  const verCD = tipoSucursal === 'CD'
  const puedeAjustar = esCD && Number(sucursal) === usuario.sucursal_id
  const alertasVisibles = alertas.filter((a) => !esCD || a.sucursal ===
    sucursales.find((s) => s.id === Number(sucursal))?.nombre)
  const columnas = esCD ? 9 : 10

  const recargarTodo = () => {
    listado.recargar()
    cargarAlertas()
    api.buscarStock(sucursal, {}).then(setOpciones).catch(() => {})
  }

  const cambiarHabilitacion = async (f) => {
    const habilitar = !f.habilitado
    if (!habilitar && !await confirmar({
      titulo: `Deshabilitar ${f.nombre}`, peligro: true, textoAceptar: 'Deshabilitar',
      mensaje: 'Dejará de aparecer para vender y para solicitar al CD. Para deshabilitarlo no tiene que tener stock ni bultos pendientes.',
    })) return
    setOcupado(f.producto_id)
    setError('')
    try {
      await api.cambiarHabilitacionProducto(usuario.sucursal_id, f.producto_id, habilitar)
      setMensaje(`${f.nombre} ${habilitar ? 'habilitado' : 'deshabilitado'} en el local.`)
      recargarTodo()
    } catch (e) { setError(e.message) } finally { setOcupado(null) }
  }

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>{esCD ? 'Stock' : `Productos y stock · ${usuario.sucursal}`}</h2>
          <p className="ayuda">{verCD
            ? 'El mínimo del CD es la suma de los mínimos de los locales; el CD puede subirlo, pero nunca dejarlo por debajo de esa suma. Los mínimos de los locales los define cada local.'
            : esAdminLocal
              ? 'Habilitá los productos que vende el local y configurá su stock mínimo (es propio de este local).'
              : 'Productos del local, su stock libre y el mínimo que configuró el administrador.'}</p>
        </div>
        {esCD && (
          <label className="selector-sucursal">Sucursal
            <select value={sucursal} onChange={(e) => { setSucursal(Number(e.target.value)); setAbierto(null) }}>
              {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre} ({s.tipo})</option>)}
            </select></label>
        )}
      </header>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />

      {alertasVisibles.length > 0 && (
        <section className="tarjeta alertas">
          <div className="fila-titulo">
            <h3>⚠ Bajo el stock mínimo ({alertasVisibles.length})</h3>
            <BotonIcono icono={verAlertas ? 'ocultar' : 'ver'}
                        etiqueta={verAlertas ? 'Ocultar alertas' : 'Ver alertas'}
                        onClick={() => setVerAlertas(!verAlertas)} />
          </div>
          {verAlertas && (
            <ul>{alertasVisibles.map((a) => (
              <li key={a.id}><b>{a.producto}</b>{esCD && ` en ${a.sucursal}`}: {a.libre} libres,
                mínimo {a.minimo} → faltan <b>{Math.max(a.minimo - a.libre, 0)}</b>
                <span className="fecha"> · desde el {formatearFecha(a.fecha)}</span></li>
            ))}</ul>
          )}
        </section>
      )}

      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label className="campo-ancho">Producto
          <input type="search" value={filtros.q} placeholder="Nombre, código, categoría o proveedor (parcial)"
                 onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} /></label>
        <label>Categoría
          <select value={filtros.categoria_id} onChange={(e) => setFiltros({ ...filtros, categoria_id: e.target.value })}>
            <option value="">Todas</option>
            {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
          </select></label>
        <label>Proveedor
          <select value={filtros.proveedor_id} onChange={(e) => setFiltros({ ...filtros, proveedor_id: e.target.value })}>
            <option value="">Todos</option>
            {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
          </select></label>
        <label>Situación
          <select value={filtros.situacion} onChange={(e) => setFiltros({ ...filtros, situacion: e.target.value })}>
            <option value="">Todas</option><option value="bajo">Bajo el mínimo</option>
            <option value="ok">Sobre el mínimo</option>
          </select></label>
        {!esCD && (
          <label>Estado en el local
            <select value={filtros.habilitado} onChange={(e) => setFiltros({ ...filtros, habilitado: e.target.value })}>
              <option value="">Todos</option><option value="1">Habilitados</option>
              <option value="0">Deshabilitados</option>
            </select></label>
        )}
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio /> : (
          <table className="tabla-compacta">
            <thead><tr><th>Producto</th><th>Categoría</th><th>Proveedor</th>
              {!esCD && <th className="numero">Precio</th>}
              <th className="numero">Disponible</th><th className="numero">Reservado</th>
              <th className="numero">Libre</th><th className="numero">Mínimo</th><th>Situación</th>
              {!esCD && <th>Estado</th>}
              <th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((f) => {
              const bajo = f.libre < f.stock_minimo
              return (
                <Fragment key={f.producto_id}>
                  <tr className={bajo ? 'bajo' : ''}>
                    <td><b>{f.nombre}</b><small className="codigo"> {f.codigo}</small></td>
                    <td>{f.categoria ?? '—'}</td>
                    <td>{f.proveedor ?? <span className="ayuda">Sin proveedor</span>}</td>
                    {!esCD && <td className="numero">{pesos(f.precio_venta)}</td>}
                    <td className="numero">{f.disponible}</td>
                    <td className="numero">{f.reservado}</td>
                    <td className="numero"><b>{f.libre}</b></td>
                    <td className="numero">{f.stock_minimo}</td>
                    <td><span className={`insignia-estado ${bajo ? 'no' : 'si'}`}>
                      {bajo ? `Faltan ${f.stock_minimo - f.libre}` : 'OK'}</span></td>
                    {!esCD && <td><Estado activo={Boolean(f.habilitado)} textos={['Habilitado', 'Deshabilitado']} /></td>}
                    <td className="acciones">
                      <BotonIcono icono={abierto === f.producto_id ? 'ocultar' : 'ver'}
                                  etiqueta={abierto === f.producto_id ? 'Cerrar detalle' : 'Abrir detalle'}
                                  activo={abierto === f.producto_id}
                                  onClick={() => setAbierto(abierto === f.producto_id ? null : f.producto_id)} />
                      {puedeAjustar && <>
                        <BotonIcono icono="editar" etiqueta="Ajustar stock disponible"
                                    onClick={() => setAjustando(f)} />
                        <BotonIcono icono="minimo" etiqueta="Editar stock mínimo del CD"
                                    onClick={() => setEditandoMinimo(f)} />
                      </>}
                      {esAdminLocal && <>
                        <BotonIcono icono="minimo" etiqueta="Editar stock mínimo del local"
                                    onClick={() => setEditandoMinimo(f)} />
                        <AlternarEstado activo={Boolean(f.habilitado)} verbos={['Deshabilitar', 'Habilitar']}
                                        disabled={ocupado === f.producto_id}
                                        onCambiar={() => cambiarHabilitacion(f)} />
                      </>}
                    </td>
                  </tr>
                  {abierto === f.producto_id && (
                    <tr className="fila-detalle"><td colSpan={columnas}>
                      <dl className="detalle-datos">
                        <div><dt>Código</dt><dd>{f.codigo}</dd></div>
                        <div><dt>Categoría</dt><dd>{f.categoria ?? '—'}</dd></div>
                        <div><dt>Proveedor</dt><dd>{f.proveedor ?? '—'}</dd></div>
                        <div><dt>Precio de venta</dt><dd>{pesos(f.precio_venta)}</dd></div>
                        <div><dt>{verCD ? 'Mínimo del CD' : 'Mínimo del local'}</dt>
                          <dd>{verCD ? f.stock_minimo : f.stock_minimo_local}</dd></div>
                        {verCD && <div><dt>Suma de los mínimos de los locales</dt><dd>{f.minimo_locales}</dd></div>}
                        <div><dt>Mínimo por defecto del catálogo</dt><dd>{f.stock_minimo_defecto}</dd></div>
                        <div><dt>Estado en la sucursal</dt><dd>{f.habilitado || verCD ? 'Habilitado' : 'Deshabilitado'}</dd></div>
                      </dl>
                    </td></tr>
                  )}
                </Fragment>
              )
            })}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>

      {ajustando && (
        <ModalAjuste fila={ajustando} sucursalId={sucursal} onCerrar={() => setAjustando(null)}
                     onGuardado={() => {
                       setMensaje(`Stock de ${ajustando.nombre} actualizado.`)
                       setAjustando(null)
                       recargarTodo()
                     }} />
      )}
      {editandoMinimo && (
        <ModalMinimo fila={editandoMinimo} sucursalId={usuario.sucursal_id} esCD={esCD}
                     nombreSucursal={usuario.sucursal}
                     onCerrar={() => setEditandoMinimo(null)}
                     onGuardado={(p) => {
                       setEditandoMinimo(null)
                       setMensaje(`Stock mínimo de ${p.nombre} en ${usuario.sucursal}: ${esCD ? p.stock_minimo : p.stock_minimo_local}.`)
                       recargarTodo()
                     }} />
      )}
      {dialogo}
    </section>
  )
}

// Valores distintos (id + nombre) de una columna, ordenados por nombre.
function distintos(filas, id, nombre) {
  const mapa = new Map()
  filas.forEach((f) => { if (f[id] != null) mapa.set(f[id], f[nombre] ?? `#${f[id]}`) })
  return [...mapa].map(([clave, texto]) => ({ id: clave, nombre: texto }))
    .sort((a, b) => a.nombre.localeCompare(b.nombre))
}

function ModalAjuste({ fila, sucursalId, onCerrar, onGuardado }) {
  const [valor, setValor] = useState(String(fila.disponible))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const numero = Number(valor)
  const valido = valor !== '' && Number.isInteger(numero) && numero >= fila.reservado
    && numero !== fila.disponible
  const guardar = async (e) => {
    e.preventDefault()
    if (!valido || guardando) return
    setGuardando(true)
    try {
      await api.ajustarStock(Number(sucursalId), fila.producto_id, numero)
      onGuardado()
    } catch (err) { setError(err.message); setGuardando(false) }
  }
  return (
    <Modal titulo={`Ajustar stock · ${fila.nombre}`} onCerrar={onCerrar} ancho="chico">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        <p className="ayuda">Hay {fila.reservado} unidades reservadas para bultos: el disponible no
          puede quedar por debajo de ese número. El ajuste queda registrado como movimiento.</p>
        <label>Stock disponible
          <input type="number" min={fila.reservado} step="1" value={valor}
                 onChange={(e) => setValor(e.target.value)} /></label>
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valido || guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}

// El administrador del local edita el mínimo de SU local; el CD, el de SU CD.
// Ninguno puede tocar el mínimo del otro.
function ModalMinimo({ fila, sucursalId, esCD, nombreSucursal, onCerrar, onGuardado }) {
  const [valor, setValor] = useState(String(esCD ? fila.stock_minimo : fila.stock_minimo_local))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const piso = esCD ? fila.minimo_locales : 0
  const valido = valor !== '' && Number.isInteger(Number(valor)) && Number(valor) >= piso
  const guardar = async (e) => {
    e.preventDefault()
    if (!valido || guardando) return
    setGuardando(true)
    try {
      onGuardado(esCD
        ? await api.cambiarMinimoCd(sucursalId, fila.producto_id, Number(valor))
        : await api.cambiarMinimoLocal(sucursalId, fila.producto_id, Number(valor)))
    } catch (err) { setError(err.message); setGuardando(false) }
  }
  return (
    <Modal titulo={`Stock mínimo · ${fila.nombre}`} onCerrar={onCerrar} ancho="chico">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        {esCD ? (
          <p className="ayuda">Es el mínimo de <b>{nombreSucursal}</b>. Parte de la suma de los mínimos
            que pusieron los locales (<b>{piso}</b> unidades): podés subirlo, pero no dejarlo por
            debajo de esa suma. No cambia el mínimo de ningún local.</p>
        ) : (
          <p className="ayuda">Es el mínimo de <b>{nombreSucursal}</b>: no cambia el de los otros locales.
            El mínimo de los CD nunca queda por debajo de la suma de los mínimos de los locales.
            Si el stock libre queda por debajo, se genera una alerta.</p>
        )}
        <label>Stock mínimo
          <input type="number" min={piso} step="1" required value={valor}
                 onChange={(e) => setValor(e.target.value)} /></label>
        {esCD && valor !== '' && Number(valor) < piso && (
          <small className="error-campo">No puede ser menor que {piso} (suma de los locales).</small>
        )}
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valido || guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}
