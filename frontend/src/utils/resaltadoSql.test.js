import { describe, expect, it } from 'vitest';
import { tokenizarSql } from './resaltadoSql';

describe('tokenizarSql', () => {
  it('reconstruye exactamente el texto original', () => {
    const sql = "CREATE PROCEDURE dbo.PA_X_Sel\n  @nId INT -- id\nAS\nSELECT N'a''b' /* c */ FROM t;";
    expect(tokenizarSql(sql).map((f) => f.valor).join('')).toBe(sql);
  });

  it('clasifica palabras clave, variables, textos y comentarios', () => {
    const tipos = Object.fromEntries(
      tokenizarSql("select @nId, N'hola' -- nota").filter((f) => f.tipo !== 'texto').map((f) => [f.valor, f.tipo]),
    );
    expect(tipos).toEqual({ select: 'clave', '@nId': 'variable', "N'hola'": 'cadena', '-- nota': 'comentario' });
  });

  it('deja como texto los nombres que no son palabras clave', () => {
    expect(tokenizarSql('Cliente').map((f) => f.tipo)).toEqual(['texto']);
  });
});
