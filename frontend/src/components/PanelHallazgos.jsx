import { useState } from 'react';
import { SEVERIDADES, etiquetaSeveridad, tituloHallazgo } from '../config/reglas';
import { etiquetaDeGrupos } from '../utils/recorrido';
import { tokenizarSql } from '../utils/resaltadoSql';
import { contarPorSeveridad, desglosarGrupo, normalizarSeveridad, ordenarHallazgos, separarMensaje } from '../utils/hallazgos';
import { TablaTiposColumnas } from './TablaTiposColumnas';
import { TablaColumnasSinCollate, collateEnTabla, tituloDeColumnas } from './TablaColumnasSinCollate';

// Observaciones que se muestran en cajitas (solo los nombres), desde cuántos casos: NOLOCK desde 3 (opción A, 8 nov.);
// «Validar tabla temporal sin crear» con más de 3 (opción A, 21 nov.).
const CAJITAS_DESDE = {
  TABLA_FISICA_SIN_NOLOCK: 3, CONSULTA_SIN_NOLOCK: 3, NOLOCK_POR_EVALUAR: 3, TEMPORAL_SIN_CREAR_VALIDAR: 4,
  TABLA_SIN_DESCRIPCION: 4, // tablas sin documentar en el diccionario, desde 4 (usuaria, 25 nov.)
};
import { EncabezadoSeccion } from './EncabezadoSeccion';
import { CasosPocoComunes } from './CasosPocoComunes';
import { EstadoInicial } from './EstadoInicial';
import { EstadoVacio } from './EstadoVacio';
import {
  IconoBaseDatos, IconoCandado, IconoCopiar, IconoCopiado, IconoErrorCirculo, IconoEscudoCheck, IconoFlecha,
} from './Iconos';

/**
 * Resalta lo que el mensaje cita entre comillas simples ('Indicatg', 'dbo2') o
 * entre comillas angulares («CONVERT_IMPLICIT(…)»), que se usan cuando el texto
 * citado trae sus propias comillas simples (p. ej. N'SUR').
 */
function MensajeResaltado({ texto }) {
  const partes = texto.split(/(«[^»\n]+»|'[^'\n]+')/g);
  return partes.map((parte, indice) =>
    /^«[^»\n]+»$|^'[^'\n]+'$/.test(parte)
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
function ResumenLateral({ conteo, total, filtro, onFiltrar, origen = 'practicas' }) {
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
    // Buenas prácticas en rojo (como siempre); Validador SQL Server en oscuro (usuaria, 22 nov.).
    <aside className={`tablero-lateral sev-${mayor}${origen === 'validador' ? ' origen-validador' : ''}`}>
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

// Texto de la usuaria (13 nov.).
const DESCRIPCION_RIESGOS = 'Se identificaron hallazgos que Genesis evaluó y clasificó como riesgos durante el análisis '
  + 'del código y del plan de ejecución. Se recomienda revisar estos hallazgos y realizar las correcciones '
  + 'correspondientes antes del pase a producción.';

// Cajitas secundarias del formulario: la línea del hallazgo es de esa cajita.
const SECCIONES = { indices: 'Índices' };

function textoParaCopiar(hallazgo, mostrarLinea) {
  const severidad = etiquetaSeveridad(normalizarSeveridad(hallazgo.severidad));
  const seccion = SECCIONES[hallazgo.seccion];
  const ubicacion = mostrarLinea ? ` (${seccion ? `${seccion}, línea` : 'línea'} ${hallazgo.linea || 1})` : '';
  const texto = `[${severidad}] ${tituloHallazgo(hallazgo)}${ubicacion}: ${hallazgo.mensaje}`;
  // Si trae un bloque de código (p. ej. la consulta más lenta del plan), se copia debajo del mensaje.
  return hallazgo.codigo ? `${texto}\n\n${hallazgo.codigo}` : texto;
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
function FilaHallazgo({ hallazgo, mostrarLinea, acciones, vinetaActiva = null }) {
  const severidad = normalizarSeveridad(hallazgo.severidad);
  const titulo = tituloHallazgo(hallazgo);
  const mensaje = hallazgo.mensaje || 'Revisa este hallazgo.';
  const { problema, solucion } = separarMensaje(mensaje, hallazgo.inicioQueHacer);
  const desglose = desglosarGrupo(problema);
  const { intro, ocurrencias } = desglose;
  // Las líneas salen del texto agrupado o, si la observación las trae aparte, de hallazgo.lineas.
  // «COLLATE no especificado en tabla temporal»: cada columna sin COLLATE es un caso (usuaria, 8 nov.).
  // «ISNULL posiblemente innecesario» como tabla: cada ISNULL es un caso (usuaria, 18 nov.).
  const porColumna = (hallazgo.regla === 'TEMPORAL_TEXTO_SIN_COLLATE'
    || (hallazgo.regla === 'ISNULL_VALIDAR_NULOS' && hallazgo.grupos?.length > 0)) && hallazgo.lineas?.length > 0;
  const lineas = porColumna
    ? [...new Set(hallazgo.lineas)].join(', ')
    : desglose.lineas || (hallazgo.lineas?.length > 1 ? hallazgo.lineas.join(', ') : null);
  const seccion = SECCIONES[hallazgo.seccion];
  // Hasta 4 líneas se muestran; con más, la cantidad de casos («20 casos»): se recorren desde «Ver en el código».
  const cantidadLineas = porColumna ? hallazgo.lineas.length : (lineas ? lineas.split(',').length : 1);
  // Columnas con su desglose de tipos («Misma columna con distinto tipo»): se muestran como tabla.
  const tablaTipos = Boolean(hallazgo.grupos?.length && hallazgo.grupos.every((grupo) => grupo.detalle));
  // Viñetas con sus propias líneas (tablas, columnas): se cuentan las viñetas, no las líneas («11 casos»).
  const porGrupos = porColumna ? null : etiquetaDeGrupos(hallazgo.grupos);
  const etiquetaLinea = (seccion ? `${seccion} · ` : '') + (porGrupos || (lineas
    ? (cantidadLineas > 4 ? `${cantidadLineas} casos` : `${lineas.includes(',') ? 'Líneas' : 'Línea'} ${lineas}`)
    : `Línea ${hallazgo.linea || 1}`));

  // «COLLATE no especificado en tabla temporal» desde 3 tablas: Tabla | Columnas sin COLLATE.
  const tablaCollate = !tablaTipos && collateEnTabla(hallazgo);
  const enTabla = tablaTipos || tablaCollate;
  // Si el texto no presenta la lista («…las siguientes…:»), sobre la tabla va su primera oración: el detalle ya está
  // en la tabla (ALTER, «Validar documentación existente»; texto de la usuaria, 20 nov.).
  const introTabla = enTabla && !intro ? (problema.match(/^[\s\S]*?[.?](?=\s+[A-ZÁÉÍÓÚÑ¿(]|$)/)?.[0] ?? problema) : null;
  // Tablas sin NOLOCK desde 3: cada tabla en su cajita, una al lado de otra (opción A de la usuaria, 8 nov.).
  const enCajitas = !enTabla && Boolean(intro) && Boolean(CAJITAS_DESDE[hallazgo.regla])
    && ocurrencias.length >= CAJITAS_DESDE[hallazgo.regla];

  return (
    <article className={`finding sev-${severidad}${enTabla ? ' finding-tabla' : ''}`}>
      <header className="finding-head">
        <h4 className="finding-title">{titulo}</h4>
        <span className="finding-head-side">
          {mostrarLinea && <span className="finding-line">{etiquetaLinea}</span>}
          <span className={`sev-pill sev-${severidad}`}>{etiquetaSeveridad(severidad)}</span>
          <BotonCopiar texto={textoParaCopiar(hallazgo, mostrarLinea)} etiqueta="Copiar observación" />
        </span>
      </header>

      <div className="finding-body">
        {(intro || introTabla) && <p className="finding-message">{intro || introTabla}</p>}
        {enTabla ? (
          tablaTipos
            ? <TablaTiposColumnas grupos={hallazgo.grupos} filaActiva={vinetaActiva} />
            : (
              <TablaColumnasSinCollate
                grupos={hallazgo.grupos}
                filaActiva={vinetaActiva}
                tituloColumnas={tituloDeColumnas(hallazgo.regla)}
              />
            )
        ) : enCajitas ? (
          <div className="lista-cajitas">
            {ocurrencias.map((texto) => <code key={texto} className="tabla-tipos-columna">{texto}</code>)}
          </div>
        ) : (
          <>
            {ocurrencias.length > 1 ? (
              <ul className="finding-list">
                {ocurrencias.map((texto, indice) => (
                  <li key={texto} className={indice === vinetaActiva ? 'ocurrencia-activa' : undefined}>
                    <MensajeResaltado texto={texto} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="finding-message"><MensajeResaltado texto={ocurrencias[0]} /></p>
            )}
          </>
        )}
        {solucion && (
          <p className="finding-fix">
            <span className="finding-label">Qué hacer:</span> <MensajeResaltado texto={solucion} />
          </p>
        )}
        {hallazgo.codigo && (
          <pre className="finding-code">
            {tokenizarSql(hallazgo.codigo).map((fragmento, indice) => (
              fragmento.tipo === 'texto'
                ? fragmento.valor
                : <span key={indice} className={`tok-${fragmento.tipo}`}>{fragmento.valor}</span>
            ))}
          </pre>
        )}
        {acciones?.(hallazgo)}
      </div>

    </article>
  );
}

// Pestañas de origen (opción B de la usuaria, 22 nov.): buenas prácticas de la Caja y lo que dice SQL Server.
const ORIGENES = {
  practicas: { titulo: 'Buenas prácticas', descripcion: 'Estándares y reglas de CAJA ICA', Icono: IconoEscudoCheck },
  validador: { titulo: 'Validador SQL Server', descripcion: 'Lector oficial de SQL Server', Icono: IconoBaseDatos },
};

function PestanasOrigen({ origen, cantidades, onElegir }) {
  return (
    <div className="origenes" role="tablist" aria-label="Origen de las observaciones">
      {Object.entries(ORIGENES).map(([id, { titulo, descripcion, Icono }]) => (
        <button
          key={id}
          type="button"
          role="tab"
          aria-selected={origen === id}
          className={`origen origen-${id}${origen === id ? ' activo' : ''}`}
          onClick={() => onElegir(id)}
        >
          <span className="origen-icono"><Icono /></span>
          <span className="origen-textos">
            <span className="origen-titulo">{titulo}</span>
            <span className="origen-descripcion">{descripcion}</span>
          </span>
          {/* Dos dígitos en cursiva, como los «01 02 03» de las tarjetas del encabezado (usuaria, 23 nov.). */}
          <span className="origen-cantidad">
            {cantidades[id] == null ? '—' : String(cantidades[id]).padStart(2, '0')}
          </span>
        </button>
      ))}
    </div>
  );
}

/**
 * El error concreto, en pocas palabras, para el título del aviso (usuaria, 23 nov.: el aviso repetía tres veces «no
 * se puede ejecutar» y el error real quedaba en letra chica). Del mensaje del validador se toma lo que pasó:
 * «…columna 1: Sintaxis incorrecta cerca de 'X'. Corregir…» → «Sintaxis incorrecta cerca de 'X'»;
 * «Se identificó que falta abrir el comentario del encabezado (/*): …» → «Falta abrir el comentario del encabezado (/*)».
 * Si no se reconoce, el nombre de la regla.
 */
function tituloDelError(hallazgo) {
  const mensaje = String(hallazgo?.mensaje || '');
  let titulo = '';
  // «Se identificó un error de sintaxis cerca de «X»: «texto de la línea» (línea N)…» (usuaria, 23 nov.).
  const cercaDe = mensaje.match(/^Se identificó un error de sintaxis (cerca de «[^»]*»)/);
  const sintaxis = mensaje.match(/^Se identificó un error de sintaxis[^:]*:\s*(.+?)\.(?:\s+Corregir|\s*$)/);
  const queFalta = mensaje.match(/^Se identificó que\s+(.+?)(?::\s|\.\s|\.$)/);
  if (cercaDe) titulo = `Error de sintaxis ${cercaDe[1]}`;
  else if (sintaxis) titulo = sintaxis[1];
  else if (queFalta) titulo = queFalta[1];
  if (!titulo || titulo.length > 90) return tituloHallazgo(hallazgo);
  return titulo.charAt(0).toUpperCase() + titulo.slice(1);
}

/**
 * Lo único que nunca queda escondido: si el Validador SQL Server encontró algo que haría fallar el código, se avisa
 * debajo de las pestañas, se esté en la que se esté. Diseño «Diagonal de marca» (idea 2, usuaria, 23 nov.), con el
 * rojo de marca y el mismo espacio de la línea de la idea 7: a la izquierda el veredicto con el corte diagonal del
 * encabezado; a la derecha el error real y la acción.
 */
function AvisoBloqueo({ criticos, enValidador, onVer }) {
  const [primero] = criticos;
  const mas = criticos.length - 1;
  return (
    <div className="aviso-bloqueo" role="alert">
      <div className="aviso-bloqueo-veredicto">
        <IconoCandado />
        <span>
          <span className="aviso-bloqueo-etiqueta">SQL Server</span>
          <strong className="aviso-bloqueo-veredicto-texto">No se puede crear</strong>
        </span>
      </div>
      <p className="aviso-bloqueo-texto">
        <strong className="aviso-bloqueo-titulo">{tituloDelError(primero)}</strong>
        <span className="aviso-bloqueo-detalle">
          Línea {primero.linea || 1}{mas > 0 && ` · y ${mas} ${mas === 1 ? 'error más' : 'errores más'}`}
          {' · '}corregirlo primero, ya que el resto de la revisión del validador depende de este error.
        </span>
      </p>
      {!enValidador && (
        <button type="button" className="aviso-bloqueo-boton" onClick={onVer}>
          Ver en el validador <IconoFlecha />
        </button>
      )}
    </div>
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
 * accionesHallazgo: (hallazgo) => contenido extra al pie de cada ficha (opcional).
 * vinetaActiva: (hallazgo) => índice de la viñeta que se está recorriendo en el código, o null (opcional).
 * validacion: resultado del Validador SQL Server ({disponible, alcance, hallazgos} o {disponible: false, motivo}).
 *   Si llega, los resultados se separan en las pestañas «Buenas prácticas» y «Validador SQL Server»; si no
 *   (undefined o null), el panel es el de siempre.
 */
export function PanelHallazgos({
  titulo,
  meta,
  estado,
  hallazgos = [],
  validacion,
  mensajeError,
  textos,
  mostrarLinea = true,
  accionesHallazgo,
  vinetaActiva,
}) {
  const [filtroElegido, setFiltro] = useState('todos');
  const [seccionElegida, setSeccion] = useState('tabla');
  // La pestaña de origen vale para el resultado en el que se eligió: una revisión nueva vuelve a «Buenas prácticas».
  const [origenPedido, setOrigenPedido] = useState(null);

  const conOrigenes = estado === 'listo' && Boolean(validacion);
  const validadorDisponible = Boolean(validacion?.disponible);
  const delValidador = validadorDisponible ? validacion.hallazgos ?? [] : [];
  const origen = conOrigenes && origenPedido?.para === hallazgos ? origenPedido.origen : 'practicas';
  const elegirOrigen = (nuevo) => {
    setOrigenPedido({ para: hallazgos, origen: nuevo });
    setFiltro('todos');
    setSeccion('tabla');
  };
  const activos = origen === 'validador' ? delValidador : hallazgos;
  const criticosValidador = conOrigenes
    ? delValidador.filter((hallazgo) => normalizarSeveridad(hallazgo.severidad) === 'critico')
    : [];

  // Si hay hallazgos de los índices (Tablas), se separan en pestañas «Tabla | Índices».
  const deIndices = activos.filter((hallazgo) => hallazgo.seccion === 'indices');
  const deTabla = activos.filter((hallazgo) => hallazgo.seccion !== 'indices');
  const conSecciones = deIndices.length > 0;
  // Si la pestaña elegida quedó vacía (nuevo análisis), se muestra la otra.
  const seccion = !conSecciones ? 'tabla'
    : seccionElegida === 'indices' || !deTabla.length ? 'indices' : 'tabla';
  const delaSeccion = !conSecciones ? activos : seccion === 'indices' ? deIndices : deTabla;

  const conteo = contarPorSeveridad(delaSeccion);
  const ordenados = ordenarHallazgos(delaSeccion);

  // Si el filtro elegido ya no tiene resultados (nuevo análisis), se vuelve a "Todos".
  const filtro = filtroElegido !== 'todos' && !conteo[filtroElegido] ? 'todos' : filtroElegido;
  const visibles = filtro === 'todos'
    ? ordenados
    : ordenados.filter((hallazgo) => normalizarSeveridad(hallazgo.severidad) === filtro);
  const hayHallazgos = estado === 'listo' && activos.length > 0;
  // Los riesgos identificados por Genesis (sin alerta de SQL Server) van aparte, debajo de los demás.
  // Los casos poco comunes (para validar con el DBA) van en su propio recuadro, al final (usuaria, 21 nov.).
  const pocoComunes = visibles.filter((hallazgo) => hallazgo.pocoComun);
  const normales = visibles.filter((hallazgo) => !hallazgo.complementario && !hallazgo.pocoComun);
  const complementarios = visibles.filter((hallazgo) => hallazgo.complementario && !hallazgo.pocoComun);

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
  } else if (estado === 'listo' && origen === 'validador' && !validadorDisponible) {
    contenido = (
      <EstadoVacio icono={<IconoBaseDatos />} titulo="El Validador SQL Server no está disponible en esta PC">
        {validacion.motivo} Las buenas prácticas se revisaron igual.
      </EstadoVacio>
    );
  } else if (estado === 'listo' && origen === 'validador' && !activos.length) {
    contenido = (
      <EstadoInicial
        variante="exito"
        titulo="Sin observaciones de SQL Server"
        descripcion="El lector oficial de SQL Server no encontró nada que observar en este código."
        pasos={[
          validacion.alcance === 'estructura'
            ? 'Se revisó que el código se pueda crear y ejecutar'
            : 'Se revisó la estructura, los errores silenciosos y el rendimiento',
          'No hay observaciones de ninguna severidad',
          'Revisa también la pestaña «Buenas prácticas»',
        ]}
      />
    );
  } else if (estado === 'listo' && !activos.length) {
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
    const fichas = (grupo, prefijo) => grupo.map((hallazgo, indice) => (
      <FilaHallazgo
        // El backend no envía un id; regla + línea + posición es estable por resultado.
        key={`${prefijo}-${hallazgo.regla}-${hallazgo.linea}-${indice}`}
        hallazgo={hallazgo}
        mostrarLinea={mostrarLinea}
        acciones={accionesHallazgo}
        vinetaActiva={vinetaActiva?.(hallazgo) ?? null}
      />
    ));
    const lista = (
      <div className="findings-list">
        {fichas(normales, seccion)}
        {complementarios.length > 0 && (
          <div className="riesgos-genesis">
            <EncabezadoSeccion
              nivel={3}
              etiqueta="Análisis complementario"
              titulo="Riesgos identificados por Genesis"
              descripcion={DESCRIPCION_RIESGOS}
            />
            {fichas(complementarios, `${seccion}-riesgo`)}
          </div>
        )}
        {pocoComunes.length > 0 && (
          <CasosPocoComunes cantidad={pocoComunes.length}>
            {fichas(pocoComunes, `${seccion}-poco-comun`)}
          </CasosPocoComunes>
        )}
      </div>
    );
    contenido = !conSecciones ? lista : (
      <div className="resultados-secciones">
        <div className="pestanas-seccion" role="tablist" aria-label="Origen de los hallazgos">
          {[
            { id: 'tabla', etiqueta: 'Tabla', cantidad: deTabla.length },
            { id: 'indices', etiqueta: 'Índices', cantidad: deIndices.length },
          ].map((opcion) => (
            <button
              key={opcion.id}
              type="button"
              role="tab"
              aria-selected={seccion === opcion.id}
              className={seccion === opcion.id ? 'pestana-seccion activa' : 'pestana-seccion'}
              disabled={!opcion.cantidad}
              onClick={() => {
                setSeccion(opcion.id);
                setFiltro('todos');
              }}
            >
              {opcion.etiqueta}
              <span className="pestana-seccion-cantidad">{opcion.cantidad}</span>
            </button>
          ))}
        </div>
        {lista}
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

  const textoTodos = [...normales, ...complementarios, ...pocoComunes]
    .map((h, i) => `${i + 1}. ${textoParaCopiar(h, mostrarLinea)}`).join('\n');

  return (
    <section className="results-panel" aria-live="polite" aria-busy={estado === 'cargando'}>
      <EncabezadoSeccion
        etiqueta="Paso 2 · Resultados"
        titulo={titulo}
        acciones={
          <>
            {meta && <span className="results-meta">{meta}</span>}
            {hayHallazgos && <BotonCopiar texto={textoTodos} etiqueta="Copiar todo" conTexto />}
          </>
        }
      />
      {conOrigenes && (
        <>
          <PestanasOrigen
            origen={origen}
            cantidades={{ practicas: hallazgos.length, validador: validadorDisponible ? delValidador.length : null }}
            onElegir={elegirOrigen}
          />
          {criticosValidador.length > 0 && (
            <AvisoBloqueo
              criticos={criticosValidador}
              enValidador={origen === 'validador'}
              onVer={() => elegirOrigen('validador')}
            />
          )}
          {origen === 'validador' && validacion.alcance === 'estructura' && validadorDisponible && (
            <p className="origen-nota">En Tablas y Diccionarios, el validador muestra solo lo que haría fallar el script.</p>
          )}
        </>
      )}
      {hayHallazgos ? (
        <div className="resultados-tablero">
          <div className="tablero-columna">
            <ResumenLateral
              conteo={conteo}
              total={delaSeccion.length}
              filtro={filtro}
              onFiltrar={setFiltro}
              origen={origen}
            />
          </div>
          {contenido}
        </div>
      ) : contenido}
    </section>
  );
}
