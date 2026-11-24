import { useState } from 'react';
import { IconoCopiado, IconoCopiar } from './Iconos';

/**
 * «Copiar consulta de validación»: copia la consulta que la observación trae lista para ejecutar en SQL Server
 * (Genesis no se conecta a la base): si las columnas del ISNULL aceptan NULL, el tipo real de las columnas
 * comparadas o, en Diccionarios, qué descripciones ya están registradas (23 nov.).
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
