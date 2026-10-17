import { useId, useState } from 'react';
import { EditorCodigo } from '../../components/EditorCodigo';
import { IconoCerrar, IconoCopiado, IconoCopiar, IconoGenerar } from '../../components/Iconos';
import { TarjetaEditor } from '../../components/TarjetaEditor';

function enumerar(elementos) {
  return elementos.length === 1 ? elementos[0] : `${elementos.slice(0, -1).join(', ')} y ${elementos.at(-1)}`;
}

/**
 * «Generar diccionario faltante»: al pie de la observación abre un cuadro igual
 * a los del formulario con el script sp_addextendedproperty de lo que falta
 * documentar. Se puede completar ahí mismo y copiar ya listo.
 */
export function GeneradorDiccionario({ faltante }) {
  const id = useId();
  const [abierto, setAbierto] = useState(false);
  const [script, setScript] = useState(faltante.script);
  const [copiado, setCopiado] = useState(false);
  // Vacía (N'') = por completar; con «-- Sugerida» = deducida del nombre, para revisar.
  const porCompletar = /@value\s*=\s*N''/i.test(script);
  const sugerido = /--\s*Sugerida/i.test(script);
  let estado = 'Completo';
  if (porCompletar) estado = 'Por completar';
  else if (sugerido) estado = 'Sugerido · revisar';

  const alCopiar = async () => {
    try {
      await navigator.clipboard.writeText(script);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1600);
    } catch {
      setCopiado(false);
    }
  };

  if (!abierto) {
    return (
      <button type="button" className="generador-abrir" onClick={() => setAbierto(true)}>
        <IconoGenerar />
        Generar diccionario faltante
      </button>
    );
  }

  return (
    <section className="generador" aria-label="Diccionario faltante">
      <TarjetaEditor
        className="field-card-full"
        numero={3}
        etiqueta="Diccionario faltante"
        htmlFor={id}
        estado={estado}
        requerido={estado !== 'Completo'}
        ayuda={`Generado para ${enumerar(faltante.elementos)}. Las descripciones se sugieren a partir de los nombres: revisarlas y mejorarlas aquí mismo antes de copiar el script.`}
        acciones={
          <>
            <button type="button" className="generador-boton" onClick={alCopiar}>
              {copiado ? <IconoCopiado /> : <IconoCopiar />}
              {copiado ? 'Copiado' : 'Copiar script'}
            </button>
            <button type="button" className="link-btn" onClick={() => setAbierto(false)} title="Ocultar el script">
              <IconoCerrar />
              Ocultar
            </button>
          </>
        }
      >
        <EditorCodigo
          id={id}
          valor={script}
          onCambiar={setScript}
          filas={Math.min(script.split('\n').length, 16)}
        />
      </TarjetaEditor>
    </section>
  );
}
