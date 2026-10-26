import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { tokenizarSql } from '../utils/resaltadoSql';

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
  const lineaActivaRef = useRef(null);
  const marcasRef = useRef(null);
  const textareaRef = useRef(null);
  const [lineaActiva, setLineaActiva] = useState(null);
  // Posición real de cada línea marcada (y de la del cursor), tomada de su número en la numeración:
  // el número siempre queda alineado con el texto, aunque el navegador tenga zoom (con zoom el alto de
  // línea tiene decimales y un cálculo «línea × alto» se corre unos píxeles por línea).
  const [ubicaciones, setUbicaciones] = useState({});
  const lineas = contarLineas(valor);
  const fragmentos = tokenizarSql(valor);

  const sincronizarDesplazamiento = (evento) => {
    const { scrollTop, scrollLeft } = evento.target;
    if (numeracionRef.current) numeracionRef.current.scrollTop = scrollTop;
    if (resaltadoRef.current) {
      resaltadoRef.current.scrollTop = scrollTop;
      resaltadoRef.current.scrollLeft = scrollLeft;
    }
    if (lineaActivaRef.current) lineaActivaRef.current.style.transform = `translateY(${-scrollTop}px)`;
    if (marcasRef.current) marcasRef.current.style.transform = `translateY(${-scrollTop}px)`;
  };

  useLayoutEffect(() => {
    const medir = () => {
      const numeracion = numeracionRef.current;
      const entrada = marcasRef.current?.parentElement ?? lineaActivaRef.current?.parentElement;
      if (!numeracion || !entrada) return;
      const base = entrada.getBoundingClientRect().top - numeracion.scrollTop;
      const nuevas = {};
      for (const linea of [...marcadas, lineaActiva].filter(Boolean)) {
        const numero = numeracion.children[linea - 1];
        if (numero) {
          const caja = numero.getBoundingClientRect();
          nuevas[linea] = { top: caja.top - base, height: caja.height };
        }
      }
      // Solo si cambió: `marcadas` puede llegar como un arreglo nuevo en cada render.
      setUbicaciones((actuales) => (JSON.stringify(actuales) === JSON.stringify(nuevas) ? actuales : nuevas));
    };
    medir();
    window.addEventListener('resize', medir);  // también al cambiar el zoom del navegador
    return () => window.removeEventListener('resize', medir);
  }, [marcadas, lineaActiva, valor]);

  // Posición de una línea: la medida o, mientras tanto, la calculada.
  const ubicacion = (linea) => ubicaciones[linea] ?? { top: `calc(var(--code-padding) + var(--code-linea) * ${linea - 1})` };

  // Las marcas nuevas se alinean con el desplazamiento actual del código.
  useEffect(() => {
    if (marcasRef.current && textareaRef.current) {
      marcasRef.current.style.transform = `translateY(${-textareaRef.current.scrollTop}px)`;
    }
  }, [marcadas]);

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
      marcasRef.current?.querySelector(`[data-linea="${enfocar.linea}"]`)
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
          {lineaActiva && (
            <div
              className="code-linea-activa"
              ref={lineaActivaRef}
              style={ubicacion(lineaActiva)}
              aria-hidden="true"
            />
          )}
          {marcadas.length > 0 && (
            <div className="code-marcas" ref={marcasRef} aria-hidden="true">
              {marcadas.map((linea) => (
                <div
                  key={linea}
                  data-linea={linea}
                  className="code-linea-marcada"
                  style={ubicacion(linea)}
                />
              ))}
            </div>
          )}
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
