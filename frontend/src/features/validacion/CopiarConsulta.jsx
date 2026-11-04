import { useState } from 'react';
import { IconoCopiado, IconoCopiar } from '../../components/Iconos';

/**
 * «Copiar consulta de validación»: copia la consulta que muestra si las columnas del ISNULL aceptan NULL,
 * lista para ejecutar en SQL Server (Genesis no se conecta a la base).
 */
export function CopiarConsulta({ consulta }) {
  const [copiada, setCopiada] = useState(false);
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(consulta);
      setCopiada(true);
      setTimeout(() => setCopiada(false), 2000);
    } catch {
      setCopiada(false);
    }
  };
  return (
    <button type="button" className="ver-en-codigo" onClick={copiar} title={consulta}>
      {copiada ? <IconoCopiado /> : <IconoCopiar />}
      {copiada ? 'Consulta copiada' : 'Copiar consulta de validación'}
    </button>
  );
}
