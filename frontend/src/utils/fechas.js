// Formato de fechas para MOSTRAR: DD/MM/AAAA (formato argentino).
// La base guarda 'AAAA-MM-DD' o 'AAAA-MM-DD HH:MM:SS' en hora local. Se arma el
// texto cortando el string, SIN pasar por new Date(): así no hay corrimientos por
// zona horaria y el valor real nunca se altera.
export function formatearFecha(valor, { conHora = false } = {}) {
  if (!valor) return '—'
  const texto = String(valor)
  const m = texto.match(/^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2}))?/)
  if (!m) return texto
  const [, anio, mes, dia, hora, minutos] = m
  const fecha = `${dia}/${mes}/${anio}`
  return conHora && hora ? `${fecha} ${hora}:${minutos}` : fecha
}

export const formatearFechaHora = (valor) => formatearFecha(valor, { conHora: true })

// Fecha de hoy como 'AAAA-MM-DD' (para el atributo max de los <input type="date">)
export function hoyISO() {
  const hoy = new Date()
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, '0')}-${String(hoy.getDate()).padStart(2, '0')}`
}

export const pesos = (n) => n == null ? '—'
  : `$${Number(n).toLocaleString('es-AR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
