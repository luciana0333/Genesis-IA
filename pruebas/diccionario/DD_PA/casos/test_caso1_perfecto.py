# -*- coding: utf-8 -*-
"""
CASO 1: Diccionario perfecto.
Todo esta bien documentado: procedimiento con descripcion, el unico
parametro con su descripcion, esquema correcto, todo entre comillas.

RESULTADO ESPERADO: 0 hallazgos.
"""

from app.analizadores.diccionario import verificar_diccionario

PROCEDIMIENTO = """
CREATE PROCEDURE Dbo.PA_Persona_Sel
(
    @cPersCod VARCHAR(13)
)
AS
BEGIN
    SELECT 1
END
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Procedimiento que permite la busqueda de informacion de PERSONA',
@level0type=N'SCHEMA',
@level0name=N'Dbo',
@level1type=N'PROCEDURE',
@level1name=N'PA_Persona_Sel'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo unico de la persona a consultar',
@level0type=N'SCHEMA',
@level0name=N'Dbo',
@level1type=N'PROCEDURE',
@level1name=N'PA_Persona_Sel',
@level2type=N'PARAMETER',
@level2name=N'@cPersCod'
GO
"""

if __name__ == "__main__":
    hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO)
    print(f"Hallazgos encontrados: {len(hallazgos)} (se esperaba: 0)\n")
    for h in hallazgos:
        print(h)