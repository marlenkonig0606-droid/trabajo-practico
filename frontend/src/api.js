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
  stock: (sucursalId) => pedir('GET', `/stock/${sucursalId}`),

  ordenes: () => pedir('GET', '/ordenes'),
  crearOrden: (destino_id, items) => pedir('POST', '/ordenes', { destino_id, items }),
  crearBulto: (ordenId, items) => pedir('POST', `/ordenes/${ordenId}/bultos`, { items }),
  precintar: (id, precinto) => pedir('POST', `/bultos/${id}/precintar`, { precinto }),
  despachar: (id) => pedir('POST', `/bultos/${id}/despachar`),
  recibir: (id, precinto, intacto) => pedir('POST', `/bultos/${id}/recibir`, { precinto, intacto }),
  historial: (id) => pedir('GET', `/bultos/${id}/historial`),

  reporteRechazados: () => pedir('GET', '/reportes/bultos-rechazados'),
  reporteTransito: () => pedir('GET', '/reportes/transito'),
  // TODO (vos): ventas, devoluciones, ABM, resto de reportes
}
