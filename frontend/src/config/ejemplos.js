/**
 * Scripts de ejemplo con los que se precargan los editores de cada vista.
 */

export const SQL_PROCEDIMIENTO = `CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId
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

export const INDICES_TABLA = `CREATE NONCLUSTERED INDEX IX_Cliente_cCodPersona
    ON CLICKTOPAY.Cliente (cCodPersona);`;

export const SQL_REPORTE = `ALTER PROCEDURE dbo.PA_BI_Sel_Reporte
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
@level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Sel_PorId'
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

/*
 * Demos para "Ver ejemplo": scripts con errores típicos para mostrar los
 * hallazgos de cada revisión. Los ejemplos de arriba son los correctos con
 * que se precarga el editor.
 */
export const DEMO_REPORTE = `ALTER PROCEDURE dbo.PA_Cliente_Sel_Resumen
AS
BEGIN
    SELECT *
    INTO #Clientes
    FROM dbo.Cliente c
    INNER JOIN dbo.Agencia a ON a.nAgenciaId = c.nAgenciaId
    WHERE c.cEstado IN ('A');

    SELECT c.cNombre, LTRIM(RTRIM(c.cDocumento)) AS cDocumento
    FROM #Clientes c WITH(NOLOCK)
    ORDER BY 1;

    RAISERROR('Proceso terminado', 10, 1);
END;`;

export const DEMO_NORMAL = `ALTER PROCEDURE dbo.PA_Cliente_Upd_Estado
    @nClienteId INT
AS
BEGIN
    DECLARE @cLista VARCHAR(MAX);

    BEGIN TRAN;

    UPDATE c
    SET c.cEstado = 'I'
    FROM dbo.Cliente c WITH(NOLOCK)
    WHERE c.nClienteId IN (@nClienteId);

    SELECT * FROM #Pendientes WITH(NOLOCK);

    WAITFOR DELAY '00:00:05';
END;`;

export const DEMO_TABLA = `CREATE TABLE TB_cliente_datos (
    id INT,
    nombre89 VARCHAR(50),
    cDescripcion VARCHAR(MAX),
    nMonto DECIMAL(18,2) COLLATE SQL_Latin1_General_CP1_CI_AS
);`;

export const DEMO_INDICES = `CREATE INDEX idx_cliente
    ON TB_cliente_datos (nombre89);
CREATE UNIQUE CLUSTERED INDEX IXU_TB_cliente_datos_cDescripcion
    ON dbo.TB_cliente_datos (cDescripcion);`;

export const NOMBRE_OBJETO_INICIAL = 'CLICKTOPAY.Cliente';
