# -*- coding: utf-8 -*-
"""
CASO 4: El diccionario documenta el parametro, pero NO tiene la
descripcion del procedimiento en si.
RESULTADO ESPERADO: 1 hallazgo (PROCEDIMIENTO_SIN_DESCRIPCION).
"""

from app.analizadores.diccionario import verificar_diccionario

PROCEDIMIENTO = """
CREATE PROCEDURE Dbo.PA_Cuenta_Ins_NuevaCuenta
(
    @cCtaCod VARCHAR(20)
)
AS
BEGIN
    SELECT 1
END
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo de cuenta',
@level0type=N'SCHEMA',
@level0name=N'Dbo',
@level1type=N'PROCEDURE',
@level1name=N'PA_Cuenta_Ins_NuevaCuenta',
@level2type=N'PARAMETER',
@level2name=N'@cCtaCod'
GO
"""

if __name__ == "__main__":
    hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO)
    print(f"Hallazgos encontrados: {len(hallazgos)} (se esperaba: 1)\n")
    for h in hallazgos:
        print(h)