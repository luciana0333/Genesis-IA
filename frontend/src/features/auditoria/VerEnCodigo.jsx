import { IconoAnterior, IconoCerrar, IconoMira, IconoSiguiente } from '../../components/Iconos';

/** «Ver en el código»: lleva al editor, a la línea de la observación, y la marca en rojo. */
export function VerEnCodigo({ onVer }) {
  return (
    <button type="button" className="ver-en-codigo" onClick={onVer}>
      <IconoMira />
      Ver en el código
    </button>
  );
}

/**
 * Barra flotante para recorrer una a una las líneas de una observación en el editor
 * («Línea 135 · 4 de 20 ‹ ›»). Queda fija abajo mientras la página está en el código.
 */
export function BarraRecorrido({ titulo, linea, posicion, total, grupo, onAnterior, onSiguiente, onCerrar }) {
  return (
    <div className="barra-recorrido" role="toolbar" aria-label={`Recorrer las líneas de ${titulo}`}>
      {grupo ? (
        // Observación con varias tablas o columnas: «Tabla 2 de 4: OpeCtaPreparada · Vez 1 de 4».
        <span className="barra-recorrido-titulo barra-recorrido-grupo">
          <span className="barra-recorrido-tabla">{grupo.tipo} {grupo.numero} de {grupo.total}:</span> {grupo.nombre}
          <span className="barra-recorrido-vez">Vez {grupo.vez} de {grupo.veces}</span>
        </span>
      ) : (
        <span className="barra-recorrido-titulo">{titulo}</span>
      )}
      <span className="barra-recorrido-linea">Línea {linea}</span>
      <span className="barra-recorrido-posicion" aria-live="polite">{posicion} de {total}</span>
      <button type="button" onClick={onAnterior} aria-label="Línea anterior"><IconoAnterior /></button>
      <button type="button" className="barra-recorrido-siguiente" onClick={onSiguiente} aria-label="Línea siguiente"><IconoSiguiente /></button>
      <button type="button" className="barra-recorrido-cerrar" onClick={onCerrar} aria-label="Cerrar recorrido">
        <IconoCerrar />
      </button>
    </div>
  );
}
