import { describe, expect, it } from 'vitest';
import { grupoDelRecorrido } from './recorrido';

const GRUPOS = [
  { nombre: 'TempDNCalculado', lineas: [345, 379, 413, 446] },
  { nombre: 'OpeCtaPreparada', lineas: [350, 384, 418, 451] },
];

describe('grupoDelRecorrido', () => {
  it('recorre todas las veces de la primera tabla y luego las de la segunda', () => {
    expect(grupoDelRecorrido(GRUPOS, 0)).toEqual(
      { numero: 1, total: 2, nombre: 'TempDNCalculado', vez: 1, veces: 4, vineta: 0 },
    );
    expect(grupoDelRecorrido(GRUPOS, 3)).toMatchObject({ numero: 1, vez: 4 });
    expect(grupoDelRecorrido(GRUPOS, 4)).toEqual(
      { numero: 2, total: 2, nombre: 'OpeCtaPreparada', vez: 1, veces: 4, vineta: 1 },
    );
  });

  it('sin grupos no hay tabla que mostrar', () => {
    expect(grupoDelRecorrido(undefined, 0)).toBeNull();
    expect(grupoDelRecorrido([], 0)).toBeNull();
  });
});
