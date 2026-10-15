import { useEffect, useId, useRef } from 'react';
import { Boton } from '../../components/Boton';
import { IconoAgregar, IconoArchivo, IconoCerrar } from '../../components/Iconos';

/**
 * Ventana que aparece al ejecutar una revisión de diccionario sin pegar el
 * diccionario. Permite volver a añadirlo o revisar igual (p. ej. un ALTER que
 * solo elimina una restricción y no necesita documentación).
 */
export function AvisoFaltaDiccionario({ objeto, nombre, onAnadir, onRevisarSinDiccionario, onCerrar }) {
  const ids = useId();
  const principalRef = useRef(null);

  useEffect(() => {
    principalRef.current?.focus();
    const alPresionar = (evento) => {
      if (evento.key === 'Escape') onCerrar();
    };
    document.addEventListener('keydown', alPresionar);
    return () => document.removeEventListener('keydown', alPresionar);
  }, [onCerrar]);

  const esTabla = objeto === 'tabla';
  const articulo = esTabla ? 'la tabla' : 'el procedimiento';

  return (
    <div className="aviso-capa" onMouseDown={(evento) => evento.target === evento.currentTarget && onCerrar()}>
      <div
        className="aviso-ventana"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={`${ids}-titulo`}
        aria-describedby={`${ids}-texto`}
      >
        <button type="button" className="aviso-cerrar" onClick={onCerrar} aria-label="Cerrar">
          <IconoCerrar />
        </button>

        <div className="aviso-cabecera">
          <span className="aviso-icono" aria-hidden="true"><IconoArchivo /></span>
          <div>
            <p className="aviso-etiqueta">Revisión incompleta</p>
            <h2 className="aviso-titulo" id={`${ids}-titulo`}>Falta el diccionario</h2>
          </div>
        </div>

        <p className="aviso-texto" id={`${ids}-texto`}>
          Se ha intentado revisar {articulo}{nombre ? <> <strong>{nombre}</strong></> : null}, pero no se incluyó su
          diccionario. Añadir el script de documentación en el cuadro 2 para continuar con la revisión.
        </p>

        <div className="aviso-objeto">
          <span className="aviso-objeto-tipo">{esTabla ? 'Tabla' : 'Procedimiento'}</span>
          <span className="aviso-objeto-estado">
            <i aria-hidden="true" />
            Diccionario no incluido
          </span>
        </div>

        <p className="aviso-nota">
          Si el cambio no requiere documentación (por ejemplo, solo elimina una restricción), puede revisarse sin
          diccionario.
        </p>

        <div className="aviso-acciones">
          <Boton variante="secundario" onClick={onRevisarSinDiccionario}>Revisar sin diccionario</Boton>
          <Boton icono={<IconoAgregar />} onClick={onAnadir} ref={principalRef}>Añadir diccionario</Boton>
        </div>
      </div>
    </div>
  );
}
