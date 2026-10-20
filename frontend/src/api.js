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


// Arma "?desde=...&hasta=..." solo con las fechas que estén cargadas
function conFechas({ desde, hasta }) {
  const q = new URLSearchParams()
  if (desde) q.set('desde', desde)
  if (hasta) q.set('hasta', hasta)
  return q.toString() ? `?${q}` : ''
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
  anular: (id, motivo) => pedir('POST', `/bultos/${id}/anular`, { motivo }),
  recibir: (id, precinto, intacto) => pedir('POST', `/bultos/${id}/recibir`, { precinto, intacto }),
  historial: (id) => pedir('GET', `/bultos/${id}/historial`),

  alertas: () => pedir('GET', '/alertas'),
  eventos: () => pedir('GET', '/eventos'),

  reporteRechazados: (f = {}) => pedir('GET', `/reportes/bultos-rechazados${conFechas(f)}`),
  reporteTransito: () => pedir('GET', '/reportes/transito'),
  reporteExistencias: () => pedir('GET', '/reportes/existencias'),
  reporteMovimientos: () => pedir('GET', '/reportes/movimientos'),
  reporteVentas: (f = {}) => pedir('GET', `/reportes/ventas${conFechas(f)}`),
  reporteMasVendidos: (f = {}) => pedir('GET', `/reportes/mas-vendidos${conFechas(f)}`),
  ventas: () => pedir('GET', '/ventas'),
  venta: (id) => pedir('GET', `/ventas/${id}`),
  registrarVenta: (datos) => pedir('POST', '/ventas', datos),
  registrarDevolucion: (datos) => pedir('POST', '/devoluciones', datos),
}
