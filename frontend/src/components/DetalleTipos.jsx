/** Tipo sin su longitud: VARCHAR(3) → VARCHAR. */
const tipoBase = (tipo) => tipo.replace(/\(.*$/, '');

/** Hay algo que desplegar si algún tipo está en varias temporales (si no, los nombres ya se leen en la fila). */
export const tieneDetalle = (detalle) => Boolean(detalle?.some((fila) => fila.tablas.length > 1));

/**
 * Panel «Detalle de tipos» de una columna (ej.: «Misma columna con distinto tipo»): cabecera con la
 * columna, el tipo de diferencia y los indicadores; debajo, Tipo de dato | Tablas temporales.
 */
export function PanelDetalleTipos({ nombre, detalle }) {
  const totalTablas = detalle.reduce((suma, fila) => suma + fila.tablas.length, 0);
  // VARCHAR(3) y VARCHAR(5): misma familia, distinta longitud; INT y VARCHAR: tipo distinto (obliga a convertir).
  const mismaFamilia = new Set(detalle.map((fila) => tipoBase(fila.tipo))).size === 1;

  return (
    <div className="detalle-tipos">
      <div className="detalle-tipos-cabecera">
        <div className="detalle-tipos-titulo">
          <span className="detalle-tipos-rotulo">
            Detalle de tipos
            <span className={`detalle-tipos-diferencia ${mismaFamilia ? 'longitud' : 'tipo'}`}>
              {mismaFamilia ? 'Distinta longitud' : 'Tipo distinto'}
            </span>
          </span>
          {nombre && <span className="detalle-tipos-columna">{nombre}</span>}
        </div>
        <div className="detalle-tipos-indicador">
          <span className="detalle-tipos-rotulo">Tipos</span>
          <strong>{detalle.length}</strong>
        </div>
        <div className="detalle-tipos-indicador">
          <span className="detalle-tipos-rotulo">Tablas</span>
          <strong>{totalTablas}</strong>
        </div>
      </div>
      <table>
        <thead>
          <tr><th scope="col">Tipo de dato</th><th scope="col">Tablas temporales</th></tr>
        </thead>
        <tbody>
          {detalle.map((fila) => {
            const porcentaje = Math.round((fila.tablas.length / totalTablas) * 100);
            return (
              <tr key={fila.tipo}>
                <td>
                  <code className="detalle-tipos-tipo">{fila.tipo}</code>
                  <span className="detalle-tipos-peso">
                    {fila.tablas.length} {fila.tablas.length === 1 ? 'tabla' : 'tablas'} · <b>{porcentaje}%</b>
                  </span>
                  <span className="detalle-tipos-barra" aria-hidden="true"><i style={{ width: `${porcentaje}%` }} /></span>
                </td>
                <td>
                  {fila.tablas.map((tabla) => <code key={tabla} className="detalle-tipos-tabla">{tabla}</code>)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
