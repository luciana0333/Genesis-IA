import { useLayoutEffect, useRef } from 'react';

/**
 * Nombre del objeto: se ve completo aunque sea largo (CONTABILIDAD.PA_AsientoDNHistorico_Sel_LibroCaja…).
 * Es una sola línea de texto que, si no entra en el ancho, sigue en la línea de abajo y el campo crece.
 * Enter no agrega un salto: envía el formulario, igual que un campo de una línea.
 */
export function CampoNombre({ id, valor, onCambiar, title }) {
  const campoRef = useRef(null);

  // El alto se ajusta al texto (y al ancho disponible) cada vez que cambia.
  useLayoutEffect(() => {
    const campo = campoRef.current;
    if (!campo) return undefined;
    const ajustar = () => {
      campo.style.height = 'auto';
      // scrollHeight no incluye el borde; el alto (box-sizing: border-box) sí.
      const borde = campo.offsetHeight - campo.clientHeight;
      campo.style.height = `${campo.scrollHeight + borde}px`;
    };
    ajustar();
    const observador = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(ajustar);
    observador?.observe(campo);
    return () => observador?.disconnect();
  }, [valor]);

  return (
    <textarea
      ref={campoRef}
      id={id}
      className="campo-icono campo-icono-nombre campo-nombre"
      rows={1}
      autoComplete="off"
      spellCheck={false}
      value={valor}
      title={title}
      onChange={(evento) => onCambiar(evento.target.value.replace(/[\r\n]+/g, ' '))}
      onKeyDown={(evento) => {
        if (evento.key === 'Enter' && !evento.ctrlKey && !evento.metaKey) {
          evento.preventDefault();
          evento.currentTarget.form?.requestSubmit();
        }
      }}
    />
  );
}
