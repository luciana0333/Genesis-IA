import { IconoMira } from '../../components/Iconos';
import { tokenizarSql } from '../../utils/resaltadoSql';

const CONTEXTO = 1; // líneas antes y después de cada línea marcada
const MAXIMO_BLOQUES = 3;

/** Tramos [desde, hasta] alrededor de cada línea marcada; los que se tocan se unen. */
function tramos(lineas, total) {
  const ordenadas = [...new Set(lineas)].filter((n) => n >= 1 && n <= total).sort((a, b) => a - b);
  const resultado = [];
  for (const linea of ordenadas) {
    const desde = Math.max(1, linea - CONTEXTO);
    const hasta = Math.min(total, linea + CONTEXTO);
    const ultimo = resultado[resultado.length - 1];
    if (ultimo && desde <= ultimo[1] + 1) ultimo[1] = Math.max(ultimo[1], hasta);
    else resultado.push([desde, hasta]);
  }
  return resultado;
}

function LineaCodigo({ numero, texto, marcada }) {
  return (
    <div className={marcada ? 'fragmento-linea marcada' : 'fragmento-linea'}>
      <span className="fragmento-numero">{numero}</span>
      <span className="fragmento-texto">
        {tokenizarSql(texto).map((fragmento, indice) => (
          fragmento.tipo === 'texto'
            ? fragmento.valor
            : <span key={indice} className={`tok-${fragmento.tipo}`}>{fragmento.valor}</span>
        ))}
        {texto ? '' : ' '}
      </span>
    </div>
  );
}

/**
 * El código de una observación dentro de su ficha: su línea (en rojo) con la anterior y la
 * siguiente, y «Ver en el código», que lleva al editor y la marca allí.
 */
export function FragmentoCodigo({ texto, lineas, cajita, onVer }) {
  const todas = texto.split('\n');
  const bloques = tramos(lineas, todas.length);
  if (!bloques.length) return null;
  const visibles = bloques.slice(0, MAXIMO_BLOQUES);
  const ocultos = bloques.length - visibles.length;

  return (
    <div className="fragmento">
      <p className="fragmento-cajita">{cajita}</p>
      <div className="fragmento-codigo">
        {visibles.map(([desde, hasta], indice) => (
          <div key={desde} className="fragmento-bloque">
            {indice > 0 && <div className="fragmento-salto" aria-hidden="true">⋯</div>}
            {todas.slice(desde - 1, hasta).map((linea, posicion) => {
              const numero = desde + posicion;
              return <LineaCodigo key={numero} numero={numero} texto={linea} marcada={lineas.includes(numero)} />;
            })}
          </div>
        ))}
        {ocultos > 0 && (
          <p className="fragmento-mas">y {ocultos} {ocultos === 1 ? 'lugar más' : 'lugares más'} en el código</p>
        )}
      </div>
      <button type="button" className="fragmento-ver" onClick={onVer}>
        <IconoMira />
        Ver en el código
      </button>
    </div>
  );
}
