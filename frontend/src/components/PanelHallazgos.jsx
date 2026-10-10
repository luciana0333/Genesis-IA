import { useMemo, useState } from 'react';
import { SEVERIDADES, etiquetaSeveridad, nombreRegla } from '../config/reglas';
import { contarPorSeveridad, desglosarGrupo, normalizarSeveridad, ordenarHallazgos, separarMensaje } from '../utils/hallazgos';
import { EncabezadoSeccion } from './EncabezadoSeccion';
import { EstadoInicial } from './EstadoInicial';
import { EstadoVacio } from './EstadoVacio';
import { IconoCopiar, IconoCopiado, IconoErrorCirculo } from './Iconos';

/** Resalta lo que el mensaje cita entre comillas simples: 'Indicatg', 'dbo2'. */
function MensajeResaltado({ texto }) {
  const partes = texto.split(/('[^'\n]+')/g);
  return partes.map((parte, indice) =>
    /^'[^'\n]+'$/.test(parte)
      ? <mark key={indice} className="finding-token">{parte.slice(1, -1)}</mark>
      : parte,
  );
}

const VEREDICTOS = {
  critico: { titulo: 'Requiere correcciones', texto: 'Hay errores críticos que impiden aprobar el objeto.' },
  alto: { titulo: 'Requiere correcciones', texto: 'Corregir los hallazgos de severidad alta antes de pasar a producción.' },
  medio: { titulo: 'Con observaciones', texto: 'Se recomienda revisar las observaciones de severidad media; no bloquean, pero conviene corregirlas.' },
  bajo: { titulo: 'Observaciones menores', texto: 'Solo hay recomendaciones o puntos por validar.' },
};

/**
 * Columna lateral oscura del tablero: total, veredicto y filtros por severidad
 * (todas las severidades, con su cantidad aunque sea cero).
 */
function ResumenLateral({ conteo, total, filtro, onFiltrar }) {
  const mayor = SEVERIDADES.find((severidad) => conteo[severidad] > 0) ?? 'bajo';
  const veredicto = VEREDICTOS[mayor];
  const opciones = [
    { id: 'todos', etiqueta: 'Todos', cantidad: total },
    ...SEVERIDADES.map((severidad) => ({
      id: severidad,
      etiqueta: etiquetaSeveridad(severidad),
      cantidad: conteo[severidad],
    })),
  ];
  return (
    <aside className={`tablero-lateral sev-${mayor}`}>
      <p className="tablero-kicker">{total === 1 ? 'Hallazgo' : 'Hallazgos'}</p>
      <strong className="tablero-total">{total}</strong>
      <p className="tablero-estado" role="status">{veredicto.titulo}</p>
      <p className="tablero-texto">{veredicto.texto}</p>
      <div className="tablero-filtros" role="group" aria-label="Filtrar por severidad">
        {opciones.map((opcion) => (
          <button
            key={opcion.id}
            type="button"
            className={`tablero-filtro filtro-${opcion.id}${filtro === opcion.id ? ' active' : ''}`}
            aria-pressed={filtro === opcion.id}
            disabled={opcion.id !== 'todos' && !opcion.cantidad}
            onClick={() => onFiltrar(opcion.id)}
          >
            <span>
              {opcion.id !== 'todos' && <i aria-hidden="true" />}
              {opcion.etiqueta}
            </span>
            <span className="tablero-cantidad">{opcion.cantidad}</span>
          </button>
        ))}
      </div>
    </aside>
  );
}

function textoParaCopiar(hallazgo, mostrarLinea) {
  const severidad = etiquetaSeveridad(normalizarSeveridad(hallazgo.severidad));
  const ubicacion = mostrarLinea ? ` (línea ${hallazgo.linea || 1})` : '';
  return `[${severidad}] ${nombreRegla(hallazgo.regla)}${ubicacion}: ${hallazgo.mensaje}`;
}

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch {
    return false;
  }
}

/** Botón que copia un texto y confirma durante un momento. */
function BotonCopiar({ texto, etiqueta, conTexto = false }) {
  const [copiado, setCopiado] = useState(false);
  const alCopiar = async () => {
    if (await copiar(texto)) {
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1600);
    }
  };
  return (
    <button
      type="button"
      className={conTexto ? 'copy-btn copy-btn--texto' : 'copy-btn'}
      onClick={alCopiar}
      aria-label={copiado ? 'Copiado' : etiqueta}
      title={copiado ? 'Copiado' : etiqueta}
    >
      {copiado ? <IconoCopiado /> : <IconoCopiar />}
      {conTexto && <span>{copiado ? 'Copiado' : etiqueta}</span>}
    </button>
  );
}

/**
 * Ficha de un hallazgo: título y, a la derecha, línea y severidad; debajo lo
 * que se encontró y, tras una línea punteada, qué hacer. Si el hallazgo agrupa
 * varias ocurrencias, cada una se lista por separado.
 */
function FilaHallazgo({ hallazgo, mostrarLinea }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  const titulo = nombreRegla(hallazgo.regla);
  const mensaje = hallazgo.mensaje || 'Revisa este hallazgo.';
  const { problema, solucion } = separarMensaje(mensaje);
  const { lineas, intro, ocurrencias } = desglosarGrupo(problema);
  const etiquetaLinea = lineas
    ? `${lineas.includes(',') ? 'Líneas' : 'Línea'} ${lineas}`
    : `Línea ${hallazgo.linea || 1}`;

  return (
    <article className={`finding sev-${severidad}`}>
      <header className="finding-head">
        <h4 className="finding-title">{titulo}</h4>
        <span className="finding-head-side">
          {mostrarLinea && <span className="finding-line">{etiquetaLinea}</span>}
          <span className={`sev-pill sev-${severidad}`}>{etiquetaSeveridad(severidad)}</span>
          <BotonCopiar texto={textoParaCopiar(hallazgo, mostrarLinea)} etiqueta="Copiar observación" />
        </span>
      </header>

      <div className="finding-body">
        {intro && <p className="finding-message">{intro}</p>}
        {ocurrencias.length > 1 ? (
          <ul className="finding-list">
            {ocurrencias.map((texto) => <li key={texto}><MensajeResaltado texto={texto} /></li>)}
          </ul>
        ) : (
          <p className="finding-message"><MensajeResaltado texto={ocurrencias[0]} /></p>
        )}
        {solucion && (
          <p className="finding-fix">
            <span className="finding-label">Qué hacer:</span> <MensajeResaltado texto={solucion} />
          </p>
        )}
      </div>

    </article>
  );
}

function EsqueletoCarga() {
  return (
    <div className="findings-skeleton" aria-hidden="true">
      {[0, 1, 2].map((indice) => <div key={indice} className="skeleton-card" />)}
    </div>
  );
}

/**
 * Panel de resultados de un análisis.
 *
 * estado: 'inicial' | 'cargando' | 'listo' | 'error'
 * textos: { inicial, cargando, sinHallazgos, tituloError } — mensajes por estado.
 */
export function PanelHallazgos({
  titulo,
  meta,
  estado,
  hallazgos = [],
  mensajeError,
  textos,
  mostrarLinea = true,
}) {
  const [filtroElegido, setFiltro] = useState('todos');
  const conteo = useMemo(() => contarPorSeveridad(hallazgos), [hallazgos]);
  const ordenados = useMemo(() => ordenarHallazgos(hallazgos), [hallazgos]);

  // Si el filtro elegido ya no tiene resultados (nuevo análisis), se vuelve a "Todos".
  const filtro = filtroElegido !== 'todos' && !conteo[filtroElegido] ? 'todos' : filtroElegido;
  const visibles = filtro === 'todos'
    ? ordenados
    : ordenados.filter((hallazgo) => normalizarSeveridad(hallazgo.severidad) === filtro);
  const hayHallazgos = estado === 'listo' && hallazgos.length > 0;

  let contenido;
  if (estado === 'cargando') {
    contenido = (
      <>
        <p className="loading-text">{textos.cargando}</p>
        <EsqueletoCarga />
      </>
    );
  } else if (estado === 'error') {
    contenido = (
      <EstadoVacio tono="error" icono={<IconoErrorCirculo />} titulo={textos.tituloError}>
        {mensajeError}
      </EstadoVacio>
    );
  } else if (estado === 'listo' && !hallazgos.length) {
    contenido = (
      <EstadoInicial
        variante="exito"
        titulo="Todo en orden"
        descripcion={textos.sinHallazgos}
        pasos={[
          'Se aplicaron todas las reglas de la revisión',
          'No hay observaciones de ninguna severidad',
          'Puedes continuar con el siguiente paso',
        ]}
      />
    );
  } else if (hayHallazgos) {
    contenido = (
      <div className="findings-list">
        {visibles.map((hallazgo, indice) => (
          <FilaHallazgo
            // El backend no envía un id; regla + línea + posición es estable por resultado.
            key={`${hallazgo.regla}-${hallazgo.linea}-${indice}`}
            hallazgo={hallazgo}
            mostrarLinea={mostrarLinea}
          />
        ))}
      </div>
    );
  } else {
    contenido = (
      <EstadoInicial
        titulo={textos.inicialTitulo}
        descripcion="Los hallazgos aparecerán aquí, ordenados por severidad."
        pasos={textos.pasos}
      />
    );
  }

  const textoTodos = visibles.map((h, i) => `${i + 1}. ${textoParaCopiar(h, mostrarLinea)}`).join('\n');

  return (
    <section className="results-panel" aria-live="polite" aria-busy={estado === 'cargando'}>
      <EncabezadoSeccion
        nivel={3}
        etiqueta="Paso 2 · Resultados"
        titulo={titulo}
        acciones={
          <>
            {meta && <span className="results-meta">{meta}</span>}
            {hayHallazgos && <BotonCopiar texto={textoTodos} etiqueta="Copiar todo" conTexto />}
          </>
        }
      />
      {hayHallazgos ? (
        <div className="resultados-tablero">
          <ResumenLateral conteo={conteo} total={hallazgos.length} filtro={filtro} onFiltrar={setFiltro} />
          {contenido}
        </div>
      ) : contenido}
    </section>
  );
}
