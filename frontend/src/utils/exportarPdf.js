// Genera y descarga un PDF (A4) con el contenido de un reporte.
//
// 1) html2canvas saca una "foto" del reporte sobre una COPIA de la página
//    (el usuario no ve ningún cambio), con el mismo ancho que tiene en pantalla
//    (los gráficos SVG ya están dibujados a ese ancho). En la copia se activa la clase
//    .exportando-pdf (tema claro, sin menús ni botones; ver styles.css).
// 2) La foto se corta en hojas A4 buscando cortes que no partan un gráfico,
//    un indicador o una fila de tabla.
// 3) jsPDF arma el archivo, agrega el número de página y lo descarga.
// Las librerías se cargan recién al apretar el botón (no pesan al abrir la app).

const ESCALA = 2                      // resolución de la imagen (2 = nítido)
const HOJA = { ancho: 210, alto: 297, margen: 10, pie: 8 }   // mm
const NO_CORTAR = [
  '.encabezado-impresion', '.reporte-seccion-cabecera', '.panel-grafico', '.kpi',
  '.grafico', '.diagnostico', '.diagnostico-curva', '.resumen-indicadores',
  '.resumen-hallazgos', 'tr', 'h2', 'h3', 'svg', '.podio', '.dona', '.barras-h-fila',
  '.aviso-recorte',
].join(',')

export async function exportarPdf(elemento, nombreArchivo) {
  const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
    import('html2canvas-pro'), import('jspdf'),
  ])
  const marca = `pdf-${Date.now()}`
  elemento.setAttribute('data-exportar', marca)
  let rangos = []
  let canvas
  try {
    canvas = await html2canvas(elemento, {
      scale: ESCALA,
      backgroundColor: '#ffffff',
      useCORS: true,
      logging: false,
      onclone: (doc) => {
        doc.body.classList.add('exportando-pdf')
        doc.querySelectorAll('details').forEach((d) => { d.open = true })
        const copia = doc.querySelector(`[data-exportar="${marca}"]`)
        // Zonas que no se pueden cortar, medidas sobre la copia ya maquetada.
        const origen = copia.getBoundingClientRect().top
        rangos = [...copia.querySelectorAll(NO_CORTAR)]
          .map((n) => [n, n.getBoundingClientRect()])
          .filter(([, r]) => r.height > 0)
          .map(([n, r]) => {
            // Un título no queda solo al final de la hoja: va con lo que le sigue.
            const extra = n.matches('.reporte-seccion-cabecera, h2, h3') ? 160 : 0
            return [(r.top - origen) * ESCALA, (r.bottom + extra - origen) * ESCALA]
          })
      },
    })
  } finally {
    elemento.removeAttribute('data-exportar')
  }

  const anchoUtil = HOJA.ancho - 2 * HOJA.margen
  const altoUtil = HOJA.alto - 2 * HOJA.margen - HOJA.pie
  const pxPorMm = canvas.width / anchoUtil
  const altoHojaPx = Math.floor(altoUtil * pxPorMm)
  const cortes = calcularCortes(canvas.height, altoHojaPx, rangos)

  const pdf = new jsPDF({ unit: 'mm', format: 'a4', orientation: 'portrait' })
  cortes.forEach(([desde, hasta], i) => {
    const hoja = document.createElement('canvas')
    hoja.width = canvas.width
    hoja.height = hasta - desde
    const ctx = hoja.getContext('2d')
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, hoja.width, hoja.height)
    ctx.drawImage(canvas, 0, desde, canvas.width, hoja.height, 0, 0, canvas.width, hoja.height)
    if (i > 0) pdf.addPage()
    pdf.addImage(hoja.toDataURL('image/jpeg', 0.92), 'JPEG', HOJA.margen, HOJA.margen,
      anchoUtil, hoja.height / pxPorMm)
    pdf.setFontSize(8)
    pdf.setTextColor(100, 116, 139)
    pdf.text(nombreArchivo, HOJA.margen, HOJA.alto - HOJA.margen)
    pdf.text(`Página ${i + 1} de ${cortes.length}`, HOJA.ancho - HOJA.margen,
      HOJA.alto - HOJA.margen, { align: 'right' })
  })
  pdf.save(`${nombreArchivo}.pdf`)
}

// Divide la altura total en hojas. Si el corte ideal cae dentro de un gráfico
// (o fila, indicador…), se adelanta al comienzo de ese elemento. Si el elemento
// es más alto que una hoja entera, no queda otra que cortarlo.
export function calcularCortes(altoTotal, altoHoja, rangos) {
  const cortes = []
  let desde = 0
  while (desde < altoTotal) {
    let hasta = Math.min(desde + altoHoja, altoTotal)
    if (hasta < altoTotal) {
      let cambio = true
      while (cambio) {
        cambio = false
        for (const [a, b] of rangos) {
          if (a < hasta && hasta < b && a > desde + altoHoja * 0.15) {
            hasta = Math.floor(a) - 1
            cambio = true
          }
        }
      }
    }
    cortes.push([desde, hasta])
    desde = hasta
  }
  return cortes
}
