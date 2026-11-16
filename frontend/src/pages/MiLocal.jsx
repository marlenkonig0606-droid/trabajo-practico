import { useEffect, useState } from 'react'
import { api } from '../api.js'
import SelectorRol from '../components/SelectorRol.jsx'
import { BotonIcono, BotonPrincipal } from '../components/UI.jsx'
import { formatearFecha } from '../utils/fechas.js'

const pesos = (n) => `$${Number(n ?? 0).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`

// Panel del ADMINISTRADOR del local: ve todo lo del local y gestiona su equipo.
export default function MiLocal({ usuario }) {
  const [panel, setPanel] = useState(null)
  const [equipo, setEquipo] = useState([])
  const [rolesElegidos, setRolesElegidos] = useState({})
  const [motivos, setMotivos] = useState({})
  const [credencial, setCredencial] = useState(null)
  const [nuevoEmail, setNuevoEmail] = useState('')
  const [nuevoRol, setNuevoRol] = useState('EMPLEADO')
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [ocupado, setOcupado] = useState(null)

  const recargar = async () => {
    const [datosPanel, lista] = await Promise.all([api.panelLocal(), api.equipoLocal()])
    setPanel(datosPanel)
    setEquipo(lista)
  }

  useEffect(() => {
    recargar().catch((e) => setError(e.message))
  }, [])

  const ejecutar = async (clave, accion) => {
    setError('')
    setMensaje('')
    setCredencial(null)
    setOcupado(clave)
    try {
      await accion()
      await recargar()
    } catch (e) {
      setError(e.message)
    } finally {
      setOcupado(null)
    }
  }

  const aprobar = (u) => ejecutar(`a${u.id}`, async () => {
    const r = await api.aprobarUsuario(u.id, rolesElegidos[u.id] ?? u.rol)
    setCredencial({ email: u.email, password: r.password_temporal, rol: r.usuario.rol })
  })

  const rechazar = (u) => ejecutar(`r${u.id}`, async () => {
    await api.rechazarUsuario(u.id, motivos[u.id] ?? '')
    setMensaje(`Se rechazó la cuenta de ${u.email}.`)
  })

  const alta = (evento) => {
    evento.preventDefault()
    ejecutar('alta', async () => {
      const r = await api.altaUsuarioLocal(nuevoEmail, nuevoRol)
      setCredencial({ email: r.usuario.email, password: r.password_temporal, rol: r.usuario.rol })
      setNuevoEmail('')
    })
  }

  const pendientes = equipo.filter((u) => u.estado === 'PENDIENTE')
  const resueltos = equipo.filter((u) => u.estado !== 'PENDIENTE')

  return (
    <>
      {error && <div className="error" role="alert">{error}</div>}
      {mensaje && <div className="exito" role="status">{mensaje}</div>}
      {credencial && <CredencialTemporal {...credencial} onCerrar={() => setCredencial(null)} />}

      <section className="tarjeta">
        <h2>Mi local · {usuario.sucursal}</h2>
        <p className="ayuda">Todo lo que pasa en tu local, de un vistazo.</p>
        {!panel ? <p className="vacio">Cargando…</p> : (
          <div className="resumen-indicadores">
            <div><span>Ventas de hoy</span>
              <strong>{pesos(panel.ventas_hoy.total)}</strong>
              <span>{panel.ventas_hoy.cantidad} ventas</span></div>
            <div><span>Ventas del mes</span>
              <strong>{pesos(panel.ventas_mes.total)}</strong>
              <span>{panel.ventas_mes.cantidad} ventas</span></div>
            <div><span>Productos bajo el mínimo</span>
              <strong>{panel.alertas_stock}</strong></div>
            <div><span>Órdenes de reposición abiertas</span>
              <strong>{panel.ordenes_abiertas}</strong></div>
            <div><span>Bultos en camino / sin verificar</span>
              <strong>{panel.bultos_en_camino} / {panel.bultos_sin_verificar}</strong></div>
            <div><span>Equipo</span>
              <strong>{panel.equipo.administradores} admin. · {panel.equipo.empleados} empl.</strong>
              <span>{panel.equipo.pendientes} pendientes · {panel.equipo.rechazados} rechazados</span></div>
          </div>
        )}
      </section>

      <section className="tarjeta">
        <h2>Solicitudes pendientes ({pendientes.length})</h2>
        <p className="ayuda">
          Hasta que no apruebes una cuenta, esa persona no puede entrar al sistema.
          Al aprobarla se genera una contraseña temporal que tenés que entregarle.
        </p>
        {pendientes.length === 0 ? <p className="vacio">No hay solicitudes pendientes.</p> : (
          <table>
            <thead><tr><th>Correo</th><th>Fecha</th><th>Perfil a asignar</th>
              <th>Motivo (si rechazás)</th><th>Acciones</th></tr></thead>
            <tbody>
              {pendientes.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}</td>
                  <td>{formatearFecha(u.fecha_alta)}</td>
                  <td>
                    <SelectorRol compacto titulo={`Perfil ${u.id}`}
                                 valor={rolesElegidos[u.id] ?? u.rol}
                                 onCambiar={(rol) => setRolesElegidos({ ...rolesElegidos, [u.id]: rol })} />
                  </td>
                  <td>
                    <input aria-label={`Motivo de rechazo de ${u.email}`} value={motivos[u.id] ?? ''}
                           onChange={(e) => setMotivos({ ...motivos, [u.id]: e.target.value })} />
                  </td>
                  <td className="acciones">
                    <BotonIcono icono="aprobar" etiqueta="Aprobar y generar contraseña temporal"
                                tono="exito" disabled={ocupado !== null} onClick={() => aprobar(u)} />
                    <BotonIcono icono="rechazar" etiqueta="Rechazar solicitud" tono="peligro"
                                disabled={ocupado !== null} onClick={() => rechazar(u)} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="tarjeta">
        <h2>Dar de alta un perfil</h2>
        <form className="alta-perfil" onSubmit={alta}>
          <label>Correo electrónico
            <input type="email" required value={nuevoEmail}
                   onChange={(e) => setNuevoEmail(e.target.value)} />
          </label>
          <SelectorRol valor={nuevoRol} onCambiar={setNuevoRol} titulo="Perfil del nuevo usuario" />
          <BotonPrincipal type="submit" disabled={ocupado !== null}>Crear perfil con contraseña temporal</BotonPrincipal>
        </form>
      </section>

      <section className="tarjeta">
        <h2>Equipo del local</h2>
        {resueltos.length === 0 ? <p className="vacio">Todavía no hay cuentas resueltas.</p> : (
          <table>
            <thead><tr><th>Correo</th><th>Perfil</th><th>Estado</th>
              <th>Resuelto por</th><th>Observaciones</th></tr></thead>
            <tbody>
              {resueltos.map((u) => (
                <tr key={u.id}>
                  <td>{u.email}{u.id === usuario.id && ' (vos)'}</td>
                  <td><span className={`insignia-rol ${u.rol.toLowerCase()}`}>
                    {u.rol === 'ADMINISTRADOR' ? 'Administrador' : 'Empleado'}</span></td>
                  <td>{u.estado === 'APROBADO' ? 'Aprobado' : 'Rechazado'}</td>
                  <td>{u.resuelto_por ?? '—'}</td>
                  <td>{u.estado === 'RECHAZADO'
                    ? (u.motivo_rechazo ?? 'Sin motivo')
                    : u.debe_cambiar_password ? 'Todavía no cambió la contraseña temporal' : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>
    </>
  )
}

// Se muestra UNA sola vez: el sistema no guarda la contraseña temporal en texto.
function CredencialTemporal({ email, password, rol, onCerrar }) {
  return (
    <section className="tarjeta credencial-temporal" role="status">
      <h2>Contraseña temporal generada</h2>
      <p>Entregale estos datos a <b>{email}</b> ({rol === 'ADMINISTRADOR' ? 'Administrador' : 'Empleado'}).
        Al entrar, el sistema le va a pedir que la cambie.</p>
      <code>{password}</code>
      <p className="ayuda">Copiala ahora: por seguridad no se vuelve a mostrar.</p>
      <button className="secundario" onClick={onCerrar}>Listo</button>
    </section>
  )
}
