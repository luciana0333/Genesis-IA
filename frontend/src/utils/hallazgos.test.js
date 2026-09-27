import { contarPorSeveridad, formatearKb, normalizarSeveridad, ordenarHallazgos, desglosarGrupo, separarMensaje } from './hallazgos';

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

describe('desglosarGrupo', () => {
  it('separa cada ocurrencia de un hallazgo agrupado y sus líneas', () => {
    const mensaje =
      'Se encontraron 2 observaciones de este tipo, en las líneas 4, 5: la columna cEstado de la temporal #TMP no tiene COLLATE; '
      + 'la columna cDescripcion de la temporal #TMP no tiene COLLATE. Añadir COLLATE a la columna, ya que sin él puede fallar.';
    const { problema, solucion } = separarMensaje(mensaje);

    expect(desglosarGrupo(problema)).toEqual({
      lineas: '4, 5',
      ocurrencias: [
        'La columna cEstado de la temporal #TMP no tiene COLLATE',
        'La columna cDescripcion de la temporal #TMP no tiene COLLATE',
      ],
    });
    expect(solucion).toBe('Añadir COLLATE a la columna, ya que sin él puede fallar.');
  });

  it('deja intacto un hallazgo simple', () => {
    expect(desglosarGrupo('La tabla dbo.TB_Estado no tiene WITH(NOLOCK).')).toEqual({
      lineas: null,
      ocurrencias: ['La tabla dbo.TB_Estado no tiene WITH(NOLOCK).'],
    });
  });
});
