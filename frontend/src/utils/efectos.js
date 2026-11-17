// Efectos visuales puramente decorativos (solo frontend).
// Se dibujan sobre un <canvas> temporal que cubre la pantalla, no bloquea
// clics y se elimina solo al terminar la animación.

const COLORES_CONFETI = ['#f94144', '#f3722c', '#f9c74f', '#90be6d', '#43aa8b', '#577590', '#9b5de5']

function animar(crearParticula, cantidad, duracionMs) {
  // Respeta la preferencia del sistema operativo de "reducir movimiento".
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

  const canvas = document.createElement('canvas')
  Object.assign(canvas.style, {
    position: 'fixed', inset: '0', width: '100vw', height: '100vh',
    pointerEvents: 'none', zIndex: '9999',
  })
  canvas.width = window.innerWidth
  canvas.height = window.innerHeight
  document.body.appendChild(canvas)
  const ctx = canvas.getContext('2d')

  const particulas = Array.from({ length: cantidad }, () => crearParticula(canvas))
  const inicio = performance.now()

  const cuadro = (ahora) => {
    const transcurrido = ahora - inicio
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    ctx.globalAlpha = Math.max(0, 1 - Math.max(0, transcurrido - duracionMs * 0.7) / (duracionMs * 0.3))
    for (const p of particulas) {
      p.vy += p.gravedad
      p.vx *= 0.99
      p.x += p.vx
      p.y += p.vy
      p.angulo += p.giro
      p.dibujar(ctx, p)
    }
    if (transcurrido < duracionMs) requestAnimationFrame(cuadro)
    else canvas.remove()
  }
  requestAnimationFrame(cuadro)
}

/** Lluvia de confeti: se usa al registrar una venta. */
export function festejarVenta() {
  animar((canvas) => ({
    x: canvas.width / 2 + (Math.random() - 0.5) * 200,
    y: canvas.height * 0.6,
    vx: (Math.random() - 0.5) * 18,
    vy: -(Math.random() * 14 + 8),
    gravedad: 0.35,
    angulo: Math.random() * Math.PI,
    giro: (Math.random() - 0.5) * 0.3,
    ancho: 6 + Math.random() * 6,
    alto: 10 + Math.random() * 8,
    color: COLORES_CONFETI[Math.floor(Math.random() * COLORES_CONFETI.length)],
    dibujar(ctx, p) {
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.angulo)
      ctx.fillStyle = p.color
      ctx.fillRect(-p.ancho / 2, -p.alto / 2, p.ancho, p.alto)
      ctx.restore()
    },
  }), 180, 3000)
}

/** Caritas tristes que caen desde arriba: se usa al registrar una devolución. */
export function lamentarDevolucion() {
  animar((canvas) => ({
    x: Math.random() * canvas.width,
    y: -40 - Math.random() * canvas.height * 0.5,
    vx: (Math.random() - 0.5) * 1.5,
    vy: Math.random() * 2 + 1,
    gravedad: 0.05,
    angulo: (Math.random() - 0.5) * 0.6,
    giro: (Math.random() - 0.5) * 0.02,
    tamano: 28 + Math.random() * 20,
    dibujar(ctx, p) {
      ctx.save()
      ctx.translate(p.x, p.y)
      ctx.rotate(p.angulo)
      ctx.font = `${p.tamano}px serif`
      ctx.textAlign = 'center'
      ctx.fillText('😢', 0, 0)
      ctx.restore()
    },
  }), 35, 3500)
}
