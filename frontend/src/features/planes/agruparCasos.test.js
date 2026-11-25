import { describe, expect, it } from 'vitest';
import { agruparCasos, claveConversion, etiquetaConsultas } from './agruparCasos';

const caso = (numero, id, resaltar) => ({ sentencia: { numero }, nodo: { id, resaltar } });

describe('agruparCasos (imagen del plan; usuaria, 25 nov.)', () => {
  it('la misma conversión en varias consultas va una sola vez, con sus consultas', () => {
    // Caso real PA_CuentasOrden_Ins_AsientoEstadisticoCapitalMensual: consultas 16 y 17.
    const grupos = agruparCasos([
      caso(12, '7', ['CONVERT_IMPLICIT(varchar(25),#MovimientoCabecera.[cMovNro] as [C].[cMovNro],0)']),
      caso(16, '3', ['CONVERT_IMPLICIT(money,#MovimientoDetalle.[nMovImporte] as [D].[nMovImporte],0)']),
      caso(17, '8', ['CONVERT_IMPLICIT(money,#MovimientoDetalle.[nMovImporte] as [D].[nMovImporte],0)']),
      caso(19, '1', ['CONVERT_IMPLICIT(char(1),[DBCMACICA].[dbo].[CtaContClase].[cCtaCaracter] as [TC].[cCtaCaracter],0)']),
    ]);
    expect(grupos.map((g) => g.consultas)).toEqual([[12], [16, 17], [19]]);
    expect(grupos[1].nodo.id).toBe('3');
  });

  it('el alias no cuenta: [D].[nMovImporte] y [M].[nMovImporte] son la misma conversión', () => {
    expect(claveConversion(['CONVERT_IMPLICIT(money,#T.[n] as [D].[n],0)']))
      .toBe(claveConversion(['CONVERT_IMPLICIT(money,#T.[n] as [M].[n],0)']));
    expect(claveConversion(['CONVERT_IMPLICIT(money,#T.[n],0)']))
      .not.toBe(claveConversion(['CONVERT_IMPLICIT(int,#T.[n],0)']));
  });

  it('sin conversión resaltada, cada operador queda como está', () => {
    expect(agruparCasos([caso(1, '2'), caso(2, '2')]).map((g) => g.consultas)).toEqual([[1], [2]]);
  });

  it('lectura completa: la misma tabla en varias consultas va una sola vez', () => {
    const scan = (numero, id) => ({ sentencia: { numero }, nodo: { id, fisica: 'Index Scan', objeto: '[dbo].[Producto]', indice: '[PK_Producto]' } });
    expect(agruparCasos([scan(38, '10'), scan(119, '12')], 'LECTURA_COMPLETA_TABLA').map((g) => g.consultas)).toEqual([[38, 119]]);
    // Otras reglas no se juntan por tabla.
    expect(agruparCasos([scan(38, '10'), scan(119, '12')], 'TABLE_SCAN_DETECTADO')).toHaveLength(2);
  });

  it('etiqueta de las consultas', () => {
    expect(etiquetaConsultas([12])).toBe('Consulta 12');
    expect(etiquetaConsultas([16, 17])).toBe('Consultas 16 y 17');
    expect(etiquetaConsultas([3, 8, 9])).toBe('Consultas 3, 8 y 9');
  });
});
