"""Caso 5: ADD exige documentar la columna; ALTER COLUMN existente no falla."""

ALTER_ADD = """
ALTER TABLE CLICKTOPAY.Cliente
ADD cCelular VARCHAR(20)
"""

DICCIONARIO_TABLA = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'Cliente'
GO
"""

ALTER_COLUMN = """
ALTER TABLE CLICKTOPAY.Cliente
ALTER COLUMN Nombre VARCHAR(120)
"""

DICCIONARIO_EXISTENTE = DICCIONARIO_TABLA + """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Nombre del cliente',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'Cliente',
@level2type=N'COLUMN',
@level2name=N'Nombre'
GO
"""
