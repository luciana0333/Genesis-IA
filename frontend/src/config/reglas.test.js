import { tituloHallazgo } from './reglas';

const LEFT_LIKE = (mensaje) => ({ regla: 'LEFT_REEMPLAZABLE_POR_LIKE', mensaje });

describe('tituloHallazgo · LEFT o SUBSTRING por LIKE (usuaria, 8 nov.)', () => {
  it('dice la función que se usó', () => {
    expect(tituloHallazgo(LEFT_LIKE("Se identificó el uso de LEFT(cCtaCod, 3) = '109' en una condición. Se recomienda evaluar el reemplazo de LEFT() por LIKE.")))
      .toBe('LEFT que puede reemplazarse por LIKE');
    expect(tituloHallazgo(LEFT_LIKE("Se identificó el uso de SUBSTRING(RH.cRHCod, 1, 1) IN ('E', 'A') en una condición. Se recomienda evaluar el reemplazo de SUBSTRING() por LIKE.")))
      .toBe('SUBSTRING que puede reemplazarse por LIKE');
  });

  it('con las dos en el mismo procedimiento, las une con «o»', () => {
    const agrupado = "Se encontraron 2 observaciones de este tipo, en las líneas 3, 7: se identificó el uso de LEFT(a, 3) = '109' en una condición; se identificó el uso de SUBSTRING(b, 1, 2) = '10' en una condición. Se recomienda evaluar el reemplazo de LEFT() por LIKE.";
    expect(tituloHallazgo(LEFT_LIKE(agrupado))).toBe('LEFT o SUBSTRING que puede reemplazarse por LIKE');
  });

  it('un LEFT JOIN no es la función LEFT; las demás reglas usan su nombre', () => {
    expect(tituloHallazgo(LEFT_LIKE('Se identificó SUBSTRING(c, 1, 2) = 10 en un LEFT JOIN.')))
      .toBe('SUBSTRING que puede reemplazarse por LIKE');
    expect(tituloHallazgo({ regla: 'CREATE_OR_ALTER', mensaje: 'LEFT(' })).toBe('Uso de CREATE OR ALTER');
  });
});
