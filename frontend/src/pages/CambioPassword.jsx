import { useState } from 'react'
import { api } from '../api.js'

// Pantalla obligatoria: aparece cuando la cuenta tiene una contraseña temporal.
// El backend bloquea todo lo demás hasta que se complete.
export default function CambioPassword({ usuario, onCambiada, onSalir }) {
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)

  const coinciden = nueva === repetida
  const valida = nueva.length >= 8 && coinciden && nueva !== actual

  const enviar = async (evento) => {
    evento.preventDefault()
    setError('')
    setGuardando(true)
    try {
      onCambiada(await api.cambiarPassword(actual, nueva))
    } catch (e) {
      setError(e.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <main className="acceso">
      <form className="tarjeta acceso-formulario" onSubmit={enviar}>
        <span className="aviso-icono" aria-hidden="true">🔒</span>
        <h2>Cambio de contraseña obligatorio</h2>
        <p className="ayuda">
          Hola {usuario.email}. Entraste con una contraseña temporal: elegí una propia
          para poder usar el sistema.
        </p>
        {error && <div className="error" role="alert">{error}</div>}
        <label>Contraseña temporal
          <input type="password" autoComplete="current-password" required value={actual}
                 onChange={(e) => setActual(e.target.value)} />
        </label>
        <label>Nueva contraseña (mínimo 8 caracteres)
          <input type="password" autoComplete="new-password" required minLength={8}
                 value={nueva} onChange={(e) => setNueva(e.target.value)} />
        </label>
        <label>Repetí la nueva contraseña
          <input type="password" autoComplete="new-password" required value={repetida}
                 onChange={(e) => setRepetida(e.target.value)} />
        </label>
        {repetida && !coinciden && <p className="ayuda">Las contraseñas no coinciden.</p>}
        {nueva && nueva === actual && (
          <p className="ayuda">La nueva tiene que ser distinta de la temporal.</p>
        )}
        <button disabled={!valida || guardando}>
          {guardando ? 'Guardando…' : 'Guardar y continuar'}
        </button>
        <button className="link" type="button" onClick={onSalir}>Cerrar sesión</button>
      </form>
    </main>
  )
}
