/**
 * Vista previa decorativa del encabezado: un fragmento de SQL y los
 * hallazgos que produciría, uno por pestaña. Solo ilustra lo que hace cada
 * revisión; no se ejecuta.
 */
export const MUESTRAS_HERO = {
  diccionario: {
    archivo: 'diccionario_TB_Estado.sql',
    lineas: [
      'EXEC sys.sp_addextendedproperty',
      "  @name  = N'MS_Description',",
      "  @value = N'Indicatg si el estado está activo',",
      "  @level0type = N'SCHEMA', @level0name = N'dbo2',",
      "  @level1type = N'TABLE',  @level1name = N'TB_Estado';",
    ],
    marcadas: [2, 3],
    hallazgos: [
      { severidad: 'alto', texto: 'Esquema no coincide' },
      { severidad: 'medio', texto: "Palabra mal escrita: 'Indicatg'" },
    ],
  },
  tabla: {
    archivo: 'TB_SolicitudArchivos.sql',
    lineas: [
      'CREATE TABLE dbo.TB_SolicitudArchivos (',
      '  nSolicitudArchivoId INT IDENTITY(1,1) NOT NULL,',
      '  cNombreArchivo VARCHAR(255) NOT NULL,',
      '  RutaArchivo VARCHAR(500) NULL,',
      '  dFechaRegistro DATETIME NOT NULL',
      ');',
    ],
    marcadas: [2, 3],
    hallazgos: [
      { severidad: 'alto', texto: 'Columna sin COLLATE' },
      { severidad: 'medio', texto: 'Prefijo de columna inválido' },
    ],
  },
  reporte: {
    archivo: 'PA_BI_Reporte.sql',
    lineas: [
      'ALTER PROCEDURE dbo.PA_BI_Reporte',
      'AS',
      'BEGIN',
      '  SELECT *',
      '  FROM dbo.Cliente',
      '  ORDER BY 1;',
      'END;',
    ],
    marcadas: [3, 4],
    hallazgos: [
      { severidad: 'alto', texto: 'SELECT estrella prohibido' },
      { severidad: 'alto', texto: 'Tabla física sin NOLOCK' },
    ],
  },
  normal: {
    archivo: 'PA_Cliente_Actualizar.sql',
    lineas: [
      'ALTER PROCEDURE dbo.PA_Cliente_Actualizar',
      '  @nClienteId INT',
      'AS',
      'BEGIN',
      '  DECLARE @nTotal INT;',
      '  WHILE 1 = 1 BREAK;',
      'END;',
    ],
    marcadas: [4, 5],
    hallazgos: [
      { severidad: 'alto', texto: 'WHILE prohibido' },
      { severidad: 'alto', texto: 'Variable declarada sin uso' },
    ],
  },
  planes: {
    archivo: 'consulta_clientes.sqlplan',
    lineas: [
      '<RelOp PhysicalOp="Table Scan"',
      '       EstimateRows="36">',
      '  <RunTimeCountersPerThread',
      '       ActualRows="48983"',
      '       ActualLogicalReads="100362" />',
      '  <SpillToTempDb SpillLevel="1" />',
      '</RelOp>',
    ],
    marcadas: [4, 5],
    hallazgos: [
      { severidad: 'alto', texto: 'Spill hacia TempDB' },
      { severidad: 'alto', texto: 'Lecturas lógicas elevadas' },
    ],
  },
};
