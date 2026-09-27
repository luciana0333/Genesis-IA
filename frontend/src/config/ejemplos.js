/**
 * Scripts de ejemplo con los que se precargan los editores de cada vista.
 */

export const SQL_PROCEDIMIENTO = `CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Consultar
    @nClienteId INT
AS
BEGIN
    SELECT nClienteId, cCodPersona, cCorreoElectronico
    FROM CLICKTOPAY.Cliente
    WHERE nClienteId = @nClienteId;
END;`;

export const SQL_TABLA = `CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    cCodPersona VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    cCorreoElectronico VARCHAR(64) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)
);`;

export const SQL_REPORTE = `ALTER PROCEDURE dbo.PA_BI_Reporte
AS
BEGIN
    SELECT cCodigo, cNombre
    FROM dbo.Cliente WITH(NOLOCK);
END;`;

export const SQL_NORMAL = `ALTER PROCEDURE dbo.PA_Cliente_Actualizar
    @nClienteId INT,
    @cNombre VARCHAR(100)
AS
BEGIN
    UPDATE dbo.Cliente
    SET cNombre = @cNombre
    WHERE nClienteId = @nClienteId;
END;`;

export const DICCIONARIO_PROCEDIMIENTO = `EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Consulta la informacion del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Consultar'
GO`;

export const DICCIONARIO_TABLA = `EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Tabla que almacena la informacion del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'TABLE', @level1name=N'Cliente'
GO
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Identificador unico del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'TABLE', @level1name=N'Cliente',
@level2type=N'COLUMN', @level2name=N'nClienteId'
GO
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Codigo de persona asociado al cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'TABLE', @level1name=N'Cliente',
@level2type=N'COLUMN', @level2name=N'cCodPersona'
GO
EXEC sys.sp_addextendedproperty
@name=N'MS_Description',
@value=N'Correo electronico de contacto del cliente',
@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY',
@level1type=N'TABLE', @level1name=N'Cliente',
@level2type=N'COLUMN', @level2name=N'cCorreoElectronico'
GO`;

export const NOMBRE_OBJETO_INICIAL = 'CLICKTOPAY.Cliente';
