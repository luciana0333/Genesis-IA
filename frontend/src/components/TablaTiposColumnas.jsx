import { Fragment, useState } from 'react';
import { IconoAumentar, IconoDisminuir } from './Iconos';
import { PanelDetalleTipos, tieneDetalle } from './DetalleTipos';

/** «en 8 tablas» o, si es una sola, su nombre: «en #DATAFINALF». */
const donde = (tablas) => (tablas.length === 1 ? `en ${tablas[0]}` : `en ${tablas.length} tablas`);

/**
 * «Misma columna con distinto tipo» como tabla (diseño de la usuaria, 7 nov.):
 * Nombre columna | Desglose de tipos y ocurrencias | Detalles. En el desglose, el tipo más usado va en
 * gris y los que se salen de él, en rojo, separados por «vs». «Ver tablas» abre, debajo de la fila,
 * el panel «Detalle de tipos».
 */
export function TablaTiposColumnas({ grupos, filaActiva = null }) {
  const [abiertas, setAbiertas] = useState(() => new Set());
  const alternar = (indice) => setAbiertas((anteriores) => {
    const nuevas = new Set(anteriores);
    if (nuevas.has(indice)) nuevas.delete(indice);
    else nuevas.add(indice);
    return nuevas;
  });

  return (
    <table className="tabla-tipos">
      <thead>
        <tr>
          <th scope="col">Nombre columna</th>
          <th scope="col">Desglose de tipos y ocurrencias</th>
          <th scope="col" className="tabla-tipos-detalles">Detalles</th>
        </tr>
      </thead>
      <tbody>
        {grupos.map((grupo, indice) => {
          const detalle = grupo.detalle ?? [];
          // El tipo con más temporales es el de referencia (gris); ante empate, el primero que aparece.
          const referencia = detalle.reduce(
            (mayor, fila, i) => (fila.tablas.length > detalle[mayor].tablas.length ? i : mayor), 0,
          );
          const abierta = abiertas.has(indice);
          return (
            <Fragment key={grupo.nombre}>
              <tr className={`tabla-tipos-fila${indice % 2 ? ' alterna' : ''}${indice === filaActiva ? ' activa' : ''}`}>
                <td><code className="tabla-tipos-columna">{grupo.nombre}</code></td>
                <td>
                  <span className="tabla-tipos-desglose">
                    {detalle.map((fila, i) => (
                      <Fragment key={fila.tipo}>
                        {i > 0 && <span className="tabla-tipos-vs">vs</span>}
                        <span className={`tabla-tipos-tipo${i === referencia ? '' : ' distinto'}`}>
                          <b>{fila.tipo}</b> {donde(fila.tablas)}
                        </span>
                      </Fragment>
                    ))}
                  </span>
                </td>
                <td className="tabla-tipos-detalles">
                  {tieneDetalle(detalle) && (
                    <button
                      type="button"
                      className={`tabla-tipos-boton${abierta ? ' abierto' : ''}`}
                      aria-expanded={abierta}
                      onClick={() => alternar(indice)}
                    >
                      {abierta ? <IconoAumentar /> : <IconoDisminuir />}
                      {abierta ? 'Ocultar tablas' : 'Ver tablas'}
                    </button>
                  )}
                </td>
              </tr>
              {abierta && (
                <tr className="tabla-tipos-panel">
                  <td colSpan={3}><PanelDetalleTipos nombre={grupo.nombre} detalle={detalle} /></td>
                </tr>
              )}
            </Fragment>
          );
        })}
      </tbody>
    </table>
  );
}
