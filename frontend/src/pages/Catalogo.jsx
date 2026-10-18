import { useEffect, useState } from 'react'
import { api } from '../api.js'

const FORMULARIO_VACIO = {
  codigo: '',
  nombre: '',
  categoria_id: '',
  proveedor_id: '',
  precio_costo: '',
  precio_venta: '',
  stock_minimo: '0',
}

export default function Catalogo() {
  const [productos, setProductos] = useState([])
  const [categorias, setCategorias] = useState([])
  const [proveedores, setProveedores] = useState([])
  const [formulario, setFormulario] = useState(FORMULARIO_VACIO)
  const [editando, setEditando] = useState(null)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')

  const recargar = async () => {
    const [listaProductos, listaCategorias, listaProveedores] = await Promise.all([
      api.productos(),
      api.categorias(),
      api.proveedores(),
    ])
    setProductos(listaProductos)
    setCategorias(listaCategorias)
    setProveedores(listaProveedores)
  }

  useEffect(() => {
    recargar().catch((e) => setError(e.message))
  }, [])

  const cambiarCampo = (e) =>
    setFormulario({ ...formulario, [e.target.name]: e.target.value })

  const limpiarFormulario = () => {
    setFormulario(FORMULARIO_VACIO)
    setEditando(null)
  }

  const guardar = async (e) => {
    e.preventDefault()
    setError('')
    setMensaje('')
    const datos = {
      ...formulario,
      categoria_id: Number(formulario.categoria_id),
      proveedor_id: formulario.proveedor_id ? Number(formulario.proveedor_id) : null,
      precio_costo: Number(formulario.precio_costo),
      precio_venta: Number(formulario.precio_venta),
      stock_minimo: Number(formulario.stock_minimo),
    }
    try {
      if (editando === null) {
        await api.crearProducto(datos)
        setMensaje('Producto creado.')
      } else {
        await api.actualizarProducto(editando, datos)
        setMensaje('Producto actualizado.')
      }
      limpiarFormulario()
      await recargar()
    } catch (e) {
      setError(e.message)
    }
  }

  const editar = (producto) => {
    setError('')
    setMensaje('')
    setEditando(producto.id)
    setFormulario({
      codigo: producto.codigo,
      nombre: producto.nombre,
      categoria_id: String(producto.categoria_id),
      proveedor_id: producto.proveedor_id ? String(producto.proveedor_id) : '',
      precio_costo: String(producto.precio_costo),
      precio_venta: String(producto.precio_venta),
      stock_minimo: String(producto.stock_minimo),
    })
  }

  const eliminar = async (producto) => {
    if (!window.confirm(`¿Eliminar el producto "${producto.nombre}"?`)) return
    setError('')
    setMensaje('')
    try {
      await api.eliminarProducto(producto.id)
      if (editando === producto.id) limpiarFormulario()
      setMensaje('Producto eliminado.')
      await recargar()
    } catch (e) {
      setError(e.message)
    }
  }

  const nombreCategoria = (id) =>
    categorias.find((categoria) => categoria.id === id)?.nombre ?? `#${id}`

  return (
    <section>
      {error && <div className="error" role="alert">{error}</div>}
      {mensaje && <p role="status">{mensaje}</p>}

      <form className="tarjeta" onSubmit={guardar}>
        <h2>{editando === null ? 'Nuevo producto' : `Editar producto #${editando}`}</h2>
        <div className="grilla">
          <label>Código
            <input name="codigo" required value={formulario.codigo} onChange={cambiarCampo} />
          </label>
          <label>Nombre
            <input name="nombre" required value={formulario.nombre} onChange={cambiarCampo} />
          </label>
          <label>Categoría
            <select name="categoria_id" required value={formulario.categoria_id}
                    onChange={cambiarCampo}>
              <option value="">Elegí una categoría…</option>
              {categorias.map((categoria) => (
                <option key={categoria.id} value={categoria.id}>{categoria.nombre}</option>
              ))}
            </select>
          </label>
          <label>Proveedor (opcional)
            <select name="proveedor_id" value={formulario.proveedor_id} onChange={cambiarCampo}>
              <option value="">Sin proveedor</option>
              {proveedores.map((proveedor) => (
                <option key={proveedor.id} value={proveedor.id}>
                  {proveedor.razon_social}
                </option>
              ))}
            </select>
          </label>
          <label>Precio de costo
            <input name="precio_costo" type="number" min="0" step="0.01" required
                   value={formulario.precio_costo} onChange={cambiarCampo} />
          </label>
          <label>Precio de venta
            <input name="precio_venta" type="number" min="0" step="0.01" required
                   value={formulario.precio_venta} onChange={cambiarCampo} />
          </label>
          <label>Stock mínimo
            <input name="stock_minimo" type="number" min="0" step="1" required
                   value={formulario.stock_minimo} onChange={cambiarCampo} />
          </label>
        </div>
        <button type="submit">{editando === null ? 'Crear producto' : 'Guardar cambios'}</button>
        {editando !== null &&
          <button type="button" className="link" onClick={limpiarFormulario}>Cancelar</button>}
      </form>

      <div className="tarjeta">
        <h2>Productos</h2>
        {productos.length === 0
          ? <p className="vacio">Todavía no hay productos.</p>
          : (
            <table>
              <thead>
                <tr>
                  <th>Código</th><th>Nombre</th><th>Categoría</th>
                  <th>Costo</th><th>Venta</th><th>Stock mínimo</th><th>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {productos.map((producto) => (
                  <tr key={producto.id}>
                    <td>{producto.codigo}</td>
                    <td>{producto.nombre}</td>
                    <td>{nombreCategoria(producto.categoria_id)}</td>
                    <td>{producto.precio_costo}</td>
                    <td>{producto.precio_venta}</td>
                    <td>{producto.stock_minimo}</td>
                    <td>
                      <button type="button" onClick={() => editar(producto)}>Editar</button>{' '}
                      <button type="button" onClick={() => eliminar(producto)}>Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </div>
    </section>
  )
}
