"""Caso 2: las columnas estan documentadas, pero la tabla no."""

TABLA = """
CREATE TABLE CLICKTOPAY.Cliente (
    Id INT NOT NULL,
    Nombre VARCHAR(80) NOT NULL
)
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Identificador',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'Cliente',
@level2type=N'COLUMN',
@level2name=N'Id'
GO
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
