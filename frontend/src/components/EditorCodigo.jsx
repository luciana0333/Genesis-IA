import { Fragment, useEffect, useRef, useState } from 'react';
import { tokenizarSql } from '../utils/resaltadoSql';

/**
 * Fragmentos coloreados agrupados por línea: [[{ tipo, valor }, ...], ...]. Cada línea del código se
 * dibuja en su propio renglón, y ahí mismo se pinta si está marcada o tiene el cursor: así el sombreado
 * siempre queda en la fila del texto, con cualquier zoom o escala de pantalla.
 */
function porLineas(fragmentos) {
  const lineas = [[]];
  for (const fragmento of fragmentos) {
    fragmento.valor.split('\n').forEach((parte, indice) => {
      if (indice > 0) lineas.push([]);
      if (parte) lineas[lineas.length - 1].push({ tipo: fragmento.tipo, valor: parte });
    });
  }
  return lineas;
}

function contarLineas(texto) {
  let lineas = 1;
  for (let i = 0; i < texto.length; i += 1) {
    if (texto.charCodeAt(i) === 10) lineas += 1;
  }
  return lineas;
}

/**
 * Área de texto para SQL con numeración de líneas, colores de sintaxis,
 * resaltado de la línea donde está el cursor y contador. Detrás del textarea
 * (con el texto transparente) se dibuja el mismo código coloreado; ambos usan
 * la misma letra y medidas para quedar alineados. Las líneas no se ajustan
 * (wrap="off") para que la numeración siempre coincida.
 *
 * `marcadas`: líneas de una observación, pintadas en rojo. `enfocar` ({ linea, clave }):
 * cada clave nueva desplaza el código hasta esa línea y deja el cursor ahí.
 */
export function EditorCodigo({
  id, valor, onCambiar, filas = 12, placeholder, etiquetaAccesible, marcadas = [], enfocar = null,
}) {
  const numeracionRef = useRef(null);
  const resaltadoRef = useRef(null);
  const textareaRef = useRef(null);
  const [lineaActiva, setLineaActiva] = useState(null);
  const lineas = contarLineas(valor);
  const renglones = porLineas(tokenizarSql(valor));

  const sincronizarDesplazamiento = (evento) => {
    const { scrollTop, scrollLeft } = evento.target;
    if (numeracionRef.current) numeracionRef.current.scrollTop = scrollTop;
    if (resaltadoRef.current) {
      resaltadoRef.current.scrollTop = scrollTop;
      resaltadoRef.current.scrollLeft = scrollLeft;
    }
  };

  // «Ver en el código»: lleva el código hasta la línea (a un tercio de la altura) y pone el cursor al inicio.
  useEffect(() => {
    const area = textareaRef.current;
    if (!enfocar || !area) return;
    const alto = parseFloat(getComputedStyle(area).lineHeight) || 20;
    area.scrollTop = Math.max(0, (enfocar.linea - 1) * alto - area.clientHeight / 3);
    let inicio = 0;
    for (let n = 1; n < enfocar.linea; n += 1) {
      const salto = area.value.indexOf('\n', inicio);
      if (salto < 0) break;
      inicio = salto + 1;
    }
    area.focus({ preventScroll: true });
    area.setSelectionRange(inicio, inicio);
    sincronizarDesplazamiento({ target: area });
    setLineaActiva(enfocar.linea);
    // El editor crece con el código: además se desplaza la página hasta la línea marcada.
    // (tras pintar las marcas nuevas)
    setTimeout(() => {
      resaltadoRef.current?.querySelector(`[data-linea="${enfocar.linea}"]`)
        ?.scrollIntoView?.({ behavior: 'smooth', block: 'center' });
    }, 0);
    // Solo cuando llega un pedido nuevo (clave nueva), no en cada render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enfocar?.clave]);

  // Línea donde está el cursor (1, 2, ...), para resaltarla.
  const actualizarLineaActiva = (evento) => {
    const { value, selectionStart } = evento.target;
    setLineaActiva(contarLineas(value.slice(0, selectionStart)));
  };

  return (
    <div className="code-editor">
      <div className="code-surface">
        <div className="code-gutter" ref={numeracionRef} aria-hidden="true">
          {Array.from({ length: lineas }, (_, indice) => (
            <span
              key={indice}
              className={marcadas.includes(indice + 1) ? 'marcada' : indice + 1 === lineaActiva ? 'activa' : undefined}
            >
              {indice + 1}
            </span>
          ))}
        </div>
        <div className="code-input">
          <pre className="code-highlight" ref={resaltadoRef} aria-hidden="true">
            <span className="code-renglones">
              {renglones.map((partes, indice) => {
                const numero = indice + 1;
                const clase = marcadas.includes(numero) ? ' marcada' : numero === lineaActiva ? ' activa' : '';
                return (
                  <span key={indice} className={`code-renglon${clase}`} data-linea={numero}>
                    {partes.map((parte, posicion) => (
                      parte.tipo === 'texto'
                        ? <Fragment key={posicion}>{parte.valor}</Fragment>
                        : <span key={posicion} className={`tok-${parte.tipo}`}>{parte.valor}</span>
                    ))}
                  </span>
                );
              })}
            </span>
          </pre>
          <textarea
            ref={textareaRef}
            id={id}
            rows={filas}
            wrap="off"
            spellCheck={false}
            autoComplete="off"
            autoCapitalize="off"
            placeholder={placeholder}
            aria-label={etiquetaAccesible}
            value={valor}
            onChange={(evento) => {
              onCambiar(evento.target.value);
              actualizarLineaActiva(evento);
            }}
            onSelect={actualizarLineaActiva}
            onBlur={() => setLineaActiva(null)}
            onScroll={sincronizarDesplazamiento}
          />
        </div>
      </div>
      <div className="code-footer">
        <span>SQL Server · T-SQL</span>
        <span>
          {lineaActiva && <span className="code-posicion">Línea {lineaActiva} · </span>}
          {lineas} {lineas === 1 ? 'línea' : 'líneas'} · {valor.length.toLocaleString()} caracteres
        </span>
      </div>
    </div>
  );
}
