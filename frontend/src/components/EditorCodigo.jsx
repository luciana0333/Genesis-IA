import { useRef } from 'react';
import { tokenizarSql } from '../utils/resaltadoSql';

function contarLineas(texto) {
  let lineas = 1;
  for (let i = 0; i < texto.length; i += 1) {
    if (texto.charCodeAt(i) === 10) lineas += 1;
  }
  return lineas;
}

/**
 * Área de texto para SQL con numeración de líneas, colores de sintaxis y
 * contador. Detrás del textarea (con el texto transparente) se dibuja el mismo
 * código coloreado; ambos usan la misma letra y medidas para quedar alineados.
 * Las líneas no se ajustan (wrap="off") para que la numeración siempre coincida.
 */
export function EditorCodigo({ id, valor, onCambiar, filas = 12, placeholder, etiquetaAccesible }) {
  const numeracionRef = useRef(null);
  const resaltadoRef = useRef(null);
  const lineas = contarLineas(valor);
  const fragmentos = tokenizarSql(valor);

  const sincronizarDesplazamiento = (evento) => {
    const { scrollTop, scrollLeft } = evento.target;
    if (numeracionRef.current) numeracionRef.current.scrollTop = scrollTop;
    if (resaltadoRef.current) {
      resaltadoRef.current.scrollTop = scrollTop;
      resaltadoRef.current.scrollLeft = scrollLeft;
    }
  };

  return (
    <div className="code-editor">
      <div className="code-surface">
        <div className="code-gutter" ref={numeracionRef} aria-hidden="true">
          {Array.from({ length: lineas }, (_, indice) => <span key={indice}>{indice + 1}</span>)}
        </div>
        <div className="code-input">
          <pre className="code-highlight" ref={resaltadoRef} aria-hidden="true">
            {fragmentos.map((fragmento, indice) => (
              fragmento.tipo === 'texto'
                ? fragmento.valor
                : <span key={indice} className={`tok-${fragmento.tipo}`}>{fragmento.valor}</span>
            ))}
            {/* Un salto final evita que la última línea vacía quede sin altura. */}
            {'\n'}
          </pre>
          <textarea
            id={id}
            rows={filas}
            wrap="off"
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            placeholder={placeholder}
            aria-label={etiquetaAccesible}
            value={valor}
            onChange={(evento) => onCambiar(evento.target.value)}
            onScroll={sincronizarDesplazamiento}
          />
        </div>
      </div>
      <div className="code-footer">
        <span>SQL Server · T-SQL</span>
        <span>{lineas} {lineas === 1 ? 'línea' : 'líneas'} · {valor.length.toLocaleString()} caracteres</span>
      </div>
    </div>
  );
}
