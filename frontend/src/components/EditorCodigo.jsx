import { useRef } from 'react';

function contarLineas(texto) {
  let lineas = 1;
  for (let i = 0; i < texto.length; i += 1) {
    if (texto.charCodeAt(i) === 10) lineas += 1;
  }
  return lineas;
}

/**
 * Área de texto para SQL con numeración de líneas y contador.
 * Las líneas no se ajustan (wrap="off") para que la numeración siempre
 * coincida con el código, igual que en un editor.
 */
export function EditorCodigo({ id, valor, onCambiar, filas = 12, placeholder, etiquetaAccesible }) {
  const numeracionRef = useRef(null);
  const lineas = contarLineas(valor);

  const sincronizarDesplazamiento = (evento) => {
    if (numeracionRef.current) numeracionRef.current.scrollTop = evento.target.scrollTop;
  };

  return (
    <div className="code-editor">
      <div className="code-surface">
        <div className="code-gutter" ref={numeracionRef} aria-hidden="true">
          {Array.from({ length: lineas }, (_, indice) => <span key={indice}>{indice + 1}</span>)}
        </div>
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
      <div className="code-footer">
        <span>SQL Server · T-SQL</span>
        <span>{lineas} {lineas === 1 ? 'línea' : 'líneas'} · {valor.length.toLocaleString()} caracteres</span>
      </div>
    </div>
  );
}
