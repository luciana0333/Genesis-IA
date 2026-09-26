import { useState } from 'react';
import { IconoArchivo, IconoCerrar, IconoSubir } from '../../components/Iconos';

function formatearTamano(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/**
 * Selector de archivo con arrastrar y soltar. El <input type="file"> real
 * queda oculto visualmente pero accesible (teclado y lectores de pantalla).
 */
export function ZonaArchivo({ id, inputRef, archivo, accept, onSeleccionar, onQuitar }) {
  const [arrastrando, setArrastrando] = useState(false);

  const alSoltar = (evento) => {
    evento.preventDefault();
    setArrastrando(false);
    const soltado = evento.dataTransfer.files?.[0];
    if (soltado) onSeleccionar(soltado);
  };

  return (
    <div className="dropzone-wrap">
      <input
        ref={inputRef}
        id={id}
        className="sr-only"
        type="file"
        accept={accept}
        onChange={(evento) => onSeleccionar(evento.target.files?.[0])}
      />
      <label
        htmlFor={id}
        className={`dropzone${arrastrando ? ' dragging' : ''}`}
        onDragOver={(evento) => {
          evento.preventDefault();
          setArrastrando(true);
        }}
        onDragLeave={() => setArrastrando(false)}
        onDrop={alSoltar}
      >
        <span className="dropzone-icon"><IconoSubir /></span>
        <span className="dropzone-title">
          Arrastra tu archivo aquí o <span className="dropzone-link">selecciónalo</span>
        </span>
        <span className="dropzone-hint">Plan real en formato .sqlplan · máximo 25 MB</span>
      </label>

      {archivo ? (
        <div className="file-chip">
          <span className="file-chip-icon"><IconoArchivo /></span>
          <span className="file-chip-info">
            <span className="file-chip-name">{archivo.name}</span>
            <span className="file-chip-size">{formatearTamano(archivo.size)}</span>
          </span>
          <button type="button" className="file-chip-remove" onClick={onQuitar} aria-label="Quitar archivo">
            <IconoCerrar />
          </button>
        </div>
      ) : (
        <p className="file-empty">Ningún archivo seleccionado</p>
      )}
    </div>
  );
}
