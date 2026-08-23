# -*- coding: utf-8 -*-
"""
CASO 2: Procedimiento con 4 parametros, pero solo 2 documentados.
RESULTADO ESPERADO: 2 hallazgos.
"""

from app.analizadores.diccionario import verificar_diccionario

PROCEDIMIENTO = """
CREATE PROCEDURE RRHH.PA_PersonaTrabajador_SelContrato
(
    @cPersCod VARCHAR(13),
    @nTipoContrato INT,
    @dFechaInicio DATE,
    @bActivo BIT
)
AS
BEGIN
    SELECT 1
END
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Busca el contrato de un trabajador',
@level0type=N'SCHEMA',
@level0name=N'RRHH',
@level1type=N'PROCEDURE',
@level1name=N'PA_PersonaTrabajador_SelContrato'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo de la persona',
@level0type=N'SCHEMA',
@level0name=N'RRHH',
@level1type=N'PROCEDURE',
@level1name=N'PA_PersonaTrabajador_SelContrato',
@level2type=N'PARAMETER',
@level2name=N'@cPersCod'
GO

EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tipo de contrato',
@level0type=N'SCHEMA',
@level0name=N'RRHH',
@level1type=N'PROCEDURE',
@level1name=N'PA_PersonaTrabajador_SelContrato',
@level2type=N'PARAMETER',
@level2name=N'@nTipoContrato'
GO
"""

if __name__ == "__main__":
    hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO)
    print(f"Hallazgos encontrados: {len(hallazgos)} (se esperaba: 2)\n")
    for h in hallazgos:
        print(h)