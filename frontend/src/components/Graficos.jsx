// Gráficos del módulo de reportes, dibujados con SVG (el proyecto no usa
// librerías de gráficos). Todos reciben los datos ya calculados por el backend.
// Pasando el mouse por encima de una barra o punto se ve su valor (<title>).

export const COLORES = {
  principal: '#22d3ee',
  secundario: '#f97316',
  exito: '#34d399',
  alerta: '#fb7185',
  violeta: '#a78bfa',
  amarillo: '#facc15',
  ejes: 'rgb(145 169 187 / 55%)',
  grilla: 'rgb(126 182 207 / 12%)',
  texto: '#91a9bb',
}
export const PALETA = ['#22d3ee', '#f97316', '#a78bfa', '#34d399', '#facc15', '#fb7185']

const MESES = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic']
export const nombreMes = (aaaamm, conAnio = true) => {
  const [anio, mes] = aaaamm.split('-')
  return `${MESES[Number(mes) - 1]}${conAnio ? ` ${anio.slice(2)}` : ''}`
}
export const pesos = (n) => n == null ? '—'
  : `$${Number(n).toLocaleString('es-AR', { maximumFractionDigits: 0 })}`
export const numero = (n, d = 0) => n == null ? '—'
  : Number(n).toLocaleString('es-AR', { maximumFractionDigits: d })

// Escala "linda" para el eje Y: 0, paso, 2·paso… hasta cubrir el máximo.
// Con enteros (cantidades) el paso nunca es menor que 1.
function escala(maximo, divisiones = 4, enteros = false) {
  if (!maximo || maximo <= 0) return { tope: 1, marcas: [0, 1] }
  const crudo = maximo / divisiones
  const potencia = 10 ** Math.floor(Math.log10(crudo))
  let paso = [1, 2, 2.5, 5, 10].map((m) => m * potencia).find((p) => p >= crudo)
  if (enteros) paso = Math.max(1, Math.ceil(paso))
  const tope = paso * Math.ceil(maximo / paso)
  return { tope, marcas: Array.from({ length: Math.round(tope / paso) + 1 }, (_, i) => i * paso) }
}
const sonEnteros = (valores) => valores.every((v) => v == null || Number.isInteger(v))
const ANCHO = 1000      // ancho lógico del SVG (se escala al contenedor)
const corto = (n) => {
  const v = Math.abs(n)
  if (v >= 1e6) return `${numero(n / 1e6, 1)}M`
  if (v >= 1e3) return `${numero(n / 1e3, 1)}k`
  return numero(n, 1)
}

// ms -> 'DD/MM/AAAA' (los ms se calcularon desde la fecha local de la venta)
const fechaCorta = (ms) => {
  const d = new Date(ms)
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`
}

export function SinDatos({ children = 'No hay datos en el período seleccionado.' }) {
  return <p className="sin-datos">{children}</p>
}

// ---------------------------------------------------------------------------
// Barras verticales (con línea opcional sobre un segundo eje)
// ---------------------------------------------------------------------------
export function BarrasVerticales({ datos, formato = numero, color = COLORES.principal,
  formatoLinea = numero, destacarExtremos = true, alto = 300 }) {
  // La línea (segundo eje) se dibuja si los datos traen el campo "linea".
  const linea = datos.some((d) => d.linea != null)
  if (!datos.length || datos.every((d) => !d.valor && !d.linea)) return <SinDatos />
  const ancho = Math.max(ANCHO, datos.length * 46)
  const m = { arriba: 16, abajo: 34, izq: 52, der: linea ? 52 : 12 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const { tope, marcas } = escala(Math.max(...datos.map((d) => d.valor || 0)), 4,
    sonEnteros(datos.map((d) => d.valor)))
  const escalaLinea = linea ? escala(Math.max(...datos.map((d) => d.linea || 0)), 4,
    sonEnteros(datos.map((d) => d.linea))) : null
  const paso = w / datos.length
  const anchoBarra = Math.min(34, paso * 0.62)
  const valores = datos.map((d) => d.valor || 0).filter((v) => v > 0)
  const max = Math.max(...valores)
  const min = Math.min(...valores)
  const yLinea = (v) => m.arriba + h - (v / escalaLinea.tope) * h
  const puntosLinea = linea ? datos
    .map((d, i) => d.linea == null ? null : [m.izq + paso * i + paso / 2, yLinea(d.linea)])
    .filter(Boolean) : []
  return (
    <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img">
      {marcas.map((v) => {
        const y = m.arriba + h - (v / tope) * h
        return <g key={v}>
          <line x1={m.izq} x2={m.izq + w} y1={y} y2={y} stroke={COLORES.grilla} />
          <text x={m.izq - 8} y={y + 4} textAnchor="end" className="eje">{corto(v)}</text>
        </g>
      })}
      {escalaLinea?.marcas.map((v) => (
        <text key={`l${v}`} x={m.izq + w + 8} y={yLinea(v) + 4} className="eje eje-linea">
          {corto(v)}</text>
      ))}
      {datos.map((d, i) => {
        const valor = d.valor || 0
        const altoBarra = (valor / tope) * h
        const x = m.izq + paso * i + (paso - anchoBarra) / 2
        const extremo = destacarExtremos && valores.length > 1
          && (valor === max ? 'max' : valor === min ? 'min' : null)
        return <g key={d.etiqueta}>
          <rect x={x} y={m.arriba + h - altoBarra} width={anchoBarra} height={Math.max(altoBarra, 0)}
                rx="3" fill={extremo === 'max' ? COLORES.exito : extremo === 'min' ? COLORES.secundario : color}
                opacity={valor ? 0.9 : 0.25}>
            <title>{`${d.etiqueta}: ${formato(valor)}${d.detalle ? ` · ${d.detalle}` : ''}`}</title>
          </rect>
          <text x={m.izq + paso * i + paso / 2} y={alto - 12} textAnchor="middle" className="eje">
            {d.etiqueta}</text>
        </g>
      })}
      {puntosLinea.length > 1 && (
        <polyline points={puntosLinea.map((p) => p.join(',')).join(' ')} fill="none"
                  stroke={COLORES.amarillo} strokeWidth="2.5" />
      )}
      {linea && datos.map((d, i) => d.linea == null ? null : (
        <circle key={`p${i}`} cx={m.izq + paso * i + paso / 2} cy={yLinea(d.linea)} r="4"
                fill={COLORES.amarillo}>
          <title>{`${d.etiqueta}: ${formatoLinea(d.linea)}`}</title>
        </circle>
      ))}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Línea con puntos (evolución mensual)
// ---------------------------------------------------------------------------
export function Linea({ datos, formato = numero, color = COLORES.amarillo, alto = 260 }) {
  const conValor = datos.filter((d) => d.valor != null)
  if (conValor.length === 0) return <SinDatos />
  const ancho = Math.max(ANCHO, datos.length * 46)
  const m = { arriba: 18, abajo: 34, izq: 56, der: 14 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const { tope, marcas } = escala(Math.max(...conValor.map((d) => d.valor)))
  const paso = w / datos.length
  const xy = (d, i) => [m.izq + paso * i + paso / 2, m.arriba + h - (d.valor / tope) * h]
  const promedio = conValor.reduce((s, d) => s + d.valor, 0) / conValor.length
  const yProm = m.arriba + h - (promedio / tope) * h
  // Segmentos consecutivos: un mes sin ventas corta la línea (no se inventa el valor).
  const tramos = []
  let actual = []
  datos.forEach((d, i) => {
    if (d.valor == null) { if (actual.length) tramos.push(actual); actual = [] }
    else actual.push(xy(d, i))
  })
  if (actual.length) tramos.push(actual)
  return (
    <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img">
      {marcas.map((v) => {
        const y = m.arriba + h - (v / tope) * h
        return <g key={v}>
          <line x1={m.izq} x2={m.izq + w} y1={y} y2={y} stroke={COLORES.grilla} />
          <text x={m.izq - 8} y={y + 4} textAnchor="end" className="eje">{corto(v)}</text>
        </g>
      })}
      <line x1={m.izq} x2={m.izq + w} y1={yProm} y2={yProm} stroke={COLORES.texto}
            strokeDasharray="5 5"><title>{`Promedio de los meses: ${formato(promedio)}`}</title></line>
      {tramos.map((t, i) => t.length > 1 && (
        <polyline key={i} points={t.map((p) => p.join(',')).join(' ')} fill="none"
                  stroke={color} strokeWidth="2.5" />
      ))}
      {datos.map((d, i) => <g key={d.etiqueta}>
        {d.valor != null && (() => {
          const [x, y] = xy(d, i)
          return <circle cx={x} cy={y} r="4.5" fill={color}>
            <title>{`${d.etiqueta}: ${formato(d.valor)}`}</title></circle>
        })()}
        <text x={m.izq + paso * i + paso / 2} y={alto - 12} textAnchor="middle" className="eje">
          {d.etiqueta}</text>
      </g>)}
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Barras horizontales (ranking)
// ---------------------------------------------------------------------------
export function BarrasHorizontales({ datos, formato = numero, color = COLORES.principal }) {
  if (!datos.length) return <SinDatos />
  const max = Math.max(...datos.map((d) => d.valor), 1)
  return (
    <div className="barras-h">
      {datos.map((d, i) => (
        <div className="barras-h-fila" key={d.etiqueta} title={`${d.etiqueta}: ${formato(d.valor)}`}>
          <span className="barras-h-puesto">{i + 1}</span>
          <span className="barras-h-etiqueta">{d.etiqueta}</span>
          <div className="barras-h-pista">
            <div style={{ width: `${(d.valor / max) * 100}%`, background: d.color ?? color }} />
          </div>
          <span className="barras-h-valor">{formato(d.valor)}{d.detalle && <small> · {d.detalle}</small>}</span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Torta / dona con leyenda de importes y porcentajes
// ---------------------------------------------------------------------------
export function Dona({ datos, formato = numero, centro }) {
  const total = datos.reduce((s, d) => s + d.valor, 0)
  if (!total) return <SinDatos />
  let acumulado = 0
  const r = 70
  const C = 2 * Math.PI * r
  return (
    <div className="dona">
      <svg viewBox="0 0 200 200" className="dona-svg" role="img">
        <circle cx="100" cy="100" r={r} fill="none" stroke={COLORES.grilla} strokeWidth="34" />
        {datos.map((d, i) => {
          const fraccion = d.valor / total
          const trazo = (
            <circle key={d.etiqueta} cx="100" cy="100" r={r} fill="none"
                    stroke={d.color ?? PALETA[i % PALETA.length]} strokeWidth="34"
                    strokeDasharray={`${fraccion * C} ${C}`} strokeDashoffset={-acumulado * C}
                    transform="rotate(-90 100 100)">
              <title>{`${d.etiqueta}: ${formato(d.valor)} (${numero(fraccion * 100, 1)} %)`}</title>
            </circle>
          )
          acumulado += fraccion
          return trazo
        })}
        {centro && <>
          <text x="100" y="96" textAnchor="middle" className="dona-centro">{centro.valor}</text>
          <text x="100" y="116" textAnchor="middle" className="eje">{centro.texto}</text>
        </>}
      </svg>
      <ul className="dona-leyenda">
        {datos.map((d, i) => (
          <li key={d.etiqueta}>
            <span className="muestra-color" style={{ background: d.color ?? PALETA[i % PALETA.length] }} />
            <b>{d.etiqueta}</b>
            <span>{formato(d.valor)}</span>
            <strong>{numero((d.valor / total) * 100, 1)} %</strong>
          </li>
        ))}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Podio de los tres primeros
// ---------------------------------------------------------------------------
export function Podio({ puestos, formato = numero }) {
  if (!puestos.length) return <SinDatos>No hay productos vendidos en el período.</SinDatos>
  // Orden visual clásico: 2º, 1º, 3º
  const orden = [puestos[1], puestos[0], puestos[2]]
  const clases = ['segundo', 'primero', 'tercero']
  const medallas = ['2', '1', '3']
  return (
    <div className="podio">
      {orden.map((p, i) => p ? (
        <div key={clases[i]} className={`podio-puesto ${clases[i]}`}>
          <span className="podio-nombre">{p.etiqueta}</span>
          <span className="podio-valor">{formato(p.valor)}</span>
          <div className="podio-escalon"><span>{medallas[i]}</span></div>
        </div>
      ) : <div key={clases[i]} className={`podio-puesto ${clases[i]} vacio-podio`} />)}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Barras agrupadas (comparar series por categoría)
// ---------------------------------------------------------------------------
export function BarrasAgrupadas({ categorias, series, formato = numero, alto = 300 }) {
  if (!categorias.length || !series.length
      || series.every((s) => s.valores.every((v) => !v))) return <SinDatos />
  const ancho = Math.max(ANCHO, categorias.length * 56)
  const m = { arriba: 16, abajo: 34, izq: 48, der: 10 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const { tope, marcas } = escala(Math.max(...series.flatMap((s) => s.valores)), 4,
    sonEnteros(series.flatMap((s) => s.valores)))
  const paso = w / categorias.length
  const grupo = Math.min(paso * 0.75, series.length * 28)
  const barra = grupo / series.length
  return (
    <>
      <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img">
        {marcas.map((v) => {
          const y = m.arriba + h - (v / tope) * h
          return <g key={v}>
            <line x1={m.izq} x2={m.izq + w} y1={y} y2={y} stroke={COLORES.grilla} />
            <text x={m.izq - 8} y={y + 4} textAnchor="end" className="eje">{corto(v)}</text>
          </g>
        })}
        {categorias.map((c, i) => <g key={c}>
          {series.map((s, j) => {
            const v = s.valores[i] || 0
            const altoBarra = (v / tope) * h
            return <rect key={s.nombre} x={m.izq + paso * i + (paso - grupo) / 2 + j * barra}
                         y={m.arriba + h - altoBarra} width={barra - 2} height={altoBarra}
                         rx="2" fill={s.color}>
              <title>{`${s.nombre} · ${c}: ${formato(v)}`}</title></rect>
          })}
          <text x={m.izq + paso * i + paso / 2} y={alto - 12} textAnchor="middle" className="eje">{c}</text>
        </g>)}
      </svg>
      <Leyenda items={series.map((s) => ({ texto: s.nombre, color: s.color }))} />
    </>
  )
}

export function Leyenda({ items }) {
  return (
    <p className="grafico-leyenda">
      {items.map((it) => (
        <span key={it.texto} className="leyenda-item">
          <span className={`muestra-color ${it.linea ? 'linea' : ''}`} style={{ background: it.color }} />
          {it.texto}
        </span>
      ))}
    </p>
  )
}

// ---------------------------------------------------------------------------
// Histograma con curva normal de referencia (opcional)
// ---------------------------------------------------------------------------
export function Histograma({ clases, curva = [], media, limiteAlto, alto = 250 }) {
  if (!clases?.length) return <SinDatos />
  const ancho = 640
  const m = { arriba: 16, abajo: 38, izq: 44, der: 12 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const xMin = clases[0].desde
  const xMax = clases[clases.length - 1].hasta || xMin + 1
  const x = (v) => m.izq + ((v - xMin) / (xMax - xMin || 1)) * w
  const { tope, marcas } = escala(Math.max(...clases.map((c) => c.cantidad),
    ...curva.map((p) => p.y)))
  const y = (v) => m.arriba + h - (v / tope) * h
  return (
    <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img">
      {marcas.map((v) => <g key={v}>
        <line x1={m.izq} x2={m.izq + w} y1={y(v)} y2={y(v)} stroke={COLORES.grilla} />
        <text x={m.izq - 8} y={y(v) + 4} textAnchor="end" className="eje">{v}</text>
      </g>)}
      {clases.map((c) => {
        const atipica = limiteAlto != null && c.desde >= limiteAlto
        return <rect key={c.desde} x={x(c.desde) + 1} y={y(c.cantidad)}
                     width={Math.max(x(c.hasta) - x(c.desde) - 2, 1)} height={m.arriba + h - y(c.cantidad)}
                     fill={atipica ? COLORES.secundario : COLORES.principal} opacity="0.75">
          <title>{`${pesos(c.desde)} a ${pesos(c.hasta)}: ${c.cantidad} ventas`}</title>
        </rect>
      })}
      {curva.length > 1 && (
        <polyline points={curva.map((p) => `${x(p.x)},${y(p.y)}`).join(' ')} fill="none"
                  stroke={COLORES.amarillo} strokeWidth="2.5" />
      )}
      {media != null && (
        <line x1={x(media)} x2={x(media)} y1={m.arriba} y2={m.arriba + h}
              stroke={COLORES.exito} strokeDasharray="5 4" strokeWidth="2">
          <title>{`Media: ${pesos(media)}`}</title></line>
      )}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const v = xMin + (xMax - xMin) * f
        return <text key={f} x={x(v)} y={alto - 14} textAnchor="middle" className="eje">{corto(v)}</text>
      })}
      <text x={m.izq + w / 2} y={alto - 1} textAnchor="middle" className="eje">Importe del ticket ($)</text>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Dispersión
// ---------------------------------------------------------------------------
export function Dispersion({ puntos, etiquetaX, formatoX = numero, esFecha = false,
  limiteAlto, alto = 280 }) {
  if (puntos.length === 0) return <SinDatos />
  const ancho = 640
  const m = { arriba: 14, abajo: 40, izq: 56, der: 14 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const xs = puntos.map((p) => p.x)
  const xMin = Math.min(...xs)
  const xMax = Math.max(...xs)
  const rango = xMax - xMin || 1
  const { tope, marcas } = escala(Math.max(...puntos.map((p) => p.y)))
  const px = (v) => m.izq + ((v - xMin) / rango) * w
  const py = (v) => m.arriba + h - (v / tope) * h
  return (
    <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img">
      {marcas.map((v) => <g key={v}>
        <line x1={m.izq} x2={m.izq + w} y1={py(v)} y2={py(v)} stroke={COLORES.grilla} />
        <text x={m.izq - 8} y={py(v) + 4} textAnchor="end" className="eje">{corto(v)}</text>
      </g>)}
      {limiteAlto != null && limiteAlto < tope && (
        <line x1={m.izq} x2={m.izq + w} y1={py(limiteAlto)} y2={py(limiteAlto)}
              stroke={COLORES.secundario} strokeDasharray="6 4">
          <title>{`Límite de ticket atípico: ${pesos(limiteAlto)}`}</title></line>
      )}
      {puntos.map((p, i) => (
        <circle key={i} cx={px(p.x)} cy={py(p.y)} r={p.atipico ? 4 : 3}
                fill={p.atipico ? COLORES.secundario : COLORES.principal}
                opacity={p.atipico ? 0.95 : 0.55}>
          <title>{p.titulo}</title>
        </circle>
      ))}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const v = xMin + rango * f
        return <text key={f} x={px(v)} y={alto - 16} textAnchor="middle" className="eje">
          {esFecha ? fechaCorta(v)
            : formatoX(v)}</text>
      })}
      <text x={m.izq + w / 2} y={alto - 1} textAnchor="middle" className="eje">{etiquetaX}</text>
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Stock libre vs. mínimo (barra + marca del mínimo)
// ---------------------------------------------------------------------------
export function StockVsMinimo({ filas }) {
  if (!filas.length) return <SinDatos>El local no tiene productos con stock registrado.</SinDatos>
  const max = Math.max(...filas.map((f) => Math.max(f.libre, f.minimo)), 1)
  return (
    <div className="barras-h stock-minimo">
      {filas.map((f) => (
        <div className={`barras-h-fila estado-${f.estado.toLowerCase()}`} key={f.producto}
             title={`${f.producto}: libre ${f.libre}, mínimo ${f.minimo}, diferencia ${f.diferencia}`}>
          <span className="barras-h-etiqueta">{f.producto}</span>
          <div className="barras-h-pista">
            <div style={{ width: `${(f.libre / max) * 100}%` }} />
            <i className="marca-minimo" style={{ left: `${(f.minimo / max) * 100}%` }} />
          </div>
          <span className="barras-h-valor">
            {f.libre} / mín. {f.minimo}{' '}
            <small className={f.diferencia < 0 ? 'negativo' : ''}>
              ({f.diferencia > 0 ? '+' : ''}{f.diferencia})</small>
          </span>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Campana de Gauss: histograma de los tickets + curva normal de referencia,
// con la media (μ) y las franjas de ±1σ y ±2σ sombreadas.
// ---------------------------------------------------------------------------
export function CampanaGauss({ clases, curva = [], media, desvio, alto = 300 }) {
  if (!clases?.length) return <SinDatos />
  const ancho = 1000
  const m = { arriba: 26, abajo: 46, izq: 52, der: 16 }
  const w = ancho - m.izq - m.der
  const h = alto - m.arriba - m.abajo
  const xMin = Math.min(clases[0].desde, ...curva.map((p) => p.x))
  const xMax = Math.max(clases[clases.length - 1].hasta, ...curva.map((p) => p.x))
  const x = (v) => m.izq + ((v - xMin) / (xMax - xMin || 1)) * w
  const { tope, marcas } = escala(Math.max(...clases.map((c) => c.cantidad),
    ...curva.map((p) => p.y)), 4, true)
  const y = (v) => m.arriba + h - (v / tope) * h
  const base = m.arriba + h
  const recortar = (v) => Math.min(Math.max(v, xMin), xMax)
  const franja = (k) => [x(recortar(media - k * desvio)), x(recortar(media + k * desvio))]
  const linea = curva.map((p) => `${x(p.x)},${y(p.y)}`).join(' ')
  const area = curva.length ? `M${x(curva[0].x)},${base} L${linea.replaceAll(' ', ' L')} L${x(curva[curva.length - 1].x)},${base} Z` : ''
  return (
    <svg className="svg-grafico" viewBox={`0 0 ${ancho} ${alto}`} role="img"
         aria-label="Histograma de tickets con curva normal de referencia">
      <defs>
        <linearGradient id="gauss-barras" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#22d3ee" stopOpacity="0.95" />
          <stop offset="1" stopColor="#0e7490" stopOpacity="0.55" />
        </linearGradient>
        <linearGradient id="gauss-area" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#facc15" stopOpacity="0.35" />
          <stop offset="1" stopColor="#facc15" stopOpacity="0.02" />
        </linearGradient>
      </defs>
      {desvio > 0 && <>
        <rect x={franja(2)[0]} y={m.arriba} width={franja(2)[1] - franja(2)[0]} height={h}
              fill="rgb(167 139 250 / 6%)"><title>μ ± 2σ: el 95 % de los tickets si fuera normal</title></rect>
        <rect x={franja(1)[0]} y={m.arriba} width={franja(1)[1] - franja(1)[0]} height={h}
              fill="rgb(167 139 250 / 11%)"><title>μ ± 1σ: el 68 % de los tickets si fuera normal</title></rect>
      </>}
      {marcas.map((v) => <g key={v}>
        <line x1={m.izq} x2={m.izq + w} y1={y(v)} y2={y(v)} stroke={COLORES.grilla} />
        <text x={m.izq - 8} y={y(v) + 4} textAnchor="end" className="eje">{v}</text>
      </g>)}
      {clases.map((c) => {
        const x0 = x(c.desde) + 1.5
        const ancho = Math.max(x(c.hasta) - x(c.desde) - 3, 1)
        return <rect key={c.desde} x={x0} y={y(c.cantidad)} width={ancho} height={base - y(c.cantidad)}
                     rx="3" fill="url(#gauss-barras)">
          <title>{`${pesos(c.desde)} a ${pesos(c.hasta)}: ${c.cantidad} ventas`}</title>
        </rect>
      })}
      {curva.length > 1 && <>
        <path d={area} fill="url(#gauss-area)" />
        <polyline points={linea} fill="none" stroke={COLORES.amarillo} strokeWidth="3"
                  strokeLinejoin="round" strokeLinecap="round" />
      </>}
      {media != null && <>
        <line x1={x(media)} x2={x(media)} y1={m.arriba - 6} y2={base} stroke={COLORES.exito}
              strokeDasharray="6 4" strokeWidth="2"><title>{`Media: ${pesos(media)}`}</title></line>
        <text x={x(media)} y={m.arriba - 10} textAnchor="middle" className="eje etiqueta-media">
          μ = {pesos(media)}</text>
      </>}
      {desvio > 0 && [-2, -1, 1, 2].map((k) => {
        const v = media + k * desvio
        if (v < xMin || v > xMax) return null
        return <text key={k} x={x(v)} y={base + 30} textAnchor="middle" className="eje eje-sigma">
          {k > 0 ? `+${k}σ` : `${k}σ`}</text>
      })}
      {[0, 0.25, 0.5, 0.75, 1].map((f) => {
        const v = xMin + (xMax - xMin) * f
        return <text key={f} x={x(v)} y={base + 16} textAnchor="middle" className="eje">{pesos(v)}</text>
      })}
    </svg>
  )
}
