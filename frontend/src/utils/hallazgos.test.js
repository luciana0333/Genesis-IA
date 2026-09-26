import { contarPorSeveridad, formatearKb, normalizarSeveridad } from './hallazgos';

describe('contarPorSeveridad', () => {
  it('cuenta cada severidad e ignora valores desconocidos', () => {
    const conteo = contarPorSeveridad([
      { severidad: 'alto' },
      { severidad: 'ALTO' },
      { severidad: 'bajo' },
      { severidad: 'inexistente' },
    ]);
    expect(conteo).toEqual({ critico: 0, alto: 2, medio: 0, bajo: 1 });
  });

  it('devuelve ceros sin hallazgos', () => {
    expect(contarPorSeveridad()).toEqual({ critico: 0, alto: 0, medio: 0, bajo: 0 });
  });
});

describe('normalizarSeveridad', () => {
  it('tolera valores nulos', () => {
    expect(normalizarSeveridad(undefined)).toBe('');
  });
});

describe('formatearKb', () => {
  it('muestra guiones cuando no hay valor', () => {
    expect(formatearKb(null)).toBe('--');
    expect(formatearKb(0)).toBe('--');
  });

  it('redondea y agrega la unidad', () => {
    expect(formatearKb(1023.6)).toMatch(/^1[,.]?024 KB$/);
  });
});
