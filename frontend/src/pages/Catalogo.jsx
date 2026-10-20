import { useEffect, useState } from 'react'
import { api } from '../api.js'

const SECCIONES = [
  { id: 'productos', titulo: 'Productos' },
  { id: 'categorias', titulo: 'Categorías' },
  { id: 'proveedores', titulo: 'Proveedores' },
  { id: 'sucursales', titulo: 'Sucursales' },
]

const CAMPOS = {
  productos: [
    { id: 'codigo', titulo: 'Código', requerido: true },
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'categoria_id', titulo: 'Categoría', tipo: 'categoria', requerido: true },
    { id: 'proveedor_id', titulo: 'Proveedor', tipo: 'proveedor' },
    { id: 'precio_costo', titulo: 'Precio de costo', tipo: 'numero', minimo: 0, paso: '0.01', requerido: true },
    { id: 'precio_venta', titulo: 'Precio de venta', tipo: 'numero', minimo: 0, paso: '0.01', requerido: true },
    { id: 'stock_minimo', titulo: 'Stock mínimo', tipo: 'numero', minimo: 0, paso: 1, requerido: true },
  ],
  categorias: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'descripcion', titulo: 'Descripción' },
  ],
  proveedores: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'razon_social', titulo: 'Razón social', requerido: true },
    { id: 'cuit', titulo: 'CUIT', requerido: true },
  ],
  sucursales: [
    { id: 'nombre', titulo: 'Nombre', requerido: true },
    { id: 'direccion', titulo: 'Dirección' },
    { id: 'tipo', titulo: 'Tipo', tipo: 'tipo_sucursal', requerido: true },
  ],
}

const COLUMNAS = {
  productos: [
    ['codigo', 'Código'], ['nombre', 'Nombre'], ['categoria_id', 'Categoría'],
    ['proveedor_id', 'Proveedor'], ['precio_costo', 'Costo'],
    ['precio_venta', 'Venta'], ['stock_minimo', 'Stock mínimo'],
  ],
  categorias: [['nombre', 'Nombre'], ['descripcion', 'Descripción']],
  proveedores: [['nombre', 'Nombre'], ['razon_social', 'Razón social'], ['cuit', 'CUIT']],
  sucursales: [['nombre', 'Nombre'], ['direccion', 'Dirección'], ['tipo', 'Tipo']],
}

const OPERACIONES = {
  productos: {
    listar: api.productos,
    crear: api.crearProducto,
    actualizar: api.actualizarProducto,
    eliminar: api.eliminarProducto,
  },
  categorias: {
    listar: api.categorias,
    crear: api.crearCategoria,
    actualizar: api.actualizarCategoria,
    eliminar: api.eliminarCategoria,
  },
  proveedores: {
    listar: api.proveedores,
    crear: api.crearProveedor,
    actualizar: api.actualizarProveedor,
    eliminar: api.eliminarProveedor,
  },
  sucursales: {
    listar: api.sucursales,
    crear: api.crearSucursal,
    actualizar: api.actualizarSucursal,
    eliminar: api.eliminarSucursal,
  },
}

const datosIniciales = (seccion, fila = null) => Object.fromEntries(
  CAMPOS[seccion].map((campo) => [
    campo.id,
    fila?.[campo.id] == null ? '' : String(fila[campo.id]),
  ]),
)

export default function Catalogo() {
  const [seccion, setSeccion] = useState('productos')
  const [datos, setDatos] = useState({
    productos: [], categorias: [], proveedores: [], sucursales: [],
  })
  const [formulario, setFormulario] = useState(null)
  const [filaEditada, setFilaEditada] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)

  const recargar = async () => {
    const [productos, categorias, proveedores, sucursales] = await Promise.all([
      api.productos(), api.categorias(), api.proveedores(), api.sucursales(),
    ])
    setDatos({ productos, categorias, proveedores, sucursales })
  }

  useEffect(() => {
    let activa = true
    recargar()
      .catch((e) => { if (activa) setError(e.message) })
      .finally(() => { if (activa) setCargando(false) })
    return () => { activa = false }
  }, [])

  const abrirNuevo = () => {
    setFilaEditada(null)
    setFormulario(datosIniciales(seccion))
    setError('')
    setMensaje('')
  }

  const abrirEdicion = (fila) => {
    setFilaEditada(fila.id)
    setFormulario(datosIniciales(seccion, fila))
    setError('')
    setMensaje('')
  }

  const cambiarSeccion = (id) => {
    setSeccion(id)
    setFormulario(null)
    setFilaEditada(null)
    setError('')
    setMensaje('')
  }

  const prepararDatos = () => {
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

  const guardar = async (evento) => {
    evento.preventDefault()
    setError('')
    setMensaje('')
    setGuardando(true)
    try {
      const operaciones = OPERACIONES[seccion]
      const payload = prepararDatos()
      if (filaEditada === null) {
        await operaciones.crear(payload)
      } else {
        await operaciones.actualizar(filaEditada, payload)
      }
      await recargar()
      setFormulario(null)
      setFilaEditada(null)
      setMensaje(filaEditada === null ? 'Registro creado.' : 'Cambios guardados.')
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  const eliminar = async (fila) => {
    if (!window.confirm(`¿Eliminar este registro de ${seccion}?`)) return
    setError('')
    setMensaje('')
    try {
      await OPERACIONES[seccion].eliminar(fila.id)
      await recargar()
      setMensaje('Registro eliminado.')
    } catch (e) {
      setError(e.message)
    }
  }

  const mostrarValor = (fila, campo) => {
    if (campo === 'categoria_id') {
      return datos.categorias.find((categoria) => categoria.id === fila.categoria_id)?.nombre ?? '—'
    }
    if (campo === 'proveedor_id') {
      return datos.proveedores.find((proveedor) => proveedor.id === fila.proveedor_id)?.nombre ?? '—'
    }
    if (campo === 'precio_costo' || campo === 'precio_venta') {
      return `$${Number(fila[campo]).toFixed(2)}`
    }
    return fila[campo] ?? '—'
  }

  const filas = datos[seccion]

  return (
    <section className="catalogo">
      <div className="catalogo-cabecera">
        <div>
          <h2>Catálogo</h2>
          <p className="vacio">Administrá productos, categorías, proveedores y sucursales.</p>
        </div>
        <button onClick={abrirNuevo} disabled={Boolean(formulario)}>Nuevo registro</button>
      </div>

      <div className="catalogo-tabs" role="tablist" aria-label="Tipo de registro">
        {SECCIONES.map((item) => (
          <button
            aria-selected={seccion === item.id}
            className={seccion === item.id ? 'activo' : ''}
            key={item.id}
            onClick={() => cambiarSeccion(item.id)}
            role="tab"
          >
            {item.titulo}
            <span>{datos[item.id].length}</span>
          </button>
        ))}
      </div>

      {error && <div className="error" role="alert">{error}</div>}
      {mensaje && <div className="exito" role="status">{mensaje}</div>}

      {formulario && (
        <form className="catalogo-formulario" onSubmit={guardar}>
          <div className="catalogo-formulario-titulo">
            <h3>{filaEditada === null ? 'Nuevo registro' : 'Editar registro'}</h3>
            <button className="link" type="button" onClick={() => setFormulario(null)}>
              Cancelar
            </button>
          </div>
          <div className="grilla">
            {CAMPOS[seccion].map((campo) => (
              <label key={campo.id}>
                {campo.titulo}
                {campo.tipo === 'categoria' || campo.tipo === 'proveedor' || campo.tipo === 'tipo_sucursal' ? (
                  <select
                    required={campo.requerido}
                    value={formulario[campo.id]}
                    onChange={(e) => setFormulario({ ...formulario, [campo.id]: e.target.value })}
                  >
                    <option value="">{campo.tipo === 'proveedor' ? 'Sin proveedor' : 'Seleccionar…'}</option>
                    {campo.tipo === 'categoria' && datos.categorias.map((categoria) => (
                      <option key={categoria.id} value={categoria.id}>{categoria.nombre}</option>
                    ))}
                    {campo.tipo === 'proveedor' && datos.proveedores.map((proveedor) => (
                      <option key={proveedor.id} value={proveedor.id}>{proveedor.nombre}</option>
                    ))}
                    {campo.tipo === 'tipo_sucursal' && <>
                      <option value="CD">Centro de distribución</option>
                      <option value="LOCAL">Local</option>
                    </>}
                  </select>
                ) : (
                  <input
                    min={campo.minimo}
                    required={campo.requerido}
                    step={campo.paso}
                    type={campo.tipo === 'numero' ? 'number' : 'text'}
                    value={formulario[campo.id]}
                    onChange={(e) => setFormulario({ ...formulario, [campo.id]: e.target.value })}
                  />
                )}
              </label>
            ))}
          </div>
          <button disabled={guardando} type="submit">
            {guardando ? 'Guardando…' : 'Guardar'}
          </button>
        </form>
      )}

      {cargando ? (
        <p className="vacio">Cargando catálogo…</p>
      ) : filas.length === 0 ? (
        <p className="vacio">No hay registros en esta sección.</p>
      ) : (
        <div className="catalogo-tabla">
          <table>
            <thead>
              <tr>
                {COLUMNAS[seccion].map(([campo, titulo]) => <th key={campo}>{titulo}</th>)}
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {filas.map((fila) => (
                <tr key={fila.id}>
                  {COLUMNAS[seccion].map(([campo]) => (
                    <td key={campo}>{mostrarValor(fila, campo)}</td>
                  ))}
                  <td className="catalogo-acciones">
                    <button className="link" onClick={() => abrirEdicion(fila)}>Editar</button>
                    <button className="link peligro" onClick={() => eliminar(fila)}>Eliminar</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
