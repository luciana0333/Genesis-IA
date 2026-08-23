# -*- coding: utf-8 -*-
"""
CASO 5: Varios errores acumulados: esquema erroneo, falta descripcion
del procedimiento, parametro sin documentar, descripcion vacia,
valores sin comillas.
RESULTADO ESPERADO: 6 hallazgos.
"""

from app.analizadores.diccionario import verificar_diccionario

PROCEDIMIENTO = """
CREATE PROCEDURE CCE.PA_Archivo_Sel_ValidaArchivo
(
    @cArchivosValidar VARCHAR(500),
    @nCantidadArchivos INT
)
AS
BEGIN
    SELECT 1
END
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'',
@level0type=N'SCHEMA',
@level0name=DBO,
@level1type=N'PROCEDURE',
@level1name=PA_ARCHIVO_SEL_VALIDAARCHIVO,
@level2type=N'PARAMETER',
@level2name=N'@cArchivosValidar'
GO
"""

if __name__ == "__main__":
    hallazgos = verificar_diccionario(PROCEDIMIENTO, DICCIONARIO)
    print(f"Hallazgos encontrados: {len(hallazgos)} (se esperaba: 6)\n")
    for h in hallazgos:
        print(h)