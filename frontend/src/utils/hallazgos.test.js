import { contarPorSeveridad, formatearKb, normalizarSeveridad, ordenarHallazgos } from './hallazgos';

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

describe('ordenarHallazgos', () => {
  it('ordena por severidad y luego por línea sin mutar la entrada', () => {
    const entrada = [
      { severidad: 'bajo', linea: 1 },
      { severidad: 'alto', linea: 8 },
      { severidad: 'critico', linea: 5 },
      { severidad: 'alto', linea: 3 },
    ];
    const ordenados = ordenarHallazgos(entrada);
    expect(ordenados.map((h) => `${h.severidad}:${h.linea}`)).toEqual(['critico:5', 'alto:3', 'alto:8', 'bajo:1']);
    expect(entrada[0].severidad).toBe('bajo');
  });
});
