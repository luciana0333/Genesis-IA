import { describe, expect, it } from 'vitest';
import { extraerNombreObjeto } from './deteccionObjeto';

describe('extraerNombreObjeto', () => {
  it('toma el nombre del CREATE o ALTER, con su esquema y sin corchetes', () => {
    expect(extraerNombreObjeto('CREATE PROCEDURE dbo.PA_Cliente_Sel_Reporte\n  @n INT\nAS')).toBe('dbo.PA_Cliente_Sel_Reporte');
    expect(extraerNombreObjeto('ALTER PROC [dbo].[PA_Cliente_Upd]')).toBe('dbo.PA_Cliente_Upd');
    expect(extraerNombreObjeto('CREATE OR ALTER PROCEDURE PA_Sin_Esquema')).toBe('PA_Sin_Esquema');
    expect(extraerNombreObjeto('CREATE TABLE CLICKTOPAY.Cliente (')).toBe('CLICKTOPAY.Cliente');
  });

  it('ignora los comentarios y devuelve vacío si no hay objeto', () => {
    expect(extraerNombreObjeto('-- CREATE PROCEDURE dbo.Viejo\nCREATE PROCEDURE dbo.Nuevo')).toBe('dbo.Nuevo');
    expect(extraerNombreObjeto('SELECT 1')).toBe('');
  });
});
