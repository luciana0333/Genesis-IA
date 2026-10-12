import { LIMITES_TIEMPO_PLAN, NOMBRES_AREA_PLAN } from '../../config/planes';

/*
 * Tarjeta «Tiempo de ejecución» con velocímetro: suma la duración (Duration del
 * XML, en milisegundos) de todas las consultas del plan, la pasa a segundos y la
 * compara con el límite del área elegida (Reportes o Negocio).
 */

const CENTRO_X = 115;
const CENTRO_Y = 120;
const RADIO = 90;

function segundos(ms) {
  const valor = ms / 1000;
  return `${valor.toLocaleString('en-US', { maximumFractionDigits: valor < 10 ? 2 : 1, minimumFractionDigits: valor < 10 ? 2 : 1 })} s`;
}

/** Punto del arco (de izquierda a derecha) para una fracción entre 0 y 1. */
function punto(fraccion) {
  const angulo = Math.PI * (1 - Math.min(Math.max(fraccion, 0), 1));
  return { x: CENTRO_X + RADIO * Math.cos(angulo), y: CENTRO_Y - RADIO * Math.sin(angulo) };
}

function arco(desde, hasta) {
  const a = punto(desde);
  const b = punto(hasta);
  return `M${a.x.toFixed(2)} ${a.y.toFixed(2)} A${RADIO} ${RADIO} 0 0 1 ${b.x.toFixed(2)} ${b.y.toFixed(2)}`;
}

export function TiempoEjecucion({ sentencias = [], area }) {
  const conTiempo = sentencias.filter((s) => s.duracionMs != null);
  if (!sentencias.length) return null;

  const nombreArea = NOMBRES_AREA_PLAN[area] ?? area;
  if (!conTiempo.length) {
    return (
      <section className="tiempo-plan" aria-label="Tiempo de ejecución">
        <span className="tiempo-etiqueta">Tiempo de ejecución</span>
        <p className="tiempo-texto">El XML no trae tiempos (QueryTimeStats): es un plan estimado. Carga el plan real para medirlo.</p>
      </section>
    );
  }

  const totalMs = conTiempo.reduce((suma, s) => suma + s.duracionMs, 0);
  const cpuMs = conTiempo.reduce((suma, s) => suma + (s.cpuMs ?? 0), 0);
  const compilacionMs = sentencias.reduce((suma, s) => suma + (s.compilacionMs ?? 0), 0);
  const limiteS = LIMITES_TIEMPO_PLAN[area] ?? null;
  const limiteMs = limiteS != null ? limiteS * 1000 : null;
  const supera = limiteMs != null && totalMs > limiteMs;

  // Escala del velocímetro: un poco más que el mayor entre el total y el límite.
  const escala = Math.max(totalMs, limiteMs ?? 0) * 1.15 || 1;
  const fraccionTotal = totalMs / escala;
  const fraccionLimite = limiteMs != null ? limiteMs / escala : null;
  const tramoNormal = fraccionLimite != null ? Math.min(fraccionTotal, fraccionLimite) : fraccionTotal;
  const marca = fraccionLimite != null ? { a: punto(fraccionLimite), angulo: Math.PI * (1 - fraccionLimite) } : null;

  const lenta = conTiempo.reduce((mayor, s) => (s.duracionMs > mayor.duracionMs ? s : mayor), conTiempo[0]);
  let resumen;
  if (limiteMs == null) resumen = 'SIN LÍMITE DEFINIDO';
  else if (supera) resumen = `${(totalMs / limiteMs).toFixed(1)}× EL LÍMITE`;
  else resumen = `${Math.round((totalMs / limiteMs) * 100)}% DEL LÍMITE`;

  return (
    <section className={`tiempo-plan${supera ? ' supera' : ''}`} aria-label="Tiempo de ejecución">
      <svg viewBox="0 0 230 140" className="tiempo-velocimetro" role="img">
        <title>{`Tiempo de ejecución: ${segundos(totalMs)}${limiteS != null ? ` de ${limiteS} s permitidos` : ''}`}</title>
        <path d={arco(0, 1)} className="tiempo-fondo" />
        {tramoNormal > 0 && <path d={arco(0, tramoNormal)} className="tiempo-normal" />}
        {supera && <path d={arco(fraccionLimite, fraccionTotal)} className="tiempo-exceso" />}
        {marca && (
          <>
            <line
              x1={CENTRO_X + (RADIO - 14) * Math.cos(marca.angulo)}
              y1={CENTRO_Y - (RADIO - 14) * Math.sin(marca.angulo)}
              x2={CENTRO_X + (RADIO + 14) * Math.cos(marca.angulo)}
              y2={CENTRO_Y - (RADIO + 14) * Math.sin(marca.angulo)}
              className="tiempo-marca"
            />
            <text
              x={CENTRO_X + (RADIO + 24) * Math.cos(marca.angulo)}
              y={CENTRO_Y - (RADIO + 24) * Math.sin(marca.angulo)}
              textAnchor="middle"
              className="tiempo-marca-texto"
            >
              {`${limiteS} s`}
            </text>
          </>
        )}
        <text x={CENTRO_X} y={104} textAnchor="middle" className="tiempo-cifra">{segundos(totalMs)}</text>
        <text x={CENTRO_X} y={124} textAnchor="middle" className="tiempo-pie">{resumen}</text>
      </svg>

      <div className="tiempo-detalle">
        <div className="tiempo-encabezado">
          <span className="tiempo-etiqueta">Tiempo de ejecución</span>
          {limiteMs != null && (
            <span className={supera ? 'tiempo-sello supera' : 'tiempo-sello'}>
              {supera ? 'Supera el límite' : 'Dentro del límite'}
            </span>
          )}
        </div>
        <p className="tiempo-texto">
          {limiteMs == null
            ? <>El área <b>{nombreArea}</b> aún no tiene un límite de tiempo definido.</>
            : <>Límite del área <b>{nombreArea}</b>: {limiteS} s.</>}
          {' '}
          {supera && <>El plan lo supera por <b className="tiempo-rojo">{segundos(totalMs - limiteMs)}</b>.</>}
          {limiteMs != null && !supera && <>Quedan <b>{segundos(limiteMs - totalMs)}</b> de margen.</>}
        </p>
        <p className="tiempo-texto">
          {conTiempo.length === 1
            ? 'El plan tiene una sola consulta.'
            : <>Suma {conTiempo.length} consultas; la más lenta es la <b>{lenta.numero}</b> ({segundos(lenta.duracionMs)}).</>}
        </p>
        <div className="tiempo-datos">
          <span>CPU <b>{segundos(cpuMs)}</b></span>
          <span>Compilación <b>{segundos(compilacionMs)}</b></span>
        </div>
      </div>
    </section>
  );
}
