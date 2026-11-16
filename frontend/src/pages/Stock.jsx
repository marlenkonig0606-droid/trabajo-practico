import { Fragment, useEffect, useState } from 'react'
import { api } from '../api.js'
import {
  Avisos, BarraFiltros, BotonIcono, Cargando, Modal, Vacio, useListado,
} from '../components/UI.jsx'
import { formatearFecha, pesos } from '../utils/fechas.js'

export default function Stock({ usuario }) {
  const esCD = usuario.tipo === 'CD'
  const [sucursales, setSucursales] = useState([])
  const [sucursal, setSucursal] = useState(usuario.sucursal_id)
  const [proveedores, setProveedores] = useState([])
  const [alertas, setAlertas] = useState([])
  const [verAlertas, setVerAlertas] = useState(true)
  const [abierto, setAbierto] = useState(null)
  const [ajustando, setAjustando] = useState(null)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const listado = useListado((f) => api.buscarStock(sucursal, f),
    { q: '', situacion: '', proveedor_id: '' }, [sucursal])
  const { filtros, setFiltros } = listado

  useEffect(() => {
    api.sucursales().then(setSucursales).catch((e) => setError(e.message))
    if (esCD) api.proveedores().then(setProveedores).catch(() => {})
  }, [])
  const cargarAlertas = () => api.alertas().then(setAlertas).catch((e) => setError(e.message))
  useEffect(() => { cargarAlertas() }, [])

  const tipoSucursal = sucursales.find((s) => s.id === Number(sucursal))?.tipo
  const verCD = tipoSucursal === 'CD'
  const puedeAjustar = esCD && Number(sucursal) === usuario.sucursal_id
  const alertasVisibles = alertas.filter((a) => !esCD || a.sucursal ===
    sucursales.find((s) => s.id === Number(sucursal))?.nombre)

  return (
    <section className="pantalla">
      <header className="pantalla-cabecera">
        <div>
          <h2>Stock disponible</h2>
          <p className="ayuda">{verCD
            ? 'El mínimo del CD es la suma de los mínimos que cada local configuró para el producto.'
            : 'El mínimo es el que configuró el administrador de este local.'}</p>
        </div>
        {esCD && (
          <label className="selector-sucursal">Sucursal
            <select value={sucursal} onChange={(e) => { setSucursal(Number(e.target.value)); setAbierto(null) }}>
              {sucursales.map((s) => <option key={s.id} value={s.id}>{s.nombre} ({s.tipo})</option>)}
            </select></label>
        )}
      </header>
      <Avisos error={error || listado.error} mensaje={mensaje} onCerrar={() => { setError(''); setMensaje('') }} />

      {alertasVisibles.length > 0 && (
        <section className="tarjeta alertas">
          <div className="fila-titulo">
            <h3>⚠ Bajo el stock mínimo ({alertasVisibles.length})</h3>
            <BotonIcono icono={verAlertas ? 'ocultar' : 'ver'}
                        etiqueta={verAlertas ? 'Ocultar alertas' : 'Ver alertas'}
                        onClick={() => setVerAlertas(!verAlertas)} />
          </div>
          {verAlertas && (
            <ul>{alertasVisibles.map((a) => (
              <li key={a.id}><b>{a.producto}</b>{esCD && ` en ${a.sucursal}`}: {a.libre} libres,
                mínimo {a.minimo} → faltan <b>{Math.max(a.minimo - a.libre, 0)}</b>
                <span className="fecha"> · desde el {formatearFecha(a.fecha)}</span></li>
            ))}</ul>
          )}
        </section>
      )}

      <BarraFiltros onBuscar={listado.aplicar} onLimpiar={listado.limpiar} cargando={listado.cargando}>
        <label className="campo-ancho">Producto
          <input type="search" value={filtros.q} placeholder="Nombre, código o proveedor (parcial)"
                 onChange={(e) => setFiltros({ ...filtros, q: e.target.value })} /></label>
        <label>Situación
          <select value={filtros.situacion} onChange={(e) => setFiltros({ ...filtros, situacion: e.target.value })}>
            <option value="">Todas</option><option value="bajo">Bajo el mínimo</option>
            <option value="ok">Sobre el mínimo</option>
          </select></label>
        {esCD && (
          <label>Proveedor
            <select value={filtros.proveedor_id} onChange={(e) => setFiltros({ ...filtros, proveedor_id: e.target.value })}>
              <option value="">Todos</option>
              {proveedores.map((p) => <option key={p.id} value={p.id}>{p.nombre}</option>)}
            </select></label>
        )}
      </BarraFiltros>

      <div className="tarjeta listado">
        {listado.cargando && !listado.datos ? <Cargando /> :
          listado.items.length === 0 ? <Vacio /> : (
          <table className="tabla-compacta">
            <thead><tr><th>Producto</th>{esCD && <th>Proveedor</th>}
              <th className="numero">Disponible</th><th className="numero">Reservado</th>
              <th className="numero">Libre</th><th className="numero">Mínimo</th><th>Situación</th>
              <th className="acciones">Acciones</th></tr></thead>
            <tbody>{listado.items.map((f) => {
              const bajo = f.libre < f.stock_minimo
              return (
                <Fragment key={f.producto_id}>
                  <tr className={bajo ? 'bajo' : ''}>
                    <td><b>{f.nombre}</b><small className="codigo"> {f.codigo}</small></td>
                    {esCD && <td>{f.proveedor ?? <span className="ayuda">Sin proveedor</span>}</td>}
                    <td className="numero">{f.disponible}</td>
                    <td className="numero">{f.reservado}</td>
                    <td className="numero"><b>{f.libre}</b></td>
                    <td className="numero">{f.stock_minimo}</td>
                    <td><span className={`insignia-estado ${bajo ? 'no' : 'si'}`}>
                      {bajo ? `Faltan ${f.stock_minimo - f.libre}` : 'OK'}</span></td>
                    <td className="acciones">
                      <BotonIcono icono={abierto === f.producto_id ? 'ocultar' : 'ver'}
                                  etiqueta={abierto === f.producto_id ? 'Cerrar detalle' : 'Abrir detalle'}
                                  activo={abierto === f.producto_id}
                                  onClick={() => setAbierto(abierto === f.producto_id ? null : f.producto_id)} />
                      {puedeAjustar && (
                        <BotonIcono icono="editar" etiqueta="Ajustar stock disponible"
                                    onClick={() => setAjustando(f)} />
                      )}
                    </td>
                  </tr>
                  {abierto === f.producto_id && (
                    <tr className="fila-detalle"><td colSpan={esCD ? 8 : 7}>
                      <dl className="detalle-datos">
                        <div><dt>Código</dt><dd>{f.codigo}</dd></div>
                        <div><dt>Precio de venta</dt><dd>{pesos(f.precio_venta)}</dd></div>
                        <div><dt>Proveedor</dt><dd>{f.proveedor ?? '—'}</dd></div>
                        <div><dt>{verCD ? 'Mínimo del CD (suma de locales)' : 'Mínimo del local'}</dt>
                          <dd>{f.stock_minimo}</dd></div>
                        <div><dt>Mínimo por defecto del catálogo</dt><dd>{f.stock_minimo_defecto}</dd></div>
                        <div><dt>Estado en la sucursal</dt><dd>{f.habilitado || verCD ? 'Habilitado' : 'Deshabilitado'}</dd></div>
                      </dl>
                    </td></tr>
                  )}
                </Fragment>
              )
            })}</tbody>
          </table>
        )}
        {listado.paginacion()}
        {listado.items.length > 0 && <GraficoStock filas={listado.items} />}
      </div>

      {ajustando && (
        <ModalAjuste fila={ajustando} sucursalId={sucursal} onCerrar={() => setAjustando(null)}
                     onGuardado={() => {
                       setMensaje(`Stock de ${ajustando.nombre} actualizado.`)
                       setAjustando(null)
                       listado.recargar()
                       cargarAlertas()
                     }} />
      )}
    </section>
  )
}

// Gráfico de barras del stock libre (los productos de la página actual)
function GraficoStock({ filas }) {
  const maximo = Math.max(1, ...filas.map((f) => Math.max(f.libre, f.stock_minimo)))
  return (
    <details className="detalle-grafico">
      <summary>Ver gráfico de stock libre</summary>
      <div className="stock-visual">
        <div className="stock-barras">
          {filas.map((f) => (
            <div className="stock-barra-item" key={f.producto_id}
                 title={`${f.nombre}: ${f.libre} libres · mínimo ${f.stock_minimo}`}>
              <span>{f.nombre}</span>
              <div className="stock-barra-pista">
                <i style={{ width: `${Math.max(0, f.libre) / maximo * 100}%` }}
                   className={f.libre < f.stock_minimo ? 'bajo' : ''} />
              </div>
              <b>{f.libre}</b>
            </div>
          ))}
        </div>
      </div>
    </details>
  )
}

function ModalAjuste({ fila, sucursalId, onCerrar, onGuardado }) {
  const [valor, setValor] = useState(String(fila.disponible))
  const [error, setError] = useState('')
  const [guardando, setGuardando] = useState(false)
  const numero = Number(valor)
  const valido = valor !== '' && Number.isInteger(numero) && numero >= fila.reservado
    && numero !== fila.disponible
  const guardar = async (e) => {
    e.preventDefault()
    if (!valido || guardando) return
    setGuardando(true)
    try {
      await api.ajustarStock(Number(sucursalId), fila.producto_id, numero)
      onGuardado()
    } catch (err) { setError(err.message); setGuardando(false) }
  }
  return (
    <Modal titulo={`Ajustar stock · ${fila.nombre}`} onCerrar={onCerrar} ancho="chico">
      <form className="formulario-modal" onSubmit={guardar}>
        {error && <div className="error" role="alert">{error}</div>}
        <p className="ayuda">Hay {fila.reservado} unidades reservadas para bultos: el disponible no
          puede quedar por debajo de ese número. El ajuste queda registrado como movimiento.</p>
        <label>Stock disponible
          <input type="number" min={fila.reservado} step="1" value={valor}
                 onChange={(e) => setValor(e.target.value)} /></label>
        <div className="modal-acciones">
          <button type="button" className="secundario" onClick={onCerrar}>Cancelar</button>
          <button type="submit" disabled={!valido || guardando}>{guardando ? 'Guardando…' : 'Guardar'}</button>
        </div>
      </form>
    </Modal>
  )
}
