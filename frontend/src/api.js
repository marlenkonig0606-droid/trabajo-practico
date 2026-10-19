// Un único lugar para hablar con el backend.
async function pedir(metodo, url, cuerpo) {
  const resp = await fetch(`/api${url}`, {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const datos = await resp.json()
  if (!resp.ok) throw new Error(datos.error || 'Error inesperado')
  return datos
}

export const api = {
  sucursales: () => pedir('GET', '/sucursales'),
  productos: () => pedir('GET', '/productos'),
  producto: (id) => pedir('GET', `/productos/${id}`),
  crearProducto: (datos) => pedir('POST', '/productos', datos),
  actualizarProducto: (id, datos) => pedir('PUT', `/productos/${id}`, datos),
  eliminarProducto: (id) => pedir('DELETE', `/productos/${id}`),
  categorias: () => pedir('GET', '/categorias'),
  categoria: (id) => pedir('GET', `/categorias/${id}`),
  crearCategoria: (datos) => pedir('POST', '/categorias', datos),
  actualizarCategoria: (id, datos) => pedir('PUT', `/categorias/${id}`, datos),
  eliminarCategoria: (id) => pedir('DELETE', `/categorias/${id}`),
  proveedores: () => pedir('GET', '/proveedores'),
  proveedor: (id) => pedir('GET', `/proveedores/${id}`),
  crearProveedor: (datos) => pedir('POST', '/proveedores', datos),
  actualizarProveedor: (id, datos) => pedir('PUT', `/proveedores/${id}`, datos),
  eliminarProveedor: (id) => pedir('DELETE', `/proveedores/${id}`),
  stock: (sucursalId) => pedir('GET', `/stock/${sucursalId}`),

  ordenes: () => pedir('GET', '/ordenes'),
  crearOrden: (destino_id, items) => pedir('POST', '/ordenes', { destino_id, items }),
  crearContenedor: (ordenId, items) => pedir('POST', `/ordenes/${ordenId}/contenedores`, { items }),
  precintar: (id, precinto) => pedir('POST', `/contenedores/${id}/precintar`, { precinto }),
  despachar: (id) => pedir('POST', `/contenedores/${id}/despachar`),
  recibir: (id, precinto, intacto) => pedir('POST', `/contenedores/${id}/recibir`, { precinto, intacto }),
  historial: (id) => pedir('GET', `/contenedores/${id}/historial`),

  reporteRechazados: () => pedir('GET', '/reportes/contenedores-rechazados'),
  reporteTransito: () => pedir('GET', '/reportes/transito'),
  // TODO (vos): ventas, devoluciones y resto de reportes
}
