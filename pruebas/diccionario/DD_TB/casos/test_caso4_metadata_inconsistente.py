"""Caso 4: esquema incorrecto, descripcion vacia y nombre sin comillas."""

TABLA = """
CREATE TABLE CLICKTOPAY.Cliente (
    Id INT,
    Estado INT
)
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=DBO,
@level1type=N'TABLE',
@level1name=N'Cliente'
GO
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'',
@level0type=N'SCHEMA',
@level0name=N'DBO',
@level1type=N'TABLE',
@level1name=N'Cliente',
@level2type=N'COLUMN',
@level2name=N'Id'
GO
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Estado del cliente',
@level0type=N'SCHEMA',
@level0name=N'DBO',
@level1type=N'TABLE',
@level1name=N'Cliente',
@level2type=N'COLUMN',
@level2name=N'Estado'
GO
"""
