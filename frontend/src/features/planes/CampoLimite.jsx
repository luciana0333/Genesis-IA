import { useState } from 'react';
import { IconoReloj, IconoSeveridadMedia } from '../../components/Iconos';

/**
 * Límite de tiempo del área (segundos), en el Paso 1: se fija antes de analizar
 * y vale para el plan suelto o para todo el lote. Se guarda por área en este navegador.
 */
export function CampoLimite({ id, nombreArea, limiteS, onCambiar }) {
  const [texto, setTexto] = useState(limiteS != null ? String(limiteS) : '');
  const paso = limiteS == null ? 1 : limiteS < 1 ? 0.1 : limiteS < 10 ? 0.5 : 1;
  const aplicar = (valor) => {
    const limpio = valor == null || Number.isNaN(valor) || valor <= 0 ? null : Math.round(valor * 100) / 100;
    setTexto(limpio != null ? String(limpio) : '');
    if (limpio !== limiteS) onCambiar(limpio);
  };

  return (
    <div className="field-group">
      <label className="field-label" htmlFor={id}>Límite de tiempo · {nombreArea}</label>
      <div className="limite-campo">
        <span className="limite-icono"><IconoReloj /></span>
        <button type="button" aria-label="Bajar el límite" onClick={() => aplicar((limiteS ?? paso * 2) - paso)}>−</button>
        <input
          id={id}
          type="text"
          inputMode="decimal"
          value={texto}
          placeholder="Sin límite"
          onChange={(evento) => setTexto(evento.target.value)}
          onBlur={() => aplicar(texto.trim() === '' ? null : Number(texto.replace(',', '.')))}
          onKeyDown={(evento) => { if (evento.key === 'Enter') evento.currentTarget.blur(); }}
        />
        <span className="limite-unidad">segundos</span>
        <button type="button" aria-label="Subir el límite" onClick={() => aplicar((limiteS ?? 0) + paso)}>+</button>
      </div>
      <p className="nota-base nota-base--campo">
        <IconoSeveridadMedia />
        Tiempo máximo permitido por plan; se fija antes de analizar.
      </p>
    </div>
  );
}
