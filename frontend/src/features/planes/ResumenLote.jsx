import { useState } from 'react';
import { Boton } from '../../components/Boton';
import { EncabezadoSeccion } from '../../components/EncabezadoSeccion';
import {
  IconoAnterior, IconoCopiado, IconoCopiar, IconoEscudoCheck, IconoHallazgo, IconoRejilla, IconoReloj, IconoSiguiente,
  IconoVolver,
} from '../../components/Iconos';
import { TarjetaMetrica } from '../../components/TarjetaMetrica';
import { formatearDuracion, ordenarPlanes } from './ordenLote';

const SEVERIDADES = [
  { id: 'critico', etiqueta: 'Crítico' },
  { id: 'alto', etiqueta: 'Alto' },
  { id: 'medio', etiqueta: 'Medio' },
  { id: 'bajo', etiqueta: 'Bajo' },
];

const NOMBRES_AREA = { reporte: 'Reportes', negocio: 'Negocio' };

export function MetricasLote({ lote }) {
  const { totales, limite } = lote;
  const porSeveridad = SEVERIDADES
    .filter(({ id }) => totales.porSeveridad[id])
    .map(({ id, etiqueta }) => `${totales.porSeveridad[id]} ${etiqueta.toLowerCase()}`);
  return (
    <section className="metrics-grid" aria-label="Resumen del lote">
      <TarjetaMetrica
        titulo="Planes revisados"
        valor={totales.planes}
        subtitulo={totales.conError ? `${totales.conError} no se pudieron leer` : `Área ${NOMBRES_AREA[lote.area] ?? lote.area}`}
        icono={<IconoRejilla />}
      />
      <TarjetaMetrica
        titulo="Superan el límite"
        valor={totales.superanLimite}
        subtitulo={limite != null ? `Límite de ${limite} s por plan` : 'Sin límite definido'}
        icono={<IconoReloj />}
      />
      <TarjetaMetrica
        titulo="Hallazgos"
        valor={totales.hallazgos}
        subtitulo={porSeveridad.length ? porSeveridad.join(' · ') : 'Sin observaciones'}
        icono={<IconoHallazgo />}
      />
      <TarjetaMetrica
        titulo="Sin hallazgos"
        valor={totales.sinHallazgos}
        subtitulo="Planes que cumplen las reglas"
        icono={<IconoEscudoCheck />}
      />
    </section>
  );
}

function PildorasSeveridad({ resumen }) {
  const presentes = SEVERIDADES.filter(({ id }) => resumen[id]);
  if (!presentes.length) return <span className="lote-limpio">Sin hallazgos</span>;
  return (
    <span className="lote-pildoras">
      {presentes.map(({ id, etiqueta }) => (
        <span key={id} className={`lote-pill sev-${id}`} title={`${resumen[id]} ${etiqueta.toLowerCase()}`}>
          {resumen[id]} {etiqueta}
        </span>
      ))}
    </span>
  );
}

function EstadoTiempo({ plan, limite }) {
  if (plan.error) return <span className="lote-estado lote-estado--error">Dañado</span>;
  if (plan.duracionMs === null || plan.duracionMs === undefined) {
    return <span className="lote-estado">Sin tiempo real</span>;
  }
  if (plan.superaLimite) return <span className="lote-estado lote-estado--supera">Supera el límite</span>;
  if (limite == null) return <span className="lote-estado">Sin límite</span>;
  return <span className="lote-estado lote-estado--ok">Dentro del límite</span>;
}

function EncabezadoOrden({ columna, titulo, orden, onOrdenar, className }) {
  const activa = orden.columna === columna;
  return (
    <th
      scope="col"
      className={className}
      aria-sort={activa ? (orden.direccion === 'desc' ? 'descending' : 'ascending') : 'none'}
    >
      <button
        type="button"
        className={activa ? 'lote-orden activa' : 'lote-orden'}
        onClick={() => onOrdenar(columna)}
        title={`Ordenar por ${titulo.toLowerCase()}`}
      >
        {titulo}
        <span className="lote-orden-flecha" aria-hidden="true">
          {activa ? (orden.direccion === 'desc' ? '▼' : '▲') : '↕'}
        </span>
      </button>
    </th>
  );
}

/** Resumen en texto (tabla para pegar en Word o en el correo). */
function textoResumen(lote, planes) {
  const area = NOMBRES_AREA[lote.area] ?? lote.area;
  const filas = planes.map((plan, indice) => {
    if (plan.error) return [indice + 1, plan.procedimiento, plan.archivo, '—', 'Dañado', '—', '—', '—', '—'];
    const estado = plan.duracionMs == null ? 'Sin tiempo real' : plan.superaLimite ? 'Supera el límite' : 'Dentro del límite';
    return [
      indice + 1, plan.procedimiento, plan.archivo, formatearDuracion(plan.duracionMs), estado,
      plan.resumen.critico, plan.resumen.alto, plan.resumen.medio, plan.resumen.bajo,
    ];
  });
  const encabezado = ['N.°', 'Procedimiento', 'Archivo', 'Tiempo', 'Estado', 'Crítico', 'Alto', 'Medio', 'Bajo'];
  const titulo = `Revisión de planes de ejecución · ${area}${lote.limite != null ? ` · límite ${lote.limite} s` : ''}`;
  const texto = [titulo, '', encabezado.join('\t'), ...filas.map((fila) => fila.join('\t'))].join('\n');
  const escapar = (valor) => String(valor).replace(/&/g, '&amp;').replace(/</g, '&lt;');
  const html = `<p><b>${escapar(titulo)}</b></p><table border="1" cellpadding="4" style="border-collapse:collapse">`
    + `<tr>${encabezado.map((celda) => `<th>${escapar(celda)}</th>`).join('')}</tr>`
    + filas.map((fila) => `<tr>${fila.map((celda) => `<td>${escapar(celda)}</td>`).join('')}</tr>`).join('')
    + '</table>';
  return { texto, html };
}

function BotonCopiarResumen({ lote, planes }) {
  const [copiado, setCopiado] = useState(false);
  const copiar = async () => {
    const { texto, html } = textoResumen(lote, planes);
    try {
      if (window.ClipboardItem) {
        await navigator.clipboard.write([new ClipboardItem({
          'text/plain': new Blob([texto], { type: 'text/plain' }),
          'text/html': new Blob([html], { type: 'text/html' }),
        })]);
      } else {
        await navigator.clipboard.writeText(texto);
      }
      setCopiado(true);
      setTimeout(() => setCopiado(false), 2000);
    } catch {
      // Sin permiso para el portapapeles: no hay nada más que hacer.
    }
  };
  return (
    <Boton variante="secundario" icono={copiado ? <IconoCopiado /> : <IconoCopiar />} onClick={copiar}>
      {copiado ? 'Copiado' : 'Copiar resumen'}
    </Boton>
  );
}

/** Tabla de planes (más lento primero) y archivos que no se revisaron. */
export function ResumenLote({ lote, orden, onOrdenar, onVerPlan }) {
  const planes = ordenarPlanes(lote.planes, orden);
  const alOrdenar = (columna) => onOrdenar(
    orden.columna === columna
      ? { columna, direccion: orden.direccion === 'desc' ? 'asc' : 'desc' }
      : { columna, direccion: 'desc' },
  );

  return (
    <section className="lote-seccion">
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Revisión por lote"
        titulo="Planes del lote"
        acciones={<BotonCopiarResumen lote={lote} planes={planes} />}
      />
      <div className="table-scroll">
        <table className="data-table lote-tabla">
          <thead>
            <tr>
              <th scope="col" className="num">N.°</th>
              <EncabezadoOrden columna="procedimiento" titulo="Procedimiento" orden={orden} onOrdenar={alOrdenar} />
              <EncabezadoOrden columna="duracion" titulo="Tiempo" orden={orden} onOrdenar={alOrdenar} className="num" />
              <th scope="col">Estado</th>
              <EncabezadoOrden columna="hallazgos" titulo="Hallazgos" orden={orden} onOrdenar={alOrdenar} />
              <th scope="col"><span className="sr-only">Acciones</span></th>
            </tr>
          </thead>
          <tbody>
            {planes.map((plan, indice) => (
              <tr key={plan.id} className={plan.superaLimite ? 'lote-fila--supera' : undefined}>
                <td className="num mono">{indice + 1}</td>
                <td>
                  <span className="lote-procedimiento">{plan.procedimiento}</span>
                  <span className="lote-ruta" title={plan.ruta}>{plan.ruta}</span>
                  {plan.error && <span className="lote-error">{plan.error}</span>}
                </td>
                <td className={`num mono${plan.superaLimite ? ' lote-tiempo--supera' : ''}`}>
                  {plan.error ? '—' : formatearDuracion(plan.duracionMs)}
                </td>
                <td><EstadoTiempo plan={plan} limite={lote.limite} /></td>
                <td>{plan.error ? '—' : <PildorasSeveridad resumen={plan.resumen} />}</td>
                <td className="lote-accion">
                  {!plan.error && (
                    <button type="button" className="lote-ver" onClick={() => onVerPlan(plan.id)}>
                      Ver detalle
                      <IconoSiguiente />
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {lote.ignorados.length > 0 && (
        <details className="lote-ignorados">
          <summary>
            {lote.ignorados.length} archivo{lote.ignorados.length === 1 ? '' : 's'} no se
            {lote.ignorados.length === 1 ? ' revisó' : ' revisaron'}
          </summary>
          <ul>
            {lote.ignorados.map((ignorado) => (
              <li key={`${ignorado.ruta}-${ignorado.motivo}`}>
                <span className="lote-ruta">{ignorado.ruta}</span>
                <span className="lote-motivo">{ignorado.motivo}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

/** Barra sobre el detalle de un plan del lote: volver al resumen y pasar al anterior o siguiente. */
export function NavegacionLote({ lote, orden, planElegido, onVerPlan, onVolver }) {
  const legibles = ordenarPlanes(lote.planes, orden).filter((plan) => !plan.error);
  const posicion = legibles.findIndex((plan) => plan.id === planElegido);
  const actual = legibles[posicion];
  if (!actual) return null;
  const anterior = legibles[posicion - 1];
  const siguiente = legibles[posicion + 1];

  return (
    <nav className="lote-nav" aria-label="Planes del lote">
      <Boton variante="secundario" icono={<IconoVolver />} onClick={onVolver}>Volver al resumen</Boton>
      <div className="lote-nav-actual">
        <span className="lote-nav-posicion">Plan {posicion + 1} de {legibles.length}</span>
        <span className="lote-procedimiento">{actual.procedimiento}</span>
      </div>
      <div className="btn-group">
        <Boton
          variante="secundario"
          icono={<IconoAnterior />}
          disabled={!anterior}
          onClick={() => anterior && onVerPlan(anterior.id)}
        >
          Anterior
        </Boton>
        <Boton
          variante="secundario"
          icono={<IconoSiguiente />}
          disabled={!siguiente}
          onClick={() => siguiente && onVerPlan(siguiente.id)}
        >
          Siguiente
        </Boton>
      </div>
    </nav>
  );
}
