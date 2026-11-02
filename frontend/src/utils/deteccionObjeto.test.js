import { describe, expect, it } from 'vitest';
import { extraerNombreObjeto, extraerNombresObjetos, resumirNombresObjetos } from './deteccionObjeto';

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

describe('extraerNombresObjetos y resumirNombresObjetos', () => {
  const varios = [
    'ALTER PROCEDURE DUN.PA_Solicitud_Sel_Avance\n(\n @nOrigenId INT\n)\nAS\nSELECT 1\nGO',
    '-- ALTER PROCEDURE DUN.PA_Comentado',
    'ALTER PROCEDURE DUN.PA_Solicitud_Sel_DetalleBasicoSolicitud\nAS\nSELECT 1\nGO',
    'CREATE PROCEDURE [DUN].[PA_Solicitud_Ins_Registro]\nAS\nSELECT 1',
  ].join('\n');

  it('toma todos los objetos del script, en orden, sin comentarios ni repetidos', () => {
    expect(extraerNombresObjetos(varios)).toEqual([
      'DUN.PA_Solicitud_Sel_Avance', 'DUN.PA_Solicitud_Sel_DetalleBasicoSolicitud', 'DUN.PA_Solicitud_Ins_Registro',
    ]);
    expect(extraerNombresObjetos(`${varios}\nALTER PROCEDURE DUN.PA_Solicitud_Sel_Avance`)).toHaveLength(3);
  });

  it('con uno solo queda su nombre; con varios, el primero y cuántos más hay', () => {
    expect(resumirNombresObjetos([])).toBe('');
    expect(resumirNombresObjetos(['dbo.Cliente'])).toBe('dbo.Cliente');
    expect(resumirNombresObjetos(extraerNombresObjetos(varios))).toBe('DUN.PA_Solicitud_Sel_Avance y 2 más');
  });
});
