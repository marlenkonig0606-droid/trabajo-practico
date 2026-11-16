// Selector visual de perfil para un usuario de local: Administrador o Empleado.
// Se usa en el registro (perfil que se solicita) y en el panel del administrador
// (alta directa y aprobación).
export const ROLES = [
  {
    valor: 'EMPLEADO',
    titulo: 'Empleado',
    detalle: 'Vende, pide reposición y recibe mercadería. No ve reportes ni habilita productos.',
  },
  {
    valor: 'ADMINISTRADOR',
    titulo: 'Administrador',
    detalle: 'Ve todo el local, aprueba empleados, habilita productos y consulta reportes.',
  },
]

export default function SelectorRol({ valor, onCambiar, titulo = 'Perfil', ayuda, compacto = false }) {
  return (
    <fieldset className={`selector-rol ${compacto ? 'compacto' : ''}`}>
      <legend>{titulo}</legend>
      <div className="selector-rol-opciones" role="radiogroup">
        {ROLES.map((rol) => (
          <label key={rol.valor} className={valor === rol.valor ? 'elegido' : ''}>
            <input type="radio" name={`rol-${titulo}`} value={rol.valor}
                   checked={valor === rol.valor}
                   onChange={() => onCambiar(rol.valor)} />
            <strong>{rol.titulo}</strong>
            {!compacto && <span>{rol.detalle}</span>}
          </label>
        ))}
      </div>
      {ayuda && <p className="ayuda">{ayuda}</p>}
    </fieldset>
  )
}
