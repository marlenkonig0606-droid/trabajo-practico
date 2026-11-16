import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'
import {
  AlternarEstado, Avisos, BarraFiltros, BotonIcono, BotonPrincipal, Cargando, Estado, Modal,
  Vacio, useConfirmacion, useListado,
} from '../components/UI.jsx'
import { pesos } from '../utils/fechas.js'

// Configuración de cada sección del catálogo (lo que varía entre ellas).
const SECCIONES = {
  productos: {
    titulo: 'Productos', nuevo: 'Nuevo producto', entidad: 'el producto',
    buscar: api.buscarProductos, crear: api.crearProducto, actualizar: api.actualizarProducto,
    cambiarEstado: api.cambiarEstadoProducto,
    detalleBaja: 'Se conserva su historial. No podrá venderse ni solicitarse mientras esté inactivo.',
    placeholder: 'Nombre o código (parcial)',
  },
  categorias: {
    titulo: 'Categorías', nuevo: 'Nueva categoría', entidad: 'la categoría',
    buscar: api.buscarCategorias, crear: api.crearCategoria, actualizar: api.actualizarCategoria,
    cambiarEstado: api.cambiarEstadoCategoria,
    detalleBaja: 'Los productos existentes conservan la categoría; no se podrán asignar productos nuevos.',
    placeholder: 'Nombre o descripción',
  },
  proveedores: {
    titulo: 'Proveedores', nuevo: 'Nuevo proveedor', entidad: 'el proveedor',
    buscar: api.buscarProveedores, crear: api.crearProveedor, actualizar: api.actualizarProveedor,
    cambiarEstado: api.cambiarEstadoProveedor,
    detalleBaja: 'Se conserva el historial y no podrá elegirse para nuevos productos.',
    placeholder: 'Nombre, razón social o CUIT',
  },
  sucursales: {
    titulo: 'Sucursales', nuevo: 'Nueva sucursal', entidad: 'la sucursal',
    buscar: api.buscarSucursales, crear: api.crearSucursal, actualizar: api.actualizarSucursal,
    cambiarEstado: api.cambiarEstadoSucursal,
    detalleBaja: 'Se conservan stock e historial; una sucursal inactiva no puede operar.',
    placeholder: 'Nombre, dirección o código',
  },
}

const CAMPOS = {
  productos: [
    { id: 'codigo', titulo: 'Código', requerido: true },
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'categoria_id', titulo: 'Categoría', tipo: 'categoria', requerido: true },
    { id: 'proveedor_id', titulo: 'Proveedor', tipo: 'proveedor' },
    { id: 'precio_costo', titulo: 'Precio de costo', tipo: 'numero', minimo: 0, paso: '0.01', requerido: true },
    { id: 'precio_venta', titulo: 'Precio de venta', tipo: 'numero', minimo: 0, paso: '0.01', requerido: true },
    { id: 'stock_minimo', titulo: 'Stock mínimo inicial en cada local', tipo: 'numero', minimo: 0, paso: 1, requerido: true },
  ],
  categorias: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'descripcion', titulo: 'Descripción' },
  ],
  proveedores: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'razon_social', titulo: 'Razón social', requerido: true },
    { id: 'cuit', titulo: 'CUIT (11 dígitos)', requerido: true },
  ],
  sucursales: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'direccion', titulo: 'Dirección', requerido: true },
    { id: 'tipo', titulo: 'Tipo', tipo: 'tipo_sucursal', requerido: true },
    // Solo al crear un LOCAL: si se deja vacío, se genera admin.local<id>@cdlocales.local
    { id: 'email_admin', titulo: 'Correo del administrador (opcional)', soloAltaLocal: true },
  ],
}

const datosIniciales = (seccion, fila = null) => Object.fromEntries(
  CAMPOS[seccion].map((c) => [c.id, fila?.[c.id] == null ? '' : String(fila[c.id])]))

export default function Catalogo() {
  const [seccion, setSeccion] = useState('productos')
  const [categorias, setCategorias] = useState([])
  const [proveedores, setProveedores] = useState([])

  const recargarAuxiliares = () => Promise.all([api.categorias(), api.proveedores()])
    .then(([c, p]) => { setCategorias(c); setProveedores(p) })
  useEffect(() => { recargarAuxiliares().catch(() => {}) }, [])

  return (
    <section className="pantalla catalogo">
      <header className="pantalla-cabecera">
        <div>
          <h2>Catálogo</h2>
          <p className="ayuda">Productos, categorías, proveedores y sucursales. Las sucursales activas
            aparecen en el registro de acceso.</p>
        </div>
      </header>
      <div className="catalogo-tabs" role="tablist" aria-label="Sección del catálogo">
        {Object.entries(SECCIONES).map(([id, s]) => (
          <button key={id} role="tab" aria-selected={seccion === id}
                  className={seccion === id ? 'activo' : ''} onClick={() => setSeccion(id)}>{s.titulo}</button>
        ))}
      </div>
      {/* key: cada sección tiene su propio listado, filtros y página */}
      <SeccionCatalogo key={seccion} seccion={seccion} categorias={categorias}
                       proveedores={proveedores} onCambioAuxiliar={recargarAuxiliares} />
    </section>
  )
}

function SeccionCatalogo({ seccion, categorias, proveedores, onCambioAuxiliar }) {
  const config = SECCIONES[seccion]
  const listado = useListado(config.buscar, { q: '', estado: '', categoria_id: '', tipo: '' })
  const { filtros, setFiltros } = listado
  const [abierto, setAbierto] = useState(null)
  const [edicion, setEdicion] = useState(null)        // { fila } o { fila: null } para alta
  const [credencial, setCredencial] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [ocupado, setOcupado] = useState(null)
  const [dialogo, confirmar] = useConfirmacion()

  const nombreCategoria = (id) => categorias.find((c) => c.id === id)?.nombre ?? '—'
  const nombreProveedor = (id) => proveedores.find((p) => p.id === id)?.nombre ?? '—'

  const cambiarEstado = async (fila) => {
    const activar = !fila.activo
    const ok = await confirmar({
      titulo: `${activar ? 'Activar' : 'Desactivar'} ${config.entidad}`,
      mensaje: `${activar ? '¿Activar' : '¿Desactivar'} ${config.entidad} "${fila.nombre}"? ${config.detalleBaja}`,
      textoAceptar: activar ? 'Activar' : 'Desactivar', peligro: !activar,
    })
    if (!ok) return
    setOcupado(fila.id)
    setError('')
    try {
      await config.cambiarEstado(fila.id, activar)
      setMensaje(`"${fila.nombre}" ${activar ? 'activado' : 'desactivado'}.`)
      listado.recargar()
      if (seccion !== 'productos') onCambioAuxiliar()
    } catch (e) { setError(e.message) } finally { setOcupado(null) }
  }

  const guardado = (creado, esAlta) => {
    setEdicion(null)
    setMensaje(esAlta ? `"${creado.nombre}" registrado.` : 'Cambios guardados.')
    // Al crear un local, el backend crea su administrador y devuelve la
    // contraseña temporal UNA sola vez.
    if (creado?.administrador) setCredencial({ local: creado.nombre, ...creado.administrador })
    if (esAlta) listado.limpiar(); else listado.recargar()
    if (seccion !== 'productos') onCambioAuxiliar()
  }

  const columnas = {
    productos: [['Producto', (f) => <><b>{f.nombre}</b><small className="codigo"> {f.codigo}</small></>],
      ['Categoría', (f) => nombreCategoria(f.categoria_id)],
      ['Precio de venta', (f) => pesos(f.precio_venta), 'numero']],
    categorias: [['Nombre', (f) => <b>{f.nombre}</b>]],
    proveedores: [['Nombre', (f) => <b>{f.nombre}</b>], ['CUIT', (f) => f.cuit]],
    sucursales: [['Sucursal', (f) => <><b>{f.nombre}</b><small className="codigo"> {f.codigo}</small></>],
      ['Tipo', (f) => (f.tipo === 'CD' ? 'Centro de distribución' : 'Local')]],
  }[seccion]

  const detalle = (f) => ({
    productos: [['Código', f.codigo], ['Proveedor', nombreProveedor(f.proveedor_id)],
      ['Precio de costo', pesos(f.precio_costo)], ['Precio de venta', pesos(f.precio_venta)],
      ['Mínimo por defecto', f.stock_minimo]],
    categorias: [['Descripción', f.descripcion || '—']],
    proveedores: [['Razón social', f.razon_social], ['CUIT', f.cuit]],
    sucursales: [['Código', f.codigo], ['Dirección', f.direccion],
      ['Tipo', f.tipo === 'CD' ? 'Centro de distribución' : 'Local']],
  }[seccion])

  return (
    <>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />
      {credencial && (
        <div className="tarjeta credencial-temporal" role="status">
          <h3>Administrador creado para {credencial.local}</h3>
          <p>Usuario: <b>{credencial.email}</b></p>
          <p>Contraseña temporal: <code>{credencial.password_temporal}</code></p>
          <p className="ayuda">Entregásela al administrador del local: al entrar debe cambiarla. No se vuelve a mostrar.</p>
          <button className="secundario" type="button" onClick={() => setCredencial(null)}>Listo</button>
        </div>
      )}
      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}
                    acciones={<BotonPrincipal onClick={() => setEdicion({ fila: null })}>{config.nuevo}</BotonPrincipal>}>
        <label className="campo-ancho">Buscar
          <input type="search" value={filtros.q} placeholder={config.placeholder}
                 onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} /></label>
        <label>Estado
          <select value={filtros.estado} onChange={(e) => setFiltros({ ...filtros, estado: e.target.value })}>
            <option value="">Todos</option><option value="activos">Activos</option>
            <option value="inactivos">Inactivos</option>
          </select></label>
        {seccion === 'productos' && (
          <label>Categoría
            <select value={filtros.categoria_id} onChange={(e) => setFiltros({ ...filtros, categoria_id: e.target.value })}>
              <option value="">Todas</option>
              {categorias.map((c) => <option key={c.id} value={c.id}>{c.nombre}</option>)}
            </select></label>
        )}
        {seccion === 'sucursales' && (
          <label>Tipo
            <select value={filtros.tipo} onChange={(e) => setFiltros({ ...filtros, tipo: e.target.value })}>
              <option value="">Todos</option><option value="CD">Centros de distribución</option>
              <option value="LOCAL">Locales</option>
            </select></label>
        )}
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio /> : (
          <table className="tabla-compacta">
            <thead><tr>{columnas.map(([t, , clase]) => <th key={t} className={clase}>{t}</th>)}
              <th>Estado</th><th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((f) => (
              <Fragment key={f.id}>
                <tr className={f.activo ? '' : 'inactiva'}>
                  {columnas.map(([t, valor, clase]) => <td key={t} className={clase}>{valor(f)}</td>)}
                  <td><Estado activo={Boolean(f.activo)} /></td>
                  <td className="acciones">
                    <BotonIcono icono={abierto === f.id ? 'ocultar' : 'ver'}
                                etiqueta={abierto === f.id ? 'Cerrar detalle' : 'Abrir detalle'}
                                activo={abierto === f.id} onClick={() => setAbierto(abierto === f.id ? null : f.id)} />
                    <BotonIcono icono="editar" etiqueta="Editar" onClick={() => setEdicion({ fila: f })} />
                    <AlternarEstado activo={Boolean(f.activo)} disabled={ocupado === f.id}
                                    onCambiar={() => cambiarEstado(f)} />
                  </td>
                </tr>
                {abierto === f.id && (
                  <tr className="fila-detalle"><td colSpan={columnas.length + 2}>
                    <dl className="detalle-datos">
                      {detalle(f).map(([t, v]) => <div key={t}><dt>{t}</dt><dd>{v}</dd></div>)}
                    </dl>
                  </td></tr>
                )}
              </Fragment>
            ))}</tbody>
          </table>
        )}
        {listado.paginacion()}
      </div>

      {edicion && (
        <ModalFormulario seccion={seccion} fila={edicion.fila} categorias={categorias}
                         proveedores={proveedores} onCerrar={() => setEdicion(null)} onGuardado={guardado} />
      )}
      {dialogo}
    </>
  )
}

function ModalFormulario({ seccion, fila, categorias, proveedores, onCerrar, onGuardado }) {
  const config = SECCIONES[seccion]
  const [formulario, setFormulario] = useState(datosIniciales(seccion, fila))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const esAlta = fila === null

  const preparar = () => {
    const salida = { ...formulario }
    if (seccion === 'productos') {
      salida.categoria_id = Number(salida.categoria_id)
      salida.proveedor_id = salida.proveedor_id ? Number(salida.proveedor_id) : null
      salida.precio_costo = Number(salida.precio_costo)
      salida.precio_venta = Number(salida.precio_venta)
      salida.stock_minimo = Number(salida.stock_minimo)
    }
    return salida
  }

  const guardar = async (e) => {
    e.preventDefault()
    if (guardando) return
    setGuardando(true)
    setError('')
    try {
      const resultado = esAlta ? await config.crear(preparar())
        : await config.actualizar(fila.id, preparar())
      onGuardado(resultado, esAlta)
    } catch (err) { setError(err.message); setGuardando(false) }
  }

  // En una edición, se muestra también la categoría/proveedor actual aunque esté inactivo
  const opciones = (lista, actual) => lista.filter((x) => x.activo || x.id === Number(actual))

  return (
    <Modal titulo={esAlta ? config.nuevo : `Editar · ${fila.nombre}`} onCerrar={onCerrar} ancho="ancho">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        <div className="grilla">
          {CAMPOS[seccion]
            .filter((c) => !c.soloAltaLocal || (esAlta && formulario.tipo === 'LOCAL'))
            .map((c) => (
              <label key={c.id}>{c.titulo}
                {['categoria', 'proveedor', 'tipo_sucursal'].includes(c.tipo) ? (
                  <select required={c.requerido} value={formulario[c.id]}
                          onChange={(e) => setFormulario({ ...formulario, [c.id]: e.target.value })}>
                    <option value="">{c.tipo === 'proveedor' ? 'Sin proveedor' : 'Seleccionar…'}</option>
                    {c.tipo === 'categoria' && opciones(categorias, fila?.categoria_id)
                      .map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                    {c.tipo === 'proveedor' && opciones(proveedores, fila?.proveedor_id)
                      .map((x) => <option key={x.id} value={x.id}>{x.nombre}</option>)}
                    {c.tipo === 'tipo_sucursal' && <>
                      <option value="CD">Centro de distribución</option>
                      <option value="LOCAL">Local</option></>}
                  </select>
                ) : (
                  <input required={c.requerido} min={c.minimo} step={c.paso}
                         type={c.tipo === 'numero' ? 'number' : 'text'} value={formulario[c.id]}
                         onChange={(e) => setFormulario({ ...formulario, [c.id]: e.target.value })} />
                )}
              </label>
            ))}
        </div>
        {seccion === 'productos' && (
          <p className="ayuda">Cada local configura su propio stock mínimo; este valor solo se usa como
            punto de partida cuando el producto se habilita en un local nuevo.</p>
        )}
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}
