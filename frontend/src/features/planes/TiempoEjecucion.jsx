import { useState } from 'react';
import { NOMBRES_AREA_PLAN } from '../../config/planes';

/*
 * Tarjeta «Tiempo de ejecución» con velocímetro de instrumento clásico: suma la
 * duración (Duration del XML, en milisegundos) de todas las consultas del plan,
 * la pasa a segundos y la compara con el límite del área (Reportes o Negocio).
 * El límite se escribe o ajusta en la tarjeta y se guarda por área en este navegador.
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
      <title>{`Tiempo de ejecución: ${seg(totalS)}${limiteS != null ? ` de ${limiteS} s permitidos` : ''}`}</title>
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

/** Cajita del límite: − / valor / +, editable a mano. */
function ControlLimite({ nombreArea, limiteS, onCambiar }) {
  const [texto, setTexto] = useState(limiteS != null ? String(limiteS) : '');
  const paso = limiteS == null ? 1 : limiteS < 1 ? 0.1 : limiteS < 10 ? 0.5 : 1;
  const aplicar = (valor) => {
    const limpio = valor == null || Number.isNaN(valor) || valor <= 0 ? null : Math.round(valor * 100) / 100;
    setTexto(limpio != null ? String(limpio) : '');
    onCambiar(limpio);
  };
  return (
    <div className="tiempo-control">
      <span className="tiempo-etiqueta">Límite {nombreArea}</span>
      <div className="tiempo-caja">
        <button type="button" aria-label="Bajar el límite" onClick={() => aplicar((limiteS ?? paso * 2) - paso)}>−</button>
        <input
          type="text"
          inputMode="decimal"
          value={texto}
          placeholder="—"
          aria-label={`Límite de tiempo de ${nombreArea} en segundos`}
          onChange={(evento) => setTexto(evento.target.value)}
          onBlur={() => aplicar(texto.trim() === '' ? null : Number(texto.replace(',', '.')))}
          onKeyDown={(evento) => { if (evento.key === 'Enter') evento.currentTarget.blur(); }}
        />
        <span className="tiempo-unidad">s</span>
        <button type="button" aria-label="Subir el límite" onClick={() => aplicar((limiteS ?? 0) + paso)}>+</button>
      </div>
      {limiteS == null && <span className="tiempo-ayuda">Escribe el límite del área para compararlo.</span>}
    </div>
  );
}

export function TiempoEjecucion({ sentencias = [], area, limiteS = null, onCambiarLimite }) {
  const conTiempo = sentencias.filter((s) => s.duracionMs != null);
  if (!sentencias.length) return null;

  const nombreArea = NOMBRES_AREA_PLAN[area] ?? area;
  if (!conTiempo.length) {
    return (
      <section className="tiempo-plan tiempo-plan--vacio" aria-label="Tiempo de ejecución">
        <span className="tiempo-etiqueta">Tiempo de ejecución</span>
        <p className="tiempo-texto">El XML no trae tiempos (QueryTimeStats): es un plan estimado. Carga el plan real para medirlo.</p>
      </section>
    );
  }

  const totalS = conTiempo.reduce((suma, s) => suma + s.duracionMs, 0) / 1000;
  const cpuS = conTiempo.reduce((suma, s) => suma + (s.cpuMs ?? 0), 0) / 1000;
  const supera = limiteS != null && totalS > limiteS;
  const lenta = conTiempo.reduce((mayor, s) => (s.duracionMs > mayor.duracionMs ? s : mayor), conTiempo[0]);

  const cambiarLimite = (valor) => onCambiarLimite?.(area, valor);

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
        {sello && <div className="tiempo-encabezado">{sello}</div>}
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
        <ControlLimite key={area} nombreArea={nombreArea} limiteS={limiteS} onCambiar={cambiarLimite} />
      </div>
    </section>
  );
}
