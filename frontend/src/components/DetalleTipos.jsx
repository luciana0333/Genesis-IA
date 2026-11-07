import { Fragment } from 'react';

/** Tipo sin su longitud: VARCHAR(3) → VARCHAR. */
const tipoBase = (tipo) => tipo.replace(/\(.*$/, '');

/** Hay algo que desplegar si algún tipo está en varias temporales (si no, los nombres ya se leen en la fila). */
export const tieneDetalle = (detalle) => Boolean(detalle?.some((fila) => fila.tablas.length > 1));

/**
 * Panel «Detalle de tipos» de una columna (ej.: «Misma columna con distinto tipo»): cabecera con la
 * columna, el tipo de diferencia y los indicadores; debajo, una franja roja por tipo con sus temporales,
 * la línea donde definen la columna y «Ir a la línea» (diseño de referencia de la usuaria, 7 nov.).
 */
export function PanelDetalleTipos({ nombre, detalle, onIrALinea }) {
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
      {/* Una franja por tipo de dato y, debajo, sus temporales con la línea donde definen la columna. */}
      <table className="detalle-tipos-lista">
        <thead>
          <tr>
            <th scope="col">Tabla temporal</th>
            <th scope="col">Línea</th>
            <th scope="col"><span className="sr-only">Ir a la línea</span></th>
          </tr>
        </thead>
        <tbody>
          {detalle.map((fila) => {
            const porcentaje = Math.round((fila.tablas.length / totalTablas) * 100);
            return (
              <Fragment key={fila.tipo}>
                <tr className="detalle-tipos-franja">
                  <th scope="rowgroup" colSpan={3}>
                    <code>{fila.tipo}</code>
                    <span>
                      {fila.tablas.length} {fila.tablas.length === 1 ? 'tabla temporal' : 'tablas temporales'} · {porcentaje}%
                    </span>
                  </th>
                </tr>
                {fila.tablas.map((tabla, i) => {
                  const linea = fila.lineas?.[i];
                  return (
                    <tr key={tabla} className="detalle-tipos-temporal">
                      <td><code>{tabla}</code></td>
                      <td className="detalle-tipos-linea">{linea ?? '—'}</td>
                      <td className="detalle-tipos-accion">
                        {linea && onIrALinea && (
                          <button type="button" className="detalle-tipos-ir" onClick={() => onIrALinea(linea)}>
                            Ir a la línea
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
