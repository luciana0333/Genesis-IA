"""Caso 3: la tabla esta documentada, pero faltan tres columnas."""

TABLA = """
CREATE TABLE CLICKTOPAY.Cliente (
    Id INT,
    Nombre VARCHAR(80),
    Estado INT,
    FechaAlta DATETIME
)
"""

DICCIONARIO = """
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla de clientes',
@level0type=N'SCHEMA',
@level0name=N'CLICKTOPAY',
@level1type=N'TABLE',
@level1name=N'Cliente'
GO
"""
