import { useEffect, useState } from 'react'
import { api } from '../api.js'

const MEDIOS_PAGO = [
  ['EFECTIVO', 'Efectivo'],
  ['TARJETA_DEBITO', 'Tarjeta de débito'],
  ['TARJETA_CREDITO', 'Tarjeta de crédito'],
  ['TRANSFERENCIA', 'Transferencia'],
]

export default function Ventas() {
  const [sucursales, setSucursales] = useState([])
  const [productos, setProductos] = useState([])
  const [ventas, setVentas] = useState([])
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')
  const [cargando, setCargando] = useState(true)

  const recargar = async () => {
    const [nuevasVentas, nuevasSucursales, nuevosProductos] = await Promise.all([
      api.ventas(), api.sucursales(), api.productos(),
    ])
    setVentas(nuevasVentas)
    setSucursales(nuevasSucursales)
    setProductos(nuevosProductos)
  }

  useEffect(() => {
    recargar()
      .catch((e) => setError(e.message))
      .finally(() => setCargando(false))
  }, [])

  const accion = async (fn, texto) => {
    setError('')
    setMensaje('')
    try {
      await fn()
    } catch (e) {
      setError(e.message)
      return false
    }
    try {
      await recargar()
      setMensaje(texto)
    } catch (e) {
      setError(e.message)
    }
    return true
  }

  return (
    <section>
      {error && <div className="error">{error}</div>}
      {mensaje && <div className="exito">{mensaje}</div>}
      <NuevaVenta
        sucursales={sucursales}
        productos={productos}
        onRegistrar={(datos) => accion(() => api.registrarVenta(datos), 'Venta registrada.')}
      />
      <NuevaDevolucion
        ventas={ventas}
        productos={productos}
        onRegistrar={(datos) => accion(() => api.registrarDevolucion(datos), 'Devolución registrada.')}
      />
      <h2>Ventas registradas</h2>
      {cargando && <p className="vacio">Cargando ventas…</p>}
      {!cargando && ventas.length === 0 && <p className="vacio">Todavía no hay ventas.</p>}
      {ventas.map((venta) => (
        <div className="tarjeta fila-titulo" key={venta.id}>
          <strong>Venta #{venta.id}</strong>
          <span>{venta.sucursal}</span>
          <span>{venta.fecha}</span>
          <span>{venta.medio_pago}</span>
          <span>Comprobante #{venta.comprobante_numero}</span>
          <strong>${Number(venta.total).toFixed(2)}</strong>
        </div>
      ))}
    </section>
  )
}

function NuevaVenta({ sucursales, productos, onRegistrar }) {
  const locales = sucursales.filter((s) => s.tipo === 'LOCAL')
  const [sucursalId, setSucursalId] = useState('')
  const [medioPago, setMedioPago] = useState('EFECTIVO')
  const [cuotas, setCuotas] = useState('1')
  const [cantidades, setCantidades] = useState({})
  const [referencia, setReferencia] = useState('')

  const registrar = async () => {
    const items = Object.entries(cantidades)
      .filter(([, cantidad]) => Number(cantidad) > 0)
      .map(([productoId, cantidad]) => ({
        producto_id: Number(productoId), cantidad: Number(cantidad),
      }))
    const registrada = await onRegistrar({
      sucursal_id: Number(sucursalId),
      items,
      medio_pago: medioPago,
      ...(medioPago === 'TARJETA_CREDITO' ? { cuotas: Number(cuotas) } : {}),
      ...(referencia.trim() ? { referencia: referencia.trim() } : {}),
    })
    if (registrada) {
      setCantidades({})
      setReferencia('')
    }
  }

  return (
    <div className="tarjeta">
      <h2>Registrar venta</h2>
      <div className="grilla">
        <label>Local
          <select value={sucursalId} onChange={(e) => setSucursalId(e.target.value)}>
            <option value="">Elegí un local…</option>
            {locales.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </select>
        </label>
        <label>Medio de pago
          <select value={medioPago} onChange={(e) => setMedioPago(e.target.value)}>
            {MEDIOS_PAGO.map(([valor, titulo]) => <option key={valor} value={valor}>{titulo}</option>)}
          </select>
        </label>
        {medioPago === 'TARJETA_CREDITO' && (
          <label>Cuotas
            <input type="number" min="1" value={cuotas}
                   onChange={(e) => setCuotas(e.target.value)} />
          </label>
        )}
        <label>Referencia (opcional)
          <input value={referencia} onChange={(e) => setReferencia(e.target.value)} />
        </label>
      </div>
      <div className="grilla">
        {productos.map((p) => (
          <label key={p.id}>{p.nombre} · ${Number(p.precio_venta).toFixed(2)}
            <input type="number" min="0" step="1" value={cantidades[p.id] ?? ''}
                   onChange={(e) => setCantidades({ ...cantidades, [p.id]: e.target.value })} />
          </label>
        ))}
      </div>
      <button disabled={!sucursalId || !Object.values(cantidades).some((cantidad) => Number(cantidad) > 0)}
              onClick={registrar}>Cobrar y emitir comprobante</button>
    </div>
  )
}

function NuevaDevolucion({ ventas, productos, onRegistrar }) {
  const [ventaId, setVentaId] = useState('')
  const [venta, setVenta] = useState(null)
  const [cantidades, setCantidades] = useState({})
  const [motivo, setMotivo] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let activa = true
    if (!ventaId) {
      setVenta(null)
      return () => { activa = false }
    }
    api.venta(ventaId)
      .then((detalle) => { if (activa) setVenta(detalle) })
      .catch((e) => { if (activa) setError(e.message) })
    return () => { activa = false }
  }, [ventaId])

  const cantidadDevuelta = (productoId) => (
    venta?.devoluciones
      .filter((d) => d.producto_id === productoId)
      .reduce((total, d) => total + d.cantidad, 0) ?? 0
  )

  const registrar = async () => {
    const items = Object.entries(cantidades)
      .filter(([, cantidad]) => Number(cantidad) > 0)
      .map(([productoId, cantidad]) => ({
        producto_id: Number(productoId), cantidad: Number(cantidad),
      }))
    setError('')
    const registrada = await onRegistrar({ venta_id: Number(ventaId), items, motivo })
    if (registrada) {
      setCantidades({})
      setMotivo('')
    }
  }

  return (
    <div className="tarjeta">
      <h2>Registrar devolución</h2>
      <label>Venta
        <select value={ventaId} onChange={(e) => setVentaId(e.target.value)}>
          <option value="">Elegí una venta…</option>
          {ventas.map((v) => (
            <option key={v.id} value={v.id}>
              #{v.id} · {v.sucursal} · {v.fecha} · ${Number(v.total).toFixed(2)}
            </option>
          ))}
        </select>
      </label>
      {error && <div className="error">{error}</div>}
      {venta && <>
        <div className="grilla">
          {venta.items.map((item) => {
            const maximo = item.cantidad - cantidadDevuelta(item.producto_id)
            return (
              <label key={item.producto_id}>
                {item.nombre} · quedan {maximo} por devolver
                <input type="number" min="0" max={maximo} step="1"
                       value={cantidades[item.producto_id] ?? ''}
                       onChange={(e) => setCantidades({
                         ...cantidades, [item.producto_id]: e.target.value,
                       })} />
              </label>
            )
          })}
        </div>
        <label>Motivo
          <input value={motivo} onChange={(e) => setMotivo(e.target.value)} />
        </label>
        <button disabled={!motivo.trim() ||
          !Object.values(cantidades).some((cantidad) => Number(cantidad) > 0)}
          onClick={registrar}>Registrar devolución y reintegro</button>
      </>}
    </div>
  )
}
