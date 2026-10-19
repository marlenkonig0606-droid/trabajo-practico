import { useState } from 'react'
import Logistica from './pages/Logistica.jsx'
import Stock from './pages/Stock.jsx'
import Reportes from './pages/Reportes.jsx'
import Catalogo from './pages/Catalogo.jsx'
import Pendiente from './pages/Pendiente.jsx'

const SECCIONES = [
  { id: 'logistica', titulo: 'Logística', componente: <Logistica /> },
  { id: 'stock', titulo: 'Stock', componente: <Stock /> },
  { id: 'reportes', titulo: 'Reportes', componente: <Reportes /> },
  { id: 'ventas', titulo: 'Ventas', componente: <Pendiente nombre="Ventas y devoluciones" /> },
  { id: 'abm', titulo: 'Catálogo', componente: <Catalogo /> },
]

export default function App() {
  const [actual, setActual] = useState('logistica')
  return (
    <div className="app">
      <header>
        <h1>Centro de distribucion MARLUFA</h1>
        <nav>
          {SECCIONES.map((s) => (
            <button key={s.id} className={actual === s.id ? 'activo' : ''}
                    onClick={() => setActual(s.id)}>{s.titulo}</button>
          ))}
        </nav>
      </header>
      <main>{SECCIONES.find((s) => s.id === actual).componente}</main>
    </div>
  )
}
