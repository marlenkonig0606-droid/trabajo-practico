const COLORES_CONFETI = ['#f94144', '#f3722c', '#f9c74f', '#90be6d', '#43aa8b', '#577590', '#9b5de5']

function animar(crearParticula, cantidad, duracionMs) {
  if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) return

  const escala = window.devicePixelRatio || 1
  const ancho = window.innerWidth
  const alto = window.innerHeight
  const canvas = document.createElement('canvas')
  Object.assign(canvas.style, {
    position: 'fixed',
    inset: '0',
    width: '100vw',
    height: '100vh',
    pointerEvents: 'none',
    zIndex: '9999',
  })
  canvas.width = ancho * escala
  canvas.height = alto * escala
  const contexto = canvas.getContext('2d')
  if (!contexto) return

  contexto.scale(escala, escala)
  document.body.appendChild(canvas)
  const particulas = Array.from({ length: cantidad }, () => crearParticula(ancho, alto))
  const inicio = performance.now()

  const dibujar = (ahora) => {
    const transcurrido = ahora - inicio
    contexto.clearRect(0, 0, ancho, alto)
    contexto.globalAlpha = Math.max(0, 1 - transcurrido / duracionMs)

    particulas.forEach((particula) => {
      particula.vy += particula.gravedad
      particula.vx *= 0.99
      particula.x += particula.vx
      particula.y += particula.vy
      particula.angulo += particula.giro
      particula.dibujar(contexto)
    })

    if (transcurrido < duracionMs) requestAnimationFrame(dibujar)
    else canvas.remove()
  }

  requestAnimationFrame(dibujar)
}

export function festejarVenta() {
  animar((ancho, alto) => ({
    x: ancho / 2 + (Math.random() - 0.5) * 180,
    y: alto * 0.65,
    vx: (Math.random() - 0.5) * 16,
    vy: -(Math.random() * 12 + 6),
    gravedad: 0.3,
    angulo: Math.random() * Math.PI,
    giro: (Math.random() - 0.5) * 0.25,
    ancho: 5 + Math.random() * 6,
    alto: 8 + Math.random() * 8,
    color: COLORES_CONFETI[Math.floor(Math.random() * COLORES_CONFETI.length)],
    dibujar(ctx) {
      ctx.save()
      ctx.translate(this.x, this.y)
      ctx.rotate(this.angulo)
      ctx.fillStyle = this.color
      ctx.fillRect(-this.ancho / 2, -this.alto / 2, this.ancho, this.alto)
      ctx.restore()
    },
  }), 160, 2800)
}

export function lamentarDevolucion() {
  animar((ancho, alto) => ({
    x: Math.random() * ancho,
    y: -40 - Math.random() * alto * 0.5,
    vx: (Math.random() - 0.5) * 1.5,
    vy: Math.random() * 2 + 1,
    gravedad: 0.04,
    angulo: (Math.random() - 0.5) * 0.4,
    giro: (Math.random() - 0.5) * 0.015,
    tamano: 26 + Math.random() * 18,
    dibujar(ctx) {
      ctx.save()
      ctx.translate(this.x, this.y)
      ctx.rotate(this.angulo)
      ctx.font = `${this.tamano}px serif`
      ctx.textAlign = 'center'
      ctx.textBaseline = 'middle'
      ctx.fillText('😢', 0, 0)
      ctx.restore()
    },
  }), 28, 3200)
}
