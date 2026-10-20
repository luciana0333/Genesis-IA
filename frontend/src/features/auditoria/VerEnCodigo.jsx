import { IconoMira } from '../../components/Iconos';

/** «Ver en el código»: lleva al editor, a la línea de la observación, y la marca en rojo. */
export function VerEnCodigo({ onVer }) {
  return (
    <button type="button" className="ver-en-codigo" onClick={onVer}>
      <IconoMira />
      Ver en el código
    </button>
  );
}
