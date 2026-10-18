import { useState } from 'react';
import { IconoAumentar, IconoDisminuir, IconoReloj, IconoSeveridadMedia } from '../../components/Iconos';
import { partesLimite } from './formatoLimite';

// Dos dígitos, como un cronómetro (00 : 52); los segundos con decimales quedan tal cual.
const textoDe = (valor) => (valor == null ? '' : Number.isInteger(valor) ? String(valor).padStart(2, '0') : String(valor));
const numero = (texto) => (texto.trim() === '' ? 0 : Number(texto.replace(',', '.')));

/**
 * Límite de tiempo del área en minutos y segundos, en el Paso 1: se fija antes de
 * analizar y vale para el plan suelto o para todo el lote. Se guarda en segundos,
 * por área, en este navegador.
 */
export function CampoLimite({ id, nombreArea, limiteS, onCambiar }) {
  const inicial = partesLimite(limiteS);
  const [minutos, setMinutos] = useState(textoDe(inicial.minutos));
  const [segundos, setSegundos] = useState(textoDe(inicial.segundos));
  const paso = limiteS == null ? 1 : limiteS < 1 ? 0.1 : limiteS < 10 ? 0.5 : 1;

  const aplicar = (valor) => {
    const limpio = valor == null || Number.isNaN(valor) || valor <= 0 ? null : Math.round(valor * 100) / 100;
    const partes = partesLimite(limpio);
    setMinutos(textoDe(partes.minutos));
    setSegundos(textoDe(partes.segundos));
    if (limpio !== limiteS) onCambiar(limpio);
  };

  // Al salir de las casillas se juntan: 1 min 75 s queda como 2 min 15 s.
  const alSalir = (evento) => {
    if (evento.currentTarget.contains(evento.relatedTarget)) return;
    if (minutos.trim() === '' && segundos.trim() === '') {
      aplicar(null);
      return;
    }
    aplicar(numero(minutos) * 60 + numero(segundos));
  };
  const alPresionar = (evento) => {
    if (evento.key === 'Enter') evento.currentTarget.blur();
  };

  return (
    <div className="field-group">
      <label className="field-label" htmlFor={id}>Límite de tiempo · {nombreArea}</label>
      <div className="limite-campo" onBlur={alSalir}>
        <span className="limite-icono" aria-hidden="true"><IconoReloj /></span>
        <div className="limite-valores">
          <input
            id={id}
            type="text"
            inputMode="numeric"
            value={minutos}
            placeholder="00"
            aria-label={`Minutos del límite de ${nombreArea}`}
            onChange={(evento) => setMinutos(evento.target.value)}
            onFocus={(evento) => evento.target.select()}
            onKeyDown={alPresionar}
          />
          <span className="limite-unidad">MIN</span>
          <span className="limite-divisor" aria-hidden="true" />
          <input
            type="text"
            inputMode="decimal"
            value={segundos}
            placeholder="00"
            aria-label={`Segundos del límite de ${nombreArea}`}
            onChange={(evento) => setSegundos(evento.target.value)}
            onFocus={(evento) => evento.target.select()}
            onKeyDown={alPresionar}
          />
          <span className="limite-unidad">SEG</span>
        </div>
        <div className="limite-flechas">
          <button type="button" aria-label="Subir el límite" onClick={() => aplicar((limiteS ?? 0) + paso)}>
            <IconoAumentar />
          </button>
          <button type="button" aria-label="Bajar el límite" onClick={() => aplicar((limiteS ?? paso * 2) - paso)}>
            <IconoDisminuir />
          </button>
        </div>
      </div>
      <p className="nota-base nota-base--campo">
        <IconoSeveridadMedia />
        Tiempo máximo permitido por plan; se fija antes de analizar.
      </p>
    </div>
  );
}
