import { useEffect, useState } from 'react'
import { api } from '../api.js'
import SelectorProductos from '../components/SelectorProductos.jsx'

export default function Solicitudes({ usuario }) {
  const [productos, setProductos] = useState([])
  const [sucursales, setSucursales] = useState([])
  const [ordenes, setOrdenes] = useState([])
  const [origenId, setOrigenId] = useState('')
  const [cantidades, setCantidades] = useState({})
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [cargando, setCargando] = useState(true)

  const recargar = async () => {
    const [listaOrdenes, listaProductos, listaSucursales] = await Promise.all([
      api.ordenes(), api.productos(), api.sucursales(),
    ])
    setOrdenes(listaOrdenes)
    setProductos(listaProductos)
    setSucursales(listaSucursales)
  }

  useEffect(() => {
    recargar()
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }, [])

  useEffect(() => {
    const centros = sucursales.filter((s) => s.tipo === 'CD')
    if (!origenId && centros.length) setOrigenId(String(centros[0].id))
  }, [sucursales, origenId])

  const solicitar = async () => {
    setError('')
    setMensaje('')
    const items = Object.entries(cantidades)
      .filter(([, cantidad]) => Number(cantidad) > 0)
      .map(([productoId, cantidad]) => ({
        producto_id: Number(productoId),
        cantidad: Number(cantidad),
      }))
    try {
      await api.solicitarOrden(Number(origenId), usuario.sucursal_id, items)
      setCantidades({})
      await recargar()
      setMensaje('Solicitud enviada al centro de distribución.')
    } catch (e) {
      setError(e.message)
    }
  }

  const recibir = async (bultoId) => {
    setError('')
    setMensaje('')
    try {
      await api.recibir(bultoId)
      await recargar()
      setMensaje('Recepción confirmada. Ahora verificá el remito y el precinto.')
    } catch (e) {
      setError(e.message)
    }
  }

  const verificar = async (bultoId, aprobado) => {
    setError('')
    setMensaje('')
    try {
      const resultado = await api.verificarRecepcion(bultoId, aprobado)
      await recargar()
      setMensaje(resultado.estado === 'VERIFICADO'
        ? 'Bulto verificado. El stock se actualizará al finalizar la verificación de todos los bultos.'
        : 'Bulto rechazado. Sus productos no se suman al stock.')
    } catch (e) {
      setError(e.message)
    }
  }

  const sugerir = async () => {
    setError('')
    try {
      const items = await api.sugerirOrden(usuario.sucursal_id)
      setCantidades(Object.fromEntries(
        items.map((item) => [item.producto_id, String(item.cantidad)]),
      ))
      if (items.length === 0) setMensaje('Tu stock disponible ya alcanza los mínimos.')
    } catch (e) {
      setError(e.message)
    }
  }

  return (
    <section>
      {error && <div className="error">{error}</div>}
      {mensaje && <div className="exito">{mensaje}</div>}
      <div className="tarjeta">
        <h2>Solicitar reposición</h2>
        <p className="ayuda">
          Elegí el CD de origen y los productos. El destino es tu sucursal, {usuario.sucursal}.
          La solicitud queda pendiente hasta que el CD la prepare y despache.
        </p>
        <div className="grilla">
          <label>Origen · Centro de distribución
            <select value={origenId} onChange={(e) => setOrigenId(e.target.value)}>
              <option value="">Elegí un CD…</option>
                {sucursales.filter((s) => s.tipo === 'CD').map((s) =>
                  <option key={s.id} value={s.id}>{s.nombre}</option>)}
            </select>
            </label>
            <div className="destino-propio"><span>Destino · Local</span>
              <strong>{usuario.sucursal}</strong>
            </div>
        </div>
        <SelectorProductos productos={productos} cantidades={cantidades}
                             onChange={setCantidades} />
        <div className="acciones-formulario">
            <button className="secundario" onClick={sugerir}>Sugerir según stock mínimo</button>
            <button disabled={!origenId
              || !Object.values(cantidades).some((cantidad) => Number(cantidad) > 0)}
                    onClick={solicitar}>Enviar solicitud</button>
        </div>
      </div>

      <h2>Solicitudes y recepciones · {usuario.sucursal}</h2>
      {cargando && <p className="vacio">Cargando solicitudes…</p>}
      {!cargando && ordenes.length === 0 && (
        <p className="vacio">Todavía no hay solicitudes para esta sucursal.</p>
      )}
      {ordenes.map((orden) => (
        <OrdenLocal key={orden.id} orden={orden} productos={productos}
                    sucursalId={usuario.sucursal_id}
                    onRecibir={recibir} onVerificar={verificar} />
      ))}
    </section>
  )
}

function OrdenLocal({ orden, productos, sucursalId, onRecibir, onVerificar }) {
  const puedeRecibir = orden.destino_id === sucursalId

  return (
    <div className="tarjeta">
      <div className="fila-titulo">
        <strong>Solicitud #{orden.id}</strong>
        <span>{orden.origen} → {orden.destino}</span>
        <span className={`estado ${orden.estado}`}>{orden.estado}</span>
        {orden.remito_numero && (
          <span>Remito {orden.remito_numero} · {orden.remito_estado}</span>
        )}
      </div>
      <table>
        <thead><tr><th>Producto</th><th>Solicitado</th><th>Enviado</th></tr></thead>
        <tbody>
          {orden.items.map((item) => (
            <tr key={item.producto_id}>
              <td>{item.nombre}</td>
              <td>{item.cantidad}</td>
              <td>{item.empaquetado}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {orden.bultos.map((bulto) => (
        <BultoLocal key={bulto.id} bulto={bulto} remitoNumero={orden.remito_numero}
                    productos={productos}
                    puedeRecibir={puedeRecibir}
                    onRecibir={onRecibir} onVerificar={onVerificar} />
      ))}
      {!puedeRecibir && (
        <p className="ayuda">La recepción y verificación corresponden al local destinatario.</p>
      )}
      {orden.remito_estado === 'VERIFICADO' && (
        <p className="exito">Remito verificado: el stock recibido ya está disponible.</p>
      )}
      {orden.remito_estado === 'RECHAZADO' && (
        <p className="error">Remito rechazado: solo se incorporan al stock los bultos verificados.</p>
      )}
    </div>
  )
}

function BultoLocal({
  bulto, remitoNumero, productos, puedeRecibir, onRecibir, onVerificar,
}) {
  const nombreProducto = (id) => productos.find((p) => p.id === id)?.nombre ?? `#${id}`

  return (
    <div className="bulto">
      <strong>Bulto #{bulto.id}</strong>
      <span className={`estado ${bulto.estado}`}>{bulto.estado}</span>
      {bulto.precinto && <span>Precinto esperado: {bulto.precinto}</span>}
      <span className="items">
        {bulto.items.map((item) =>
          `${item.cantidad} × ${nombreProducto(item.producto_id)}`).join(', ')}
      </span>
      {puedeRecibir && bulto.estado === 'EN_TRANSITO' && (
        <div className="recepcion-bulto">
          <p>Confirmá primero que el bulto llegó al local.</p>
          <button onClick={() => onRecibir(bulto.id)}>Confirmar recepción</button>
        </div>
      )}
      {puedeRecibir && bulto.estado === 'RECIBIDO' && (
        <div className="recepcion-bulto">
          <p>Recepción confirmada. Compará el remito y el precinto con los datos esperados y elegí:</p>
          <div className="acciones-verificacion">
            <button onClick={() => onVerificar(bulto.id, true)}>Verificar</button>
            <button className="peligro" onClick={() => onVerificar(bulto.id, false)}>
              Rechazar
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
