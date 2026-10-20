import { useEffect, useState } from 'react'
import Logistica from './pages/Logistica.jsx'
import Stock from './pages/Stock.jsx'
import Reportes from './pages/Reportes.jsx'
import Catalogo from './pages/Catalogo.jsx'
import Ventas from './pages/Ventas.jsx'
import Acceso from './pages/Acceso.jsx'
import Solicitudes from './pages/Solicitudes.jsx'
import { api } from './api.js'

export default function App() {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [actual, setActual] = useState('logistica')

  const iniciar = (sesion) => {
    setUsuario(sesion)
    setActual(sesion.tipo === 'CD' ? 'logistica' : 'stock')
  }

  useEffect(() => {
    api.sesion()
      .then(iniciar)
      .catch((e) => {
        if (e.status !== 401) setError(e.message)
      })
      .finally(() => setCargando(false))
  }, [])

  const cerrarSesion = async () => {
    setError('')
    try {
      await api.cerrarSesion()
      setUsuario(null)
    } catch (e) {
      setError(e.message)
    }
  }

  if (cargando) return <main className="acceso"><p>Cargando…</p></main>
  if (!usuario) {
    return <>
      {error && <div className="error">{error}</div>}
      <Acceso onAuthenticated={iniciar} />
    </>
  }

  const secciones = [
    ...(usuario.tipo === 'CD'
      ? [
        { id: 'logistica', titulo: 'Logística', componente: <Logistica /> },
        { id: 'abm', titulo: 'Catálogo', componente: <Catalogo /> },
      ]
      : [{
        id: 'solicitudes',
        titulo: 'Reposición',
        componente: <Solicitudes usuario={usuario} />,
      },
      { id: 'ventas', titulo: 'Ventas', componente: <Ventas usuario={usuario} /> }]),
    { id: 'stock', titulo: 'Stock', componente: <Stock usuario={usuario} /> },
    { id: 'reportes', titulo: 'Reportes', componente: <Reportes usuario={usuario} /> },
  ]
  const paginaActual = secciones.find((seccion) => seccion.id === actual) ?? secciones[0]

  return (
    <div className="app">
      <header>
        <h1>CD → Locales</h1>
        <nav>
          {secciones.map((s) => (
            <button key={s.id} className={actual === s.id ? 'activo' : ''}
                    onClick={() => setActual(s.id)}>{s.titulo}</button>
          ))}
          <span className="sesion-usuario">{usuario.email} · {usuario.sucursal}</span>
          <button className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
        </nav>
      </header>
      {error && <div className="error">{error}</div>}
      <main>{paginaActual.componente}</main>
    </div>
  )
}
