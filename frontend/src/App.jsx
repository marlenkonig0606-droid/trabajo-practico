import { useEffect, useState } from 'react'
import Logistica from './pages/Logistica.jsx'
import Stock from './pages/Stock.jsx'
import ReportesCD from './pages/ReportesCD.jsx'
import ReportesLocal from './pages/ReportesLocal.jsx'
import Catalogo from './pages/Catalogo.jsx'
import Ventas from './pages/Ventas.jsx'
import Acceso from './pages/Acceso.jsx'
import Solicitudes from './pages/Solicitudes.jsx'
import MiLocal from './pages/MiLocal.jsx'
import ProductosLocal from './pages/ProductosLocal.jsx'
import CambioPassword from './pages/CambioPassword.jsx'
import { api } from './api.js'

export default function App() {
  const [usuario, setUsuario] = useState(null)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [actual, setActual] = useState('logistica')

  const iniciar = (sesion) => {
    setUsuario(sesion)
    setActual(sesion.tipo === 'CD' ? 'logistica'
      : sesion.rol === 'ADMINISTRADOR' ? 'milocal' : 'stock')
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

  // Contraseña temporal: hasta cambiarla no puede usar nada más.
  if (usuario.debe_cambiar_password) {
    return <CambioPassword usuario={usuario} onCambiada={iniciar} onSalir={cerrarSesion} />
  }

  const esAdminLocal = usuario.tipo === 'LOCAL' && usuario.rol === 'ADMINISTRADOR'
  const esEmpleado = usuario.tipo === 'LOCAL' && usuario.rol === 'EMPLEADO'

  const secciones = [
    ...(esAdminLocal
      ? [{ id: 'milocal', titulo: 'Mi local', componente: <MiLocal usuario={usuario} /> }]
      : []),
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
      { id: 'ventas', titulo: 'Ventas', componente: <Ventas usuario={usuario} /> },
      { id: 'productos', titulo: 'Productos', componente: <ProductosLocal usuario={usuario} /> }]),
    { id: 'stock', titulo: 'Stock', componente: <Stock usuario={usuario} /> },
    // RBAC: el empleado no ve reportes (el backend también lo bloquea).
    ...(esEmpleado
      ? []
      : [{
        id: 'reportes',
        titulo: 'Reportes',
        // El local ve su reporte gerencial; el CD ve el de la red y puede
        // abrir el de cualquier local (misma plantilla) o el detalle operativo.
        componente: usuario.tipo === 'LOCAL'
          ? <ReportesLocal usuario={usuario} />
          : <ReportesCD usuario={usuario} />,
      }]),
  ]
  const paginaActual = secciones.find((seccion) => seccion.id === actual) ?? secciones[0]

  return (
    <div className="app">
      <header className="topbar">
        <div className="marca">
          <span className="marca-indicador" aria-hidden="true" />
          <div>
            <h1>CYBER-WAREHOUSE</h1>
            <p>CENTRO DE DISTRIBUCIÓN <span>·</span> SISTEMA OPERATIVO</p>
          </div>
        </div>
        <nav>
          {secciones.map((s) => (
            <button key={s.id} className={actual === s.id ? 'activo' : ''}
                    onClick={() => setActual(s.id)}>{s.titulo}</button>
          ))}
          <span className="sesion-usuario"><i aria-hidden="true" />{usuario.email} · {usuario.sucursal}</span>
          <button className="secundario" onClick={cerrarSesion}>Cerrar sesión</button>
        </nav>
      </header>
      {error && <div className="error">{error}</div>}
      <main>{paginaActual.componente}</main>
    </div>
  )
}
