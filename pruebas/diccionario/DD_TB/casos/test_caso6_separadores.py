"""
Caso 6: el diccionario no depende de GO.

Incluye el script real de TB_SolicitudArchivos (sentencias separadas con ";",
sin GO, con una coma sobrante y nombres sin comillas) y variantes del mismo
diccionario correcto separado de distintas formas.
"""

TABLA = """
CREATE TABLE dbo.TB_SolicitudArchivos
(
    nSolicitudArchivoId INT IDENTITY(1,1) NOT NULL,
    nSolicitudId INT NOT NULL,
    cNombreArchivo VARCHAR(255) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL DEFAULT '',
    cRutaArchivo VARCHAR(500) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL DEFAULT '',
    dFechaRegistro DATETIME NOT NULL DEFAULT GETDATE(),
    bActivo BIT NOT NULL DEFAULT 1,

    CONSTRAINT PK_TB_SolicitudArchivos PRIMARY KEY CLUSTERED (nSolicitudArchivoId)
);
"""

# Script tal como lo entregó el equipo.
DICCIONARIO_REAL = """EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Identificador único de la tabla SolicitudArchivos',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,


EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Identificador único de la tabla SolicitudArchivos',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = nSolicitudArchivoId;

-- nSolicitudId
EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Identificador de la solicitud asociada',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = nSolicitudId;

-- cNombreArchivo
EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Nombre del archivo adjunto',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = cNombreArchivo;

-- cRutaArchivo
EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Ruta de almacenamiento del archivo',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = cRutaArchivo;

-- dFechaRegistro
EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Fecha de registro del archivo',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = dFechaRegistro;

-- bActivo
EXEC sys.sp_addextendedproperty
@name = N'MS_Description',
@value = N'Indica si el registro se encuentra activo (1=Activo, 0=Inactivo)',
@level0type = N'SCHEMA', @level0name = dbo,
@level1type = N'TABLE',  @level1name = TB_SolicitudArchivos,
@level2type = N'COLUMN', @level2name = bActivo;
"""

_DESCRIPCIONES = [
    (None, "Archivos adjuntos registrados para cada solicitud"),
    ("nSolicitudArchivoId", "Identificador unico del archivo de la solicitud"),
    ("nSolicitudId", "Identificador de la solicitud asociada"),
    ("cNombreArchivo", "Nombre del archivo adjunto"),
    ("cRutaArchivo", "Ruta de almacenamiento del archivo"),
    ("dFechaRegistro", "Fecha de registro del archivo; se asigna al insertar"),
    ("bActivo", "Indica si el registro se encuentra activo (1=Activo, 0=Inactivo)"),
]


def _sentencia(columna, descripcion):
    texto = (
        "EXEC sys.sp_addextendedproperty\n"
        "@name = N'MS_Description',\n"
        f"@value = N'{descripcion}',\n"
        "@level0type = N'SCHEMA', @level0name = N'dbo',\n"
        "@level1type = N'TABLE', @level1name = N'TB_SolicitudArchivos'"
    )
    if columna:
        texto += f",\n@level2type = N'COLUMN', @level2name = N'{columna}'"
    return texto


def diccionario_correcto(terminador: str) -> str:
    """El mismo diccionario válido, con cada sentencia seguida de `terminador`."""
    return "\n".join(_sentencia(col, desc) + terminador for col, desc in _DESCRIPCIONES)


# Variantes del diccionario correcto según cómo se separan las sentencias.
SEPARADORES = {
    "con GO": "\nGO",
    "con punto y coma": ";",
    "con punto y coma y GO": ";\nGO",
    "sin separador": "",
}
