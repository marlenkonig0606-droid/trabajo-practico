import { useEffect, useState } from 'react'
import { api } from '../api.js'
import SelectorRol from '../components/SelectorRol.jsx'

export default function Acceso({ onAuthenticated }) {
  const [modo, setModo] = useState('login')
  const [sucursales, setSucursales] = useState([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [sucursalId, setSucursalId] = useState('')
  const [codigoCd, setCodigoCd] = useState('')
  const [rol, setRol] = useState('EMPLEADO')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  // Aviso de cuenta no habilitada: { estado: 'PENDIENTE' | 'RECHAZADO', mensaje, motivo }
  const [aviso, setAviso] = useState(null)

  useEffect(() => {
    api.sucursales().then(setSucursales).catch((e) => setError(e.message))
  }, [])

  const tipoSucursal = sucursales.find((s) => s.id === Number(sucursalId))?.tipo

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setCargando(true)
    try {
      if (modo === 'registro') {
        const respuesta = await api.registrar({
          email,
          password,
          sucursal_id: Number(sucursalId),
          ...(tipoSucursal === 'CD' ? { codigo_cd: codigoCd } : { rol }),
        })
        // Los usuarios de local quedan pendientes: no se inicia sesión.
        if (respuesta.pendiente) {
          setAviso({ estado: 'PENDIENTE', mensaje: respuesta.mensaje })
          return
        }
        onAuthenticated(respuesta)
      } else {
        onAuthenticated(await api.iniciarSesion({ email, password }))
      }
    } catch (e) {
      if (e.status === 403 && e.datos?.estado) {
        setAviso({ estado: e.datos.estado, mensaje: e.message, motivo: e.datos.motivo })
      } else {
        setError(e.message)
      }
    } finally {
      setCargando(false)
    }
  }

  const volver = () => {
    setAviso(null)
    setModo('login')
    setPassword('')
  }

  return (
    <main className="acceso">
      {aviso ? (
        <AvisoCuenta aviso={aviso} onVolver={volver} />
      ) : (
      <form className="tarjeta acceso-formulario" onSubmit={enviar}>
        <div className="acceso-marca">
          <span className="marca-indicador" aria-hidden="true" />
          <div>
            <h1>CYBER-WAREHOUSE</h1>
            <p>CENTRO DE DISTRIBUCIÓN <span>·</span> SISTEMA OPERATIVO</p>
          </div>
        </div>
        <h2>{modo === 'login' ? 'Iniciar sesión' : 'Crear cuenta'}</h2>
        <p className="vacio">
          Ingresá para consultar la información habilitada para tu sucursal.
        </p>
        {error && <div className="error">{error}</div>}
        <label>Correo electrónico
          <input type="email" autoComplete="username" required value={email}
                 onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>Contraseña
          <input type="password"
                 autoComplete={modo === 'login' ? 'current-password' : 'new-password'}
                 minLength={modo === 'registro' ? 8 : undefined}
                 required value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </label>
        {modo === 'registro' && (
          <label>Tu sucursal
            <select required value={sucursalId} onChange={(e) => setSucursalId(e.target.value)}>
              <option value="">Elegí tu sucursal…</option>
              {sucursales.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.nombre} ({s.tipo === 'CD' ? 'Centro de distribución' : 'Local'})
                </option>
              ))}
            </select>
          </label>
        )}
        {modo === 'registro' && tipoSucursal === 'LOCAL' && (
          <SelectorRol valor={rol} onCambiar={setRol} titulo="Perfil que solicitás"
                       ayuda="El administrador de tu local revisa la solicitud y confirma el perfil." />
        )}
        {modo === 'registro' && tipoSucursal === 'CD' && (
            <label>Código de invitación del CD
              <input type="password" autoComplete="off" required value={codigoCd}
                     onChange={(e) => setCodigoCd(e.target.value)} />
            </label>
          )}
        <button disabled={cargando || (modo === 'registro' && !sucursalId)}>
          {cargando ? 'Un momento…' : modo === 'login' ? 'Iniciar sesión' : 'Registrarme'}
        </button>
        <button className="link" type="button" onClick={() => {
          setModo(modo === 'login' ? 'registro' : 'login')
          setError('')
        }}>
          {modo === 'login' ? '¿No tenés cuenta? Registrate' : 'Ya tengo cuenta'}
        </button>
        <p className="ayuda">
          Las cuentas de local quedan pendientes hasta que las apruebe el administrador
          del local. Para registrar una cuenta del CD necesitás el código de invitación.
        </p>
      </form>
      )}
    </main>
  )
}

// Pantalla que ve el empleado mientras su cuenta no está habilitada.
function AvisoCuenta({ aviso, onVolver }) {
  const rechazada = aviso.estado === 'RECHAZADO'
  return (
    <section className={`tarjeta acceso-formulario aviso-cuenta ${rechazada ? 'rechazada' : ''}`}
             role="status">
      <span className="aviso-icono" aria-hidden="true">{rechazada ? '✕' : '⏳'}</span>
      <h2>{rechazada ? 'Cuenta rechazada' : 'Cuenta pendiente de validación'}</h2>
      <p>{aviso.mensaje}</p>
      {rechazada && aviso.motivo && <p className="ayuda">Motivo: {aviso.motivo}</p>}
      {!rechazada && (
        <ol className="aviso-pasos">
          <li>El administrador de tu local revisa tu solicitud.</li>
          <li>Al aprobarla, te entrega una contraseña temporal.</li>
          <li>Entrás con esa contraseña y elegís una nueva.</li>
        </ol>
      )}
      <button type="button" onClick={onVolver}>Volver al inicio de sesión</button>
    </section>
  )
}
