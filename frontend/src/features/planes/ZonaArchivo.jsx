import { useState } from 'react';
import { IconoArchivo, IconoCerrar, IconoComprimido, IconoSubir } from '../../components/Iconos';

const MAXIMO_VISIBLES = 6;

function formatearTamano(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const esComprimido = (archivo) => /\.(zip|rar)$/i.test(archivo.name);

/** Lee todas las entradas de una carpeta (el navegador las entrega por tandas). */
function leerCarpeta(lector) {
  return new Promise((resolver) => {
    const entradas = [];
    const leerTanda = () => lector.readEntries((tanda) => {
      if (!tanda.length) {
        resolver(entradas);
        return;
      }
      entradas.push(...tanda);
      leerTanda();
    }, () => resolver(entradas));
    leerTanda();
  });
}

/** Archivos de una entrada soltada: si es carpeta, todos los de adentro (con su ruta). */
async function archivosDeEntrada(entrada, ruta = '') {
  if (entrada.isFile) {
    const archivo = await new Promise((resolver) => entrada.file(resolver, () => resolver(null)));
    if (archivo && ruta) archivo.rutaRelativa = `${ruta}${archivo.name}`;
    return archivo ? [archivo] : [];
  }
  if (!entrada.isDirectory) return [];
  const hijos = await leerCarpeta(entrada.createReader());
  const listas = await Promise.all(hijos.map((hijo) => archivosDeEntrada(hijo, `${ruta}${entrada.name}/`)));
  return listas.flat();
}

async function archivosSoltados(dataTransfer) {
  const entradas = Array.from(dataTransfer.items ?? [])
    .map((item) => item.webkitGetAsEntry?.())
    .filter(Boolean);
  if (!entradas.length) return Array.from(dataTransfer.files ?? []);
  const listas = await Promise.all(entradas.map((entrada) => archivosDeEntrada(entrada)));
  return listas.flat();
}

/**
 * Selector de archivos con arrastrar y soltar (archivos sueltos, comprimidos o
 * carpetas completas). El <input type="file"> real queda oculto visualmente pero
 * accesible (teclado y lectores de pantalla).
 */
export function ZonaArchivo({ id, inputRef, archivos = [], accept, multiple = false, pista, onSeleccionar, onQuitar }) {
  const [arrastrando, setArrastrando] = useState(false);
  const [verTodos, setVerTodos] = useState(false);

  const alSoltar = async (evento) => {
    evento.preventDefault();
    setArrastrando(false);
    const soltados = await archivosSoltados(evento.dataTransfer);
    if (soltados.length) onSeleccionar(multiple ? soltados : soltados.slice(0, 1));
  };

  const visibles = verTodos ? archivos : archivos.slice(0, MAXIMO_VISIBLES);
  const ocultos = archivos.length - visibles.length;
  const totalBytes = archivos.reduce((suma, archivo) => suma + archivo.size, 0);

  return (
    <div className="dropzone-wrap">
      <input
        ref={inputRef}
        id={id}
        className="sr-only"
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(evento) => onSeleccionar(Array.from(evento.target.files ?? []))}
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
          Arrastra {multiple ? 'tus archivos o una carpeta' : 'tu archivo'} aquí o{' '}
          <span className="dropzone-link">selecciónalo{multiple ? 's' : ''}</span>
        </span>
        <span className="dropzone-hint">{pista}</span>
      </label>

      {archivos.length > 1 && (
        <p className="file-resumen">
          {archivos.length} archivos · {formatearTamano(totalBytes)}
        </p>
      )}
      {archivos.length ? (
        <ul className="file-lista">
          {visibles.map((archivo, indice) => (
            <li key={`${archivo.rutaRelativa || archivo.name}-${indice}`} className="file-chip">
              <span className="file-chip-icon">{esComprimido(archivo) ? <IconoComprimido /> : <IconoArchivo />}</span>
              <span className="file-chip-info">
                <span className="file-chip-name" title={archivo.rutaRelativa || archivo.name}>{archivo.name}</span>
                <span className="file-chip-size">{formatearTamano(archivo.size)}</span>
              </span>
              <button
                type="button"
                className="file-chip-remove"
                onClick={() => onQuitar(indice)}
                aria-label={`Quitar ${archivo.name}`}
              >
                <IconoCerrar />
              </button>
            </li>
          ))}
          {ocultos > 0 && (
            <li>
              <button type="button" className="file-ver-todos" onClick={() => setVerTodos(true)}>
                Ver los {ocultos} restantes
              </button>
            </li>
          )}
        </ul>
      ) : (
        <p className="file-empty">Ningún archivo seleccionado</p>
      )}
    </div>
  );
}
