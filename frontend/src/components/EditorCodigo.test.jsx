import { render } from '@testing-library/react';
import { EditorCodigo } from './EditorCodigo';

const CODIGO = ['UPDATE a', '\tSet a.nNumAnalistas = T.nNumAnalistas', '\t--Select *', '', '\tFrom #MOSTRARDETALLE a'].join('\n');

function dibujar(props = {}) {
  const { container } = render(
    <EditorCodigo id="sql" valor={CODIGO} onCambiar={() => {}} etiquetaAccesible="SQL" {...props} />,
  );
  return container;
}

describe('EditorCodigo', () => {
  it('dibuja un renglón por línea, con el mismo texto que el código', () => {
    const renglones = [...dibujar().querySelectorAll('.code-renglon')];
    expect(renglones.map((renglon) => renglon.textContent)).toEqual(CODIGO.split('\n'));
    expect(renglones.map((renglon) => renglon.dataset.linea)).toEqual(['1', '2', '3', '4', '5']);
  });

  it('el sombreado de la línea marcada va en el renglón de su propio texto', () => {
    const contenedor = dibujar({ marcadas: [3] });
    const marcados = [...contenedor.querySelectorAll('.code-renglon.marcada')];
    expect(marcados.map((renglon) => renglon.textContent)).toEqual(['\t--Select *']);
    expect(contenedor.querySelector('.code-gutter span.marcada').textContent).toBe('3');
  });
});
