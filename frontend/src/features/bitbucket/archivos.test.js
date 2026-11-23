import { armarRevision, moduloDe, pesoGravedad, situacion } from './archivos';

const tabla = { id: 't', ruta: 'Tablas/OCR.Documento.sql', estado: 'agregado', tipo: 'tabla', objeto: 'OCR.Documento', contenido: 'CREATE TABLE OCR.Documento (nDocumentoId INT)', pareja: null, dudoso: false };
const indices = { id: 'i', ruta: 'Indices/OCR.Documento_IX.sql', estado: 'agregado', tipo: 'indices', objeto: 'OCR.Documento', contenido: 'CREATE INDEX IXN_Documento ON OCR.Documento (nDocumentoId)', pareja: 't', dudoso: false };
const diccionario = { id: 'd', ruta: 'Diccionarios/OCR.Documento_DD.sql', estado: 'agregado', tipo: 'diccionario_tabla', objeto: 'OCR.Documento', contenido: "EXEC sys.sp_addextendedproperty 'MS_Description'", pareja: 't', dudoso: false };
const dudoso = { id: 'p', ruta: 'Procedimientos/OCR.PA_Documento_Sel_Resumen.sql', estado: 'agregado', tipo: 'procedimiento', objeto: 'OCR.PA_Documento_Sel_Resumen', contenido: 'CREATE PROCEDURE OCR.PA_Documento_Sel_Resumen AS SELECT 1', pareja: null, dudoso: true };

describe('situacion y módulo de cada archivo', () => {
  it('un archivo dudoso no se revisa hasta que la usuaria elige (Genesis no adivina)', () => {
    expect(situacion(dudoso, undefined)).toBe('confirmar');
    expect(moduloDe(dudoso, undefined)).toBeNull();
    expect(situacion(dudoso, 'reporte')).toBe('revisar');
    expect(moduloDe(dudoso, 'reporte')).toBe('reporte');
  });

  it('sin duda se usa el módulo sugerido, y se puede cambiar o no revisar', () => {
    expect(moduloDe(tabla, undefined)).toBe('tabla');
    expect(moduloDe({ ...dudoso, dudoso: false }, 'reporte')).toBe('reporte');
    expect(situacion(tabla, 'ninguno')).toBe('omitido');
    expect(moduloDe(tabla, 'ninguno')).toBeNull();
  });

  it('esquemas, datos, eliminados e índices con su tabla no tienen tarjeta propia', () => {
    expect(situacion({ ...tabla, tipo: 'esquema' })).toBe('sinReglas');
    expect(situacion({ ...tabla, tipo: 'datos' })).toBe('sinReglas');
    expect(situacion({ ...tabla, tipo: 'desconocido' })).toBe('sinReglas');
    expect(situacion({ ...tabla, estado: 'eliminado' })).toBe('eliminado');
    expect(situacion(indices)).toBe('adjunto');
  });
});

describe('armarRevision: lo mismo que si se pegara en el módulo', () => {
  it('la tabla lleva sus índices en la cajita de índices', () => {
    const revision = armarRevision(tabla, 'tabla', [tabla, indices]);
    expect(revision.tipoRevision).toBe('tabla_estructura');
    expect(revision.campos.sqlObject).toBe(tabla.contenido);
    expect(revision.campos.indicesScript).toBe(indices.contenido);
    expect(revision.campos.objetoNombre).toBe('OCR.Documento');
  });

  it('el diccionario se revisa con el objeto que documenta', () => {
    const revision = armarRevision(diccionario, 'diccionario_tabla', [tabla, diccionario]);
    expect(revision).toMatchObject({ tipoRevision: 'tabla', campos: { sqlObject: tabla.contenido, dictScript: diccionario.contenido } });
  });

  it('si el objeto del diccionario no viene en el cambio, lo dice en vez de revisar a medias', () => {
    expect(armarRevision(diccionario, 'diccionario_tabla', [diccionario]).error).toMatch(/no viene en el cambio/);
    expect(armarRevision(diccionario, 'diccionario_tabla', [{ ...tabla, estado: 'eliminado' }, diccionario]).error).toMatch(/no viene/);
  });

  it('procedimientos y reportes van con su código', () => {
    expect(armarRevision(dudoso, 'procedimiento', [dudoso])).toMatchObject({ tipoRevision: 'procedimiento_normal', campos: { sqlObject: dudoso.contenido } });
    expect(armarRevision(dudoso, 'reporte', [dudoso]).tipoRevision).toBe('reporte');
  });
});

describe('pesoGravedad', () => {
  it('una crítica pesa más que muchas altas, y así hacia abajo', () => {
    const una = { critico: 1, alto: 0, medio: 0, bajo: 0 };
    const muchas = { critico: 0, alto: 50, medio: 99, bajo: 99 };
    expect(pesoGravedad(una)).toBeGreaterThan(pesoGravedad(muchas));
    expect(pesoGravedad(undefined)).toBe(0);
  });
});
