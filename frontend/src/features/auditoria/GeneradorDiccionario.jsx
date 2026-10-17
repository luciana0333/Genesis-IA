import { useState } from 'react';
import { IconoArchivo, IconoCopiado, IconoCopiar } from '../../components/Iconos';
import { tokenizarSql } from '../../utils/resaltadoSql';

/**
 * «Generar diccionario faltante»: muestra, al pie de la observación, el script
 * sp_addextendedproperty de lo que falta documentar, listo para completar las
 * descripciones y copiar.
 */
export function GeneradorDiccionario({ faltante }) {
  const [abierto, setAbierto] = useState(false);
  const [copiado, setCopiado] = useState(false);
  const cantidad = faltante.elementos.length;

  const alCopiar = async () => {
    try {
      await navigator.clipboard.writeText(faltante.script);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1600);
    } catch {
      setCopiado(false);
    }
  };

  if (!abierto) {
    return (
      <button type="button" className="generador-abrir" onClick={() => setAbierto(true)}>
        <IconoArchivo />
        Generar diccionario faltante
      </button>
    );
  }

  return (
    <section className="generador" aria-label="Diccionario faltante">
      <header className="generador-cabecera">
        <div>
          <p className="generador-etiqueta">Script sugerido</p>
          <p className="generador-resumen">
            {cantidad} {cantidad === 1 ? 'sentencia' : 'sentencias'} · {faltante.elementos.join(', ')}
          </p>
        </div>
        <div className="generador-acciones">
          <button type="button" className="generador-boton generador-boton--principal" onClick={alCopiar}>
            {copiado ? <IconoCopiado /> : <IconoCopiar />}
            {copiado ? 'Copiado' : 'Copiar script'}
          </button>
          <button type="button" className="generador-boton" onClick={() => setAbierto(false)}>Ocultar</button>
        </div>
      </header>
      <pre className="generador-codigo">
        {tokenizarSql(faltante.script).map((fragmento, indice) => (
          fragmento.tipo === 'texto'
            ? fragmento.valor
            : <span key={indice} className={`tok-${fragmento.tipo}`}>{fragmento.valor}</span>
        ))}
      </pre>
      <p className="generador-nota">
        Completar cada descripción donde dice «Completar» antes de ejecutar el script: si se deja vacía, la revisión
        la marcará como descripción vacía.
      </p>
    </section>
  );
}
