import {
  IconoArchivos, IconoCargando, IconoCodigo, IconoErrorCirculo, IconoEscudoAlerta, IconoEscudoCheck, IconoFlecha, IconoLibro,
  IconoTabla, IconoVolver,
} from '../../components/Iconos';
import { MODULOS, nombreArchivo, pesoGravedad, tipoDe } from './archivos';
import { describirReferencia } from './enlace';
import { abrirEnModulo } from './traspaso';

const ICONOS = { tabla: IconoTabla, libro: IconoLibro, codigo: IconoCodigo, otro: IconoArchivos };
const SEVERIDADES = [
  { clave: 'critico', uno: 'crítica', varios: 'críticas', titulo: 'Críticas' },
  { clave: 'alto', uno: 'alta', varios: 'altas', titulo: 'Altas' },
  { clave: 'medio', uno: 'media', varios: 'medias', titulo: 'Medias' },
  { clave: 'bajo', uno: 'baja', varios: 'bajas', titulo: 'Bajas' },
];

function veredicto(total, conteo) {
  if (conteo.critico || conteo.alto) {
    const graves = conteo.critico + conteo.alto;
    return {
      icono: IconoEscudoAlerta,
      titulo: 'Requiere corrección',
      texto: conteo.critico
        ? `${conteo.critico} ${conteo.critico === 1 ? 'observación crítica' : 'observaciones críticas'}.`
        : `${graves} ${graves === 1 ? 'observación alta' : 'observaciones altas'}.`,
    };
  }
  if (total) return { icono: IconoEscudoCheck, titulo: 'Observaciones menores', texto: 'Solo medias y bajas.' };
  return { icono: IconoEscudoCheck, titulo: 'Todo en orden', texto: 'Ningún archivo tiene observaciones.' };
}

function CuentasArchivo({ conteo }) {
  const presentes = SEVERIDADES.filter(({ clave }) => conteo[clave]);
  if (!presentes.length) return <span className="bb-cuentas-vacio">Sin observaciones</span>;
  return (
    <span className="bb-cuentas">
      {presentes.map(({ clave, uno, varios }) => (
        <span key={clave} className={`bb-cuenta bb-sev-${clave}`}>
          <b>{conteo[clave]}</b> {conteo[clave] === 1 ? uno : varios}
        </span>
      ))}
    </span>
  );
}

function FilaResultado({ fila, numero, resultado }) {
  const { archivo } = fila;
  const Icono = ICONOS[tipoDe(archivo).icono] ?? IconoArchivos;
  const destino = MODULOS[resultado.revision.modulo];
  return (
    <li className="bb-fila">
      <span className="bb-fila-numero">{String(numero).padStart(2, '0')}</span>
      <span className="bb-icono-tipo"><Icono /></span>
      <span className="bb-fila-nombres">
        <span className="bb-archivo" title={archivo.ruta}>{nombreArchivo(archivo.ruta)}</span>
        <span className="bb-archivo-detalle">{tipoDe(archivo).etiqueta}</span>
      </span>
      <span className="bb-fila-estado">
        {resultado.estado === 'revisando' && <span className="bb-revisando"><IconoCargando className="bb-girando" />Revisando…</span>}
        {resultado.estado === 'error' && <span className="bb-fila-error"><IconoErrorCirculo />{resultado.mensaje}</span>}
        {resultado.estado === 'listo' && <CuentasArchivo conteo={resultado.conteo} />}
      </span>
      <button
        type="button"
        className="bb-abrir"
        disabled={resultado.estado === 'revisando'}
        onClick={() => abrirEnModulo(resultado.revision)}
      >
        Abrir en {destino.etiqueta}
        <IconoFlecha />
      </button>
    </li>
  );
}

/** Paso 3: tablero dividido (columna oscura con el total y el veredicto; a la derecha, cada archivo). */
export function ResultadoBitbucket({ cambio, filas, resultados, onVolver, onNuevoEnlace }) {
  const revisadas = filas.filter((fila) => resultados[fila.archivo.id]);
  const listos = revisadas.filter((fila) => resultados[fila.archivo.id].estado === 'listo');
  const enCurso = revisadas.filter((fila) => resultados[fila.archivo.id].estado === 'revisando').length;
  const conteo = { critico: 0, alto: 0, medio: 0, bajo: 0 };
  for (const fila of listos) {
    for (const { clave } of SEVERIDADES) conteo[clave] += resultados[fila.archivo.id].conteo[clave];
  }
  const total = Object.values(conteo).reduce((suma, valor) => suma + valor, 0);
  // Los más graves primero; mientras se revisa, se mantiene el orden de la lista.
  const ordenadas = enCurso
    ? revisadas
    : [...revisadas].sort((a, b) => pesoGravedad(resultados[b.archivo.id].conteo) - pesoGravedad(resultados[a.archivo.id].conteo));
  const juicio = veredicto(total, conteo);
  const IconoVeredicto = juicio.icono;

  return (
    <section className="bb-tablero" aria-labelledby="bb-resultado-titulo" aria-busy={enCurso > 0}>
      <aside className="bb-lateral">
        <p className="bb-etiqueta bb-etiqueta-clara">Resultado</p>
        <p className="bb-total">{total}</p>
        <p className="bb-total-detalle">
          {total === 1 ? 'observación' : 'observaciones'} en {revisadas.length} {revisadas.length === 1 ? 'archivo' : 'archivos'}
          <span className="bb-total-origen">{describirReferencia(cambio.origen)} · {cambio.origen.repositorio}</span>
        </p>
        {enCurso > 0 ? (
          <p className="bb-veredicto">
            <IconoCargando className="bb-girando" />
            <span><b>Revisando</b>{revisadas.length - enCurso} de {revisadas.length} archivos listos.</span>
          </p>
        ) : (
          <p className={conteo.critico || conteo.alto ? 'bb-veredicto bb-veredicto-alerta' : 'bb-veredicto'}>
            <IconoVeredicto />
            <span><b>{juicio.titulo}</b>{juicio.texto}</span>
          </p>
        )}
        <ul className="bb-severidades">
          {SEVERIDADES.map(({ clave, titulo }) => (
            <li key={clave} className={`bb-sev-${clave}`}><span>{titulo}</span><b>{conteo[clave]}</b></li>
          ))}
        </ul>
        <div className="bb-lateral-acciones">
          <button type="button" className="bb-enlace-claro" onClick={onVolver}><IconoVolver />Volver a la lista</button>
          <button type="button" className="bb-enlace-claro" onClick={onNuevoEnlace}>Revisar otro link</button>
        </div>
      </aside>

      <div className="bb-principal">
        <header className="bb-seccion-cabecera bb-sin-relleno">
          <p className="bb-etiqueta">Archivos revisados</p>
          <h2 id="bb-resultado-titulo" className="bb-seccion-titulo">Detalle por archivo</h2>
          <p className="bb-seccion-detalle">Ordenados de mayor a menor gravedad. «Abrir en …» lleva al módulo con el código ya pegado.</p>
        </header>
        <ol className="bb-filas">
          {ordenadas.map((fila, indice) => (
            <FilaResultado key={fila.archivo.id} fila={fila} numero={indice + 1} resultado={resultados[fila.archivo.id]} />
          ))}
        </ol>
      </div>
    </section>
  );
}
