import { useState } from 'react'

export default function SelectorProductos({ productos, cantidades, onChange, mostrarPrecio = false }) {
  const [productoId, setProductoId] = useState('')
  const seleccionados = Object.keys(cantidades).map(Number)
  const disponibles = productos.filter((p) => !seleccionados.includes(p.id))

  const agregar = () => {
    if (!productoId) return
    onChange({ ...cantidades, [productoId]: '1' })
    setProductoId('')
  }

  const quitar = (id) => {
    const actualizadas = { ...cantidades }
    delete actualizadas[id]
    onChange(actualizadas)
  }

  return (
    <div className="selector-productos">
      <div className="fila-seleccion">
        <label>Agregar producto
          <select value={productoId} onChange={(e) => setProductoId(e.target.value)}>
            <option value="">Elegí un producto…</option>
            {disponibles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.nombre}{mostrarPrecio ? ` · $${Number(p.precio_venta).toFixed(2)}` : ''}
              </option>
            ))}
          </select>
        </label>
        <button type="button" disabled={!productoId} onClick={agregar}>Agregar</button>
      </div>
      {seleccionados.map((id) => {
        const producto = productos.find((p) => p.id === id)
        if (!producto) return null
        return (
          <div className="producto-seleccionado" key={id}>
            <span>{producto.nombre}
              {mostrarPrecio && ` · $${Number(producto.precio_venta).toFixed(2)}`}
            </span>
            <label>Cantidad
              <input type="number" min="1" step="1" value={cantidades[id]}
                     onChange={(e) => onChange({ ...cantidades, [id]: e.target.value })} />
            </label>
            <button type="button" className="secundario"
                    onClick={() => quitar(id)}>Quitar</button>
          </div>
        )
      })}
    </div>
  )
}
