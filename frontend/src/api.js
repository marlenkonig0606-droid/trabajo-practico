// Un único lugar para hablar con el backend.
async function pedir(metodo, url, cuerpo) {
  const resp = await fetch(`/api${url}`, {
    method: metodo,
    headers: { 'Content-Type': 'application/json' },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const texto = await resp.text()
  let datos = null
  try {
    datos = texto ? JSON.parse(texto) : null
  } catch {
    // la respuesta no era JSON (ej. página de error HTML)
  }
  if (!resp.ok) {
    throw new Error(datos?.error || (texto ? `Error ${resp.status}` : `Sin respuesta del backend (${resp.status}). ¿Está corriendo python app.py?`))
  }
  return datos
}


export const api = {
  sucursales: () => pedir('GET', '/sucursales'),
  productos: () => pedir('GET', '/productos'),
  stock: (sucursalId) => pedir('GET', `/stock/${sucursalId}`),

  sugerirOrden: (localId) => pedir('GET', `/sucursales/${localId}/sugerencia`),
  ordenes: () => pedir('GET', '/ordenes'),
  crearOrden: (destino_id, items) => pedir('POST', '/ordenes', { destino_id, items }),
  crearBulto: (ordenId, items) => pedir('POST', `/ordenes/${ordenId}/bultos`, { items }),
  precintar: (id, precinto) => pedir('POST', `/bultos/${id}/precintar`, { precinto }),
  despachar: (id) => pedir('POST', `/bultos/${id}/despachar`),
  recibir: (id, precinto, intacto) => pedir('POST', `/bultos/${id}/recibir`, { precinto, intacto }),
  historial: (id) => pedir('GET', `/bultos/${id}/historial`),

  alertas: () => pedir('GET', '/alertas'),
  eventos: () => pedir('GET', '/eventos'),

  reporteRechazados: () => pedir('GET', '/reportes/bultos-rechazados'),
  reporteTransito: () => pedir('GET', '/reportes/transito'),
  ventas: () => pedir('GET', '/ventas'),
  venta: (id) => pedir('GET', `/ventas/${id}`),
  registrarVenta: (datos) => pedir('POST', '/ventas', datos),
  registrarDevolucion: (datos) => pedir('POST', '/devoluciones', datos),
}
