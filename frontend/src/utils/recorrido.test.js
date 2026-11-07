import { describe, expect, it } from 'vitest';
import { desglosarGrupo, separarMensaje } from './hallazgos';
import { etiquetaDeGrupos, grupoDelRecorrido } from './recorrido';

const GRUPOS = [
  { nombre: 'TempDNCalculado', lineas: [345, 379, 413, 446] },
  { nombre: 'OpeCtaPreparada', lineas: [350, 384, 418, 451] },
];

describe('grupoDelRecorrido', () => {
  it('recorre todas las veces de la primera tabla y luego las de la segunda', () => {
    expect(grupoDelRecorrido(GRUPOS, 0)).toEqual(
      { numero: 1, total: 2, nombre: 'TempDNCalculado', tipo: 'Tabla', vez: 1, veces: 4, vineta: 0 },
    );
    expect(grupoDelRecorrido(GRUPOS, 3)).toMatchObject({ numero: 1, vez: 4 });
    expect(grupoDelRecorrido(GRUPOS, 4)).toEqual(
      { numero: 2, total: 2, nombre: 'OpeCtaPreparada', tipo: 'Tabla', vez: 1, veces: 4, vineta: 1 },
    );
  });

  it('dice «Columna» cuando las viñetas son columnas', () => {
    const columnas = [{ nombre: 'cCodAge', lineas: [10, 40], tipo: 'Columna' }];
    expect(grupoDelRecorrido(columnas, 1)).toMatchObject({ tipo: 'Columna', nombre: 'cCodAge', vez: 2, veces: 2 });
  });

  it('sin grupos no hay tabla que mostrar', () => {
    expect(grupoDelRecorrido(undefined, 0)).toBeNull();
    expect(grupoDelRecorrido([], 0)).toBeNull();
  });
});

describe('etiquetaDeGrupos', () => {
  it('cuenta las viñetas, no las líneas', () => {
    expect(etiquetaDeGrupos(GRUPOS)).toBe('2 tablas');
    expect(etiquetaDeGrupos([
      { nombre: 'a', lineas: [1, 2, 3], tipo: 'Columna' },
      { nombre: 'b', lineas: [4], tipo: 'Columna' },
    ])).toBe('2 columnas');
    expect(etiquetaDeGrupos([GRUPOS[0]])).toBeNull();
    expect(etiquetaDeGrupos(undefined)).toBeNull();
  });
});

describe('«Misma columna con distinto tipo»', () => {
  it('muestra la introducción y una viñeta por columna', () => {
    const mensaje = 'Se identificaron las siguientes columnas con diferentes tipos de datos o longitudes entre las '
      + "tablas temporales: 'cCodAge': VARCHAR(3) en 8 tablas temporales y VARCHAR(5) en 8; "
      + "'cTipo': VARCHAR(10) en 8 tablas temporales y VARCHAR(1) en #DATAFINALF. Se recomienda validar los tipos "
      + 'de datos y longitudes definidos para cada columna, ya que las diferencias pueden generar conversiones '
      + 'implícitas. De confirmarse que cumplen el mismo propósito, se recomienda homologarlos.';
    const { problema, solucion } = separarMensaje(mensaje);
    expect(solucion).toMatch(/^Se recomienda validar .* se recomienda homologarlos\.$/);
    expect(desglosarGrupo(problema)).toEqual({
      lineas: null,
      intro: 'Se identificaron las siguientes columnas con diferentes tipos de datos o longitudes entre las tablas temporales:',
      ocurrencias: [
        "'cCodAge': VARCHAR(3) en 8 tablas temporales y VARCHAR(5) en 8",
        "'cTipo': VARCHAR(10) en 8 tablas temporales y VARCHAR(1) en #DATAFINALF",
      ],
    });
  });
});
