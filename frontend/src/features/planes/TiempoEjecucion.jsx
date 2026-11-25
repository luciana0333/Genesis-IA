import { NOMBRES_AREA_PLAN } from '../../config/planes';
import { formatearLimite } from './formatoLimite';

/*
 * Tarjeta «Tiempo de ejecución»: suma la duración (Duration del XML, en milisegundos) de todas las consultas
 * del plan, la pasa a segundos y la compara con el límite del área (Reportes o Negocio). El límite se fija en
 * el Paso 1 (antes de analizar); aquí solo se muestra. Diseño elegido por la usuaria (idea 2, 25 nov.): un
 * anillo fino en el rojo de la Caja con el tiempo al centro y los datos en cuadritos con su «01» en cursiva.
 */

const RADIO = 42;
const PERIMETRO = 2 * Math.PI * RADIO;

function seg(valor) {
  const decimales = valor < 10 ? 2 : 1;
  return `${valor.toLocaleString('en-US', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })} s`;
}

/** Anillo: la parte roja es cuánto del límite se usó (lleno si lo supera). */
function Anillo({ totalS, limiteS }) {
  const fraccion = limiteS ? Math.min(totalS / limiteS, 1) : 0;
  // Un tiempo mínimo igual se ve: un punto rojo al inicio del anillo.
  const largo = fraccion > 0 ? Math.max(fraccion * PERIMETRO, 2.5) : 0;
  return (
    <div className="tiempo-anillo">
      <svg viewBox="0 0 100 100" role="img">
        <title>{`Tiempo de ejecución: ${seg(totalS)}${limiteS != null ? ` de ${formatearLimite(limiteS)} permitidos` : ''}`}</title>
        <circle cx="50" cy="50" r={RADIO} className="tiempo-anillo-fondo" />
        {largo > 0 && (
          <circle cx="50" cy="50" r={RADIO} className="tiempo-anillo-avance"
            strokeDasharray={`${largo} ${PERIMETRO}`} transform="rotate(-90 50 50)" />
        )}
      </svg>
      <div className="tiempo-anillo-centro">
        <strong>{seg(totalS)}</strong>
        <span>{limiteS != null ? `de ${formatearLimite(limiteS)}` : 'Sin límite'}</span>
      </div>
    </div>
  );
}

/** Límite del área, solo para leer: se fija en el Paso 1, antes de analizar. */
function LimiteFijo({ nombreArea, limiteS }) {
  return (
    <div className="tiempo-control">
      <span className="tiempo-etiqueta">Límite {nombreArea}</span>
      <strong className={limiteS != null ? 'tiempo-limite-valor' : 'tiempo-limite-valor vacio'}>
        {limiteS != null ? formatearLimite(limiteS) : 'Sin límite definido'}
      </strong>
    </div>
  );
}

export function TiempoEjecucion({ sentencias = [], area, limiteS = null }) {
  const conTiempo = sentencias.filter((s) => s.duracionMs != null);
  if (!sentencias.length) return null;

  const nombreArea = NOMBRES_AREA_PLAN[area] ?? area;
  if (!conTiempo.length) {
    return (
      <section className="tiempo-plan tiempo-plan--vacio" aria-label="Tiempo de ejecución">
        <span className="tiempo-etiqueta">Tiempo de ejecución</span>
        <p className="tiempo-texto">El XML no trae tiempos (QueryTimeStats): puede ser un plan estimado o de una versión de SQL Server que no los registra. Carga el plan real para medirlo.</p>
      </section>
    );
  }

  const totalS = conTiempo.reduce((suma, s) => suma + s.duracionMs, 0) / 1000;
  const cpuS = conTiempo.reduce((suma, s) => suma + (s.cpuMs ?? 0), 0) / 1000;
  const supera = limiteS != null && totalS > limiteS;
  const lenta = conTiempo.reduce((mayor, s) => (s.duracionMs > mayor.duracionMs ? s : mayor), conTiempo[0]);

  let sello = null;
  if (limiteS != null) {
    sello = supera
      ? <span className="tiempo-sello supera">Supera el límite · {(totalS / limiteS).toFixed(1)}×</span>
      : <span className="tiempo-sello">Dentro del límite · {Math.round((totalS / limiteS) * 100)}%</span>;
  }

  let exceso = '—';
  if (limiteS != null) exceso = supera ? `+${seg(totalS - limiteS)}` : seg(limiteS - totalS);

  const datos = [
    { etiqueta: limiteS != null && !supera ? 'Margen' : 'Exceso', valor: exceso, rojo: supera },
    { etiqueta: 'Consultas', valor: String(conTiempo.length) },
    ...(conTiempo.length > 1 ? [{ etiqueta: `Más lenta · Consulta ${lenta.numero}`, valor: seg(lenta.duracionMs / 1000) }] : []),
    { etiqueta: 'CPU', valor: seg(cpuS) },
  ];

  return (
    <section className={`tiempo-plan${supera ? ' supera' : ''}`} aria-label="Tiempo de ejecución">
      <div className="tiempo-esfera">
        <Anillo totalS={totalS} limiteS={limiteS} />
      </div>
      <div className="tiempo-lado">
        {/* Arriba, el límite con el que se revisó; a la derecha, el resultado. */}
        <div className="tiempo-encabezado">
          <LimiteFijo nombreArea={nombreArea} limiteS={limiteS} />
          {sello}
        </div>
        <div className="tiempo-datos">
          {datos.map((dato, indice) => (
            <div key={dato.etiqueta}>
              <i className="tiempo-numero">{String(indice + 1).padStart(2, '0')}</i>
              <span className="tiempo-etiqueta">{dato.etiqueta}</span>
              <strong className={dato.rojo ? 'rojo' : undefined}>{dato.valor}</strong>
            </div>
          ))}
        </div>
        <p className="tiempo-nota">
          {limiteS == null
            ? 'Indica el límite en el Paso 1 para comparar el tiempo del plan.'
            : `Suma la duración de ${conTiempo.length === 1 ? 'la consulta' : `las ${conTiempo.length} consultas`} y la compara con el límite del área.`}
        </p>
      </div>
    </section>
  );
}
