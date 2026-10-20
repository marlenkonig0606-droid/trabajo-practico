import { useEffect, useState } from 'react'
import { api } from '../api.js'

export default function Acceso({ onAuthenticated }) {
  const [modo, setModo] = useState('login')
  const [sucursales, setSucursales] = useState([])
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [sucursalId, setSucursalId] = useState('')
  const [codigoCd, setCodigoCd] = useState('')
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  useEffect(() => {
    api.sucursales().then(setSucursales).catch((e) => setError(e.message))
  }, [])

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setCargando(true)
    try {
      const usuario = modo === 'registro'
        ? await api.registrar({
          email,
          password,
          sucursal_id: Number(sucursalId),
          ...(sucursales.find((s) => s.id === Number(sucursalId))?.tipo === 'CD'
            ? { codigo_cd: codigoCd }
            : {}),
        })
        : await api.iniciarSesion({ email, password })
      onAuthenticated(usuario)
    } catch (e) {
      setError(e.message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <main className="acceso">
      <form className="tarjeta acceso-formulario" onSubmit={enviar}>
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
        {modo === 'registro'
          && sucursales.find((s) => s.id === Number(sucursalId))?.tipo === 'CD' && (
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
          Para registrar una cuenta del CD necesitás el código de invitación.
        </p>
      </form>
    </main>
  )
}
