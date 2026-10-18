import { NOMBRES_AREA_PLAN } from '../../config/planes';
import { formatearLimite } from './formatoLimite';

/*
 * Tarjeta «Tiempo de ejecución» con velocímetro de instrumento clásico: suma la
 * duración (Duration del XML, en milisegundos) de todas las consultas del plan,
 * la pasa a segundos y la compara con el límite del área (Reportes o Negocio).
 * El límite se fija en el Paso 1 (antes de analizar); aquí solo se muestra.
 */

const ANCHO = 280;
const CX = 140;
const CY = 150;
const R = 110;
const MARCAS = 30; // marcas finas; cada 5, una gruesa con su número
function seg(valor) {
  const decimales = valor < 10 ? 2 : 1;
  return `${valor.toLocaleString('en-US', { minimumFractionDigits: decimales, maximumFractionDigits: decimales })} s`;
}

/** Punto del arco para una fracción entre 0 (izquierda) y 1 (derecha). */
function punto(fraccion, radio = R) {
  const angulo = Math.PI * (1 - Math.min(Math.max(fraccion, 0), 1));
  return [CX + radio * Math.cos(angulo), CY - radio * Math.sin(angulo)];
}

function arco(desde, hasta, radio = R) {
  const [x1, y1] = punto(desde, radio);
  const [x2, y2] = punto(hasta, radio);
  return `M${x1.toFixed(1)} ${y1.toFixed(1)} A${radio} ${radio} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
}

/** Escala «redonda» (6 divisiones de 1, 2, 2.5 o 5 × 10ⁿ) que contenga el valor con holgura. */
function escalaPara(valor) {
  const paso = valor / 6;
  const potencia = 10 ** Math.floor(Math.log10(paso || 1));
  const redondo = [1, 2, 2.5, 5, 10].find((m) => m * potencia >= paso) * potencia;
  return redondo * 6;
}

function etiquetaEscala(valor) {
  return valor >= 10 ? String(Math.round(valor)) : String(Number(valor.toFixed(2)));
}

function FlechaLimite({ fraccion }) {
  const angulo = Math.PI * (1 - fraccion);
  const [ax, ay] = punto(fraccion, R + 8);
  const ex = Math.cos(angulo) * 8;
  const ey = Math.sin(angulo) * 8;
  const nx = Math.sin(angulo) * 5;
  const ny = Math.cos(angulo) * 5;
  return <polygon points={`${ax},${ay} ${ax + ex + nx},${ay - ey + ny} ${ax + ex - nx},${ay - ey - ny}`} className="tiempo-flecha-limite" />;
}

function Velocimetro({ totalS, limiteS }) {
  const maximo = escalaPara(Math.max(totalS, limiteS ?? 0) * 1.15);
  const fTotal = totalS / maximo;
  const fLimite = limiteS != null ? limiteS / maximo : null;
  const anguloAguja = Math.PI * (1 - Math.min(fTotal, 1));
  const [px, py] = punto(fTotal, R - 14);
  const bx = Math.sin(anguloAguja) * 6;
  const by = Math.cos(anguloAguja) * 6;

  return (
    <svg viewBox={`0 0 ${ANCHO} 192`} className="tiempo-velocimetro" role="img">
      <title>{`Tiempo de ejecución: ${seg(totalS)}${limiteS != null ? ` de ${formatearLimite(limiteS)} permitidos` : ''}`}</title>
      <path d={arco(0, 1)} className="tiempo-banda" />
      {fLimite != null && fLimite < 1 && <path d={arco(fLimite, 1)} className="tiempo-banda-roja" />}
      <path d={arco(0, Math.min(fTotal, 1))} className="tiempo-avance" />
      {Array.from({ length: MARCAS + 1 }, (_, i) => {
        const f = i / MARCAS;
        const gruesa = i % 5 === 0;
        const [x1, y1] = punto(f, R - 9);
        const [x2, y2] = punto(f, R - (gruesa ? 22 : 16));
        const roja = fLimite != null && f > fLimite + 1e-9;
        const [tx, ty] = punto(f, R - 36);
        return (
          <g key={i}>
            <line x1={x1} y1={y1} x2={x2} y2={y2} className={`tiempo-marca${gruesa ? ' gruesa' : ''}${roja ? ' roja' : ''}`} />
            {gruesa && <text x={tx} y={ty + 4} textAnchor="middle" className="tiempo-escala">{etiquetaEscala(f * maximo)}</text>}
          </g>
        );
      })}
      {fLimite != null && fLimite <= 1 && <FlechaLimite fraccion={fLimite} />}
      <polygon points={`${CX + bx},${CY + by} ${px},${py} ${CX - bx},${CY - by}`} className="tiempo-aguja" />
      <circle cx={CX} cy={CY} r={9} className="tiempo-eje" />
      <circle cx={CX} cy={CY} r={3} fill="#ffffff" />
      <rect x={CX - 48} y={162} width={96} height={27} className="tiempo-lectura" />
      <text x={CX} y={180.5} textAnchor="middle" className="tiempo-lectura-texto">{seg(totalS)}</text>
    </svg>
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

  return (
    <section className={`tiempo-plan${supera ? ' supera' : ''}`} aria-label="Tiempo de ejecución">
      <div className="tiempo-esfera">
        <Velocimetro totalS={totalS} limiteS={limiteS} />
      </div>
      <div className="tiempo-lado">
        {/* Arriba, el límite con el que se revisó; a la derecha, el resultado. */}
        <div className="tiempo-encabezado">
          <LimiteFijo nombreArea={nombreArea} limiteS={limiteS} />
          {sello}
        </div>
        <div className="tiempo-datos">
          <div>
            <span className="tiempo-etiqueta">{limiteS != null && !supera ? 'Margen' : 'Exceso'}</span>
            <strong className={supera ? 'rojo' : undefined}>{exceso}</strong>
          </div>
          <div>
            <span className="tiempo-etiqueta">Consultas</span>
            <strong>
              {conTiempo.length}
              {conTiempo.length > 1 && <small> · C{lenta.numero} {seg(lenta.duracionMs / 1000)}</small>}
            </strong>
          </div>
          <div>
            <span className="tiempo-etiqueta">CPU</span>
            <strong>{seg(cpuS)}</strong>
          </div>
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
