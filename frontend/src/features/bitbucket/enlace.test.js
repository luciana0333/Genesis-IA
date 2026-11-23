import { describirReferencia, leerEnlace } from './enlace';

describe('leerEnlace', () => {
  it('reconoce los tres tipos de link que mandan los desarrolladores', () => {
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/overview')).toEqual({
      tipo: 'pr', espacio: 'cajaica', repositorio: 'objetos-base-de-datos', referencia: '129',
      enlace: 'https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/overview',
    });
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos/branch/feature/60PSO2026-adecuar-deposito-cts-cuenta'))
      .toMatchObject({ tipo: 'rama', referencia: 'feature/60PSO2026-adecuar-deposito-cts-cuenta' });
    expect(leerEnlace('https://bitbucket.org/cajaica/genn-ocr/commits/602464364d664f7377a8cb43f65d4d8248980305'))
      .toMatchObject({ tipo: 'commit', repositorio: 'genn-ocr', referencia: '602464364d664f7377a8cb43f65d4d8248980305' });
  });

  it('tolera lo que suele venir al copiar del correo', () => {
    const casos = [
      '  https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129  ',
      'bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129',
      'https://www.bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/diff#chg-archivo.sql',
      'https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129?w=1',
      'http://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/129/',
    ];
    for (const caso of casos) {
      expect(leerEnlace(caso)).toMatchObject({ tipo: 'pr', repositorio: 'objetos-base-de-datos', referencia: '129' });
    }
  });

  it('una rama con caracteres codificados se lee como se escribió', () => {
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos/branch/refactor%2Fmejorar-alerta'))
      .toMatchObject({ tipo: 'rama', referencia: 'refactor/mejorar-alerta' });
  });

  it('explica qué falta cuando el link no sirve', () => {
    expect(leerEnlace('').error).toMatch(/Pega el link/);
    expect(leerEnlace('https://github.com/cajaica/repo/pull/1').error).toMatch(/no es de Bitbucket/);
    expect(leerEnlace('https://bitbucket.org/cajaica').error).toMatch(/Falta el repositorio/);
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos').error).toMatch(/pull request, una rama o un commit/);
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos/pull-requests/abc').error).toMatch(/pull request/);
    expect(leerEnlace('https://bitbucket.org/cajaica/objetos-base-de-datos/commits/zzz').error).toMatch(/commit/);
    expect(leerEnlace('https://bitbucket.org.evil.com/cajaica/repo/pull-requests/1').error).toMatch(/no es de Bitbucket/);
  });
});

describe('describirReferencia', () => {
  it('arma el texto corto de cada tipo', () => {
    expect(describirReferencia({ tipo: 'pr', referencia: '129' })).toBe('Pull request #129');
    expect(describirReferencia({ tipo: 'commit', referencia: '602464364d664f7377' })).toBe('Commit 6024643');
    expect(describirReferencia({ tipo: 'rama', referencia: 'feature/x' })).toBe('Rama feature/x');
  });
});
