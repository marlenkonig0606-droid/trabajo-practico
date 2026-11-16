// Búsqueda parcial tolerante: sin mayúsculas ni tildes y aceptando UN error de
// tipeo (con 3 letras o más). Ej.: "agu", "AGUA", "aguo" encuentran "Agua 1.5L".
export const normalizar = (texto) => String(texto ?? '').normalize('NFD')
  .replace(/[̀-ͯ]/g, '').toLowerCase().trim()

function distancia(a, b) {
  const fila = Array.from({ length: b.length + 1 }, (_, j) => j)
  for (let i = 1; i <= a.length; i++) {
    let anterior = fila[0]
    fila[0] = i
    for (let j = 1; j <= b.length; j++) {
      const guardado = fila[j]
      fila[j] = Math.min(fila[j] + 1, fila[j - 1] + 1, anterior + (a[i - 1] === b[j - 1] ? 0 : 1))
      anterior = guardado
    }
  }
  return fila[b.length]
}

export function coincide(texto, consulta) {
  const q = normalizar(consulta)
  if (!q) return true
  const t = normalizar(texto)
  if (t.includes(q)) return true
  if (q.length < 3) return false
  // Se compara la consulta con cada tramo del texto de su mismo largo (±1).
  for (let largo = q.length - 1; largo <= q.length + 1; largo++) {
    for (let i = 0; i + largo <= t.length; i++) {
      if (distancia(q, t.slice(i, i + largo)) <= 1) return true
    }
  }
  return false
}
