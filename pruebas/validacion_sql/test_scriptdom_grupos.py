"""Validación SQL Server (grupos 1, 2, 3, 4 y 6, 3 nov.): cada validación marca su caso y deja pasar lo válido.

Los casos que hacen fallar el script o dan un resultado equivocado se comprobaron en SQL Server. Cada caso es
(nombre, código, tipo esperado); con tipo None, ese código NO debe marcarse con el tipo de su mismo nombre
(«x ok …» no debe dar el tipo de «x»). Se saltan si la PC no tiene ScriptDom (viene con SSMS).
"""

import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura
from app.analizadores.scriptdom_mensajes import mensaje_hecho

HAY_SCRIPTDOM = LECTOR_SCRIPTDOM.estado().get("disponible", False) and LECTOR_SCRIPTDOM.estado().get("revisor", False)

CASOS = [
    ('137', 'CREATE PROCEDURE dbo.PA_X\n  @pcCod VARCHAR(20), @pnId INT\nAS\nBEGIN\n  SELECT @nNoDeclarada\n  SELECT @pcCod, @pnId\nEND', 'VARIABLE_NO_DECLARADA'),
    ('137 antes del DECLARE', 'CREATE PROCEDURE dbo.PA_X\n  @pcCod VARCHAR(20), @pnId INT\nAS\nBEGIN\n  SET @n = 1\n  DECLARE @n INT\n  SELECT @pcCod, @pnId\nEND', 'VARIABLE_NO_DECLARADA'),
    ('137 ok sp_executesql @p', "CREATE PROCEDURE dbo.PA_X\n  @pcCod VARCHAR(20), @pnId INT\nAS\nBEGIN\n  DECLARE @x INT = 1, @s NVARCHAR(100) = N'SELECT @p'\n  EXEC sp_executesql @s, N'@p INT', @p = @x\n  SELECT @pcCod, @pnId\nEND", None),
    ('134', 'CREATE PROCEDURE dbo.PA_X\n  @pcCod VARCHAR(20), @pnId INT\nAS\nBEGIN\n  DECLARE @n INT\n  DECLARE @N INT\n  SELECT @pcCod, @pnId\nEND', 'VARIABLE_DECLARADA_DOS_VECES'),
    ('134 param', 'CREATE PROCEDURE dbo.PA_X @pnId INT AS\nDECLARE @pnId INT\nSELECT @pnId', 'VARIABLE_DECLARADA_DOS_VECES'),
    ('205', 'SELECT 1, 2\nUNION ALL\nSELECT 3', 'UNION_COLUMNAS_DISTINTAS'),
    ('205 ok', 'SELECT 1, 2 UNION ALL SELECT 3, 4', None),
    ('2715', "DECLARE @c VARCHR(10) = 'a'\nSELECT @c", 'TIPO_DESCONOCIDO'),
    ('2715 ok sysname', "DECLARE @s SYSNAME = 'a'\nSELECT @s", None),
    ('2715 ok tipo propio', 'DECLARE @t TipoCuenta\nSELECT @t', None),
    ('131', "DECLARE @v VARCHAR(9000) = 'a'\nSELECT @v", 'TAMANO_FUERA_DE_RANGO'),
    ('2717 nvarchar', "DECLARE @v NVARCHAR(5000) = 'a'\nSELECT @v", 'TAMANO_FUERA_DE_RANGO'),
    ('2717 decimal', 'DECLARE @v DECIMAL(40, 2) = 1\nSELECT @v', 'TAMANO_FUERA_DE_RANGO'),
    ('192 escala', 'DECLARE @v DECIMAL(5, 8) = 1\nSELECT @v', 'TAMANO_FUERA_DE_RANGO'),
    ('1001 char 0', "DECLARE @v CHAR(0) = 'a'\nSELECT @v", 'TAMANO_FUERA_DE_RANGO'),
    ('tamaño ok MAX', "DECLARE @v VARCHAR(MAX) = 'a', @w NVARCHAR(4000) = N'b'\nSELECT @v, @w", None),
    ('8159', 'WITH C (a, b) AS (SELECT 1) SELECT a FROM C', 'CTE_COLUMNAS_DISTINTAS'),
    ('239', 'WITH C AS (SELECT 1 AS a), C AS (SELECT 2 AS a) SELECT a FROM C', 'CTE_NOMBRE_REPETIDO'),
    ('135', 'IF 1 = 1 BREAK', 'BREAK_FUERA_DE_WHILE'),
    ('135 ok', 'DECLARE @i INT = 0\nWHILE @i < 3 BEGIN SET @i += 1 IF @i = 2 BREAK END', None),
    ('133', 'GOTO Fin', 'GOTO_SIN_ETIQUETA'),
    ('133 ok', 'GOTO Fin\nFin:\nSELECT 1', None),
    ('1033 ok FOR XML', "SELECT (SELECT 1 AS a ORDER BY a FOR XML PATH('')) AS x", None),
    ('1033 ok TOP', 'SELECT a FROM (SELECT TOP 5 1 AS a ORDER BY a) x', None),
    ('147', 'SELECT n FROM #W WHERE SUM(n) > 0', 'AGREGADO_EN_WHERE'),
    ('147 ok subconsulta', 'SELECT n FROM #W WHERE n > (SELECT SUM(n) FROM #W)', None),
    ('2744', 'CREATE TABLE #I (a INT IDENTITY(1,1), b INT IDENTITY(1,1))', 'DOS_IDENTITY'),
    ('VARCHAR sin tamaño', "DECLARE @c VARCHAR = 'x'\nSELECT @c", 'VARCHAR_SIN_TAMANO'),
    ('CAST sin tamaño', 'SELECT CAST(n AS VARCHAR) FROM #T', 'VARCHAR_SIN_TAMANO'),
    ('CHAR ok columna', 'CREATE TABLE #T (cFlag CHAR)', None),
    ('= NULL', 'DECLARE @x INT = 1\nIF @x = NULL SELECT 1', 'COMPARACION_CON_NULL'),
    ('<> NULL WHERE', 'SELECT a FROM dbo.T WHERE a <> NULL', 'COMPARACION_CON_NULL'),
    ('CASE WHEN NULL', 'DECLARE @x INT = 1\nSELECT CASE @x WHEN NULL THEN 1 ELSE 2 END', 'COMPARACION_CON_NULL'),
    ('= NULL ok SET', 'DECLARE @x INT\nSET @x = NULL\nSELECT @x', None),
    ('ISNULL corta', "DECLARE @c VARCHAR(3) = NULL\nSELECT ISNULL(@c, 'Sin dato')", 'ISNULL_TRUNCA'),
    ('ISNULL ok', "DECLARE @c VARCHAR(20) = NULL\nSELECT ISNULL(@c, 'Sin dato')", None),
    ('texto largo', "DECLARE @c VARCHAR(5) = 'Lima Norte'\nSELECT @c", 'TEXTO_MAS_LARGO_QUE_VARIABLE'),
    ('texto largo SET', "DECLARE @c VARCHAR(5)\nSET @c = 'Lima Norte'\nSELECT @c", 'TEXTO_MAS_LARGO_QUE_VARIABLE'),
    ('varias filas', 'DECLARE @n INT\nSELECT @n = n FROM #V\nSELECT @n', 'ASIGNACION_VARIAS_FILAS'),
    ('varias filas ok WHERE', 'DECLARE @n INT\nSELECT @n = n FROM #V WHERE id = 1\nSELECT @n', None),
    ('varias filas ok acumula', "DECLARE @c VARCHAR(MAX) = ''\nSELECT @c = @c + cNombre + ',' FROM #V\nSELECT @c", None),
    ('varias filas ok agregado', 'DECLARE @n INT\nSELECT @n = COUNT(*) FROM #V\nSELECT @n', None),
    ('NOT IN', 'SELECT a FROM dbo.T WHERE a NOT IN (SELECT b FROM dbo.U)', 'NOT_IN_SUBCONSULTA'),
    ('NOT IN ok lista', 'SELECT a FROM dbo.T WHERE a NOT IN (1, 2)', None),
    ('TOP sin ORDER', 'SELECT TOP 1 a FROM dbo.T', 'TOP_SIN_ORDER_BY'),
    ('TOP ok ORDER', 'SELECT TOP 1 a FROM dbo.T ORDER BY a', None),
    ('TOP ok EXISTS', 'IF EXISTS (SELECT TOP 1 1 FROM dbo.T) SELECT 1', None),
    ('BETWEEN', "DECLARE @d DATETIME = GETDATE()\nIF @d BETWEEN '2026-11-01' AND '2026-11-30' SELECT 1", 'BETWEEN_FECHA_SIN_HORA'),
    ('BETWEEN temporal', "CREATE TABLE #F (dFecha DATETIME)\nSELECT 1 FROM #F WHERE dFecha BETWEEN '20261101' AND '20261130'", 'BETWEEN_FECHA_SIN_HORA'),
    ('BETWEEN ok DATE', "DECLARE @d DATE = GETDATE()\nIF @d BETWEEN '2026-11-01' AND '2026-11-30' SELECT 1", None),
    ('ROWCOUNT', 'UPDATE dbo.T SET a = 1 WHERE b = 2\nSET @x = 1\nIF @@ROWCOUNT = 0 SELECT 1', 'ROWCOUNT_DESPUES_DE_OTRA'),
    ('ROWCOUNT ok', 'UPDATE dbo.T SET a = 1 WHERE b = 2\nIF @@ROWCOUNT = 0 SELECT 1', None),
    ('@@IDENTITY', 'INSERT INTO dbo.T (a) VALUES (1)\nSELECT @@IDENTITY', 'USO_ARROBA_IDENTITY'),
    ('sin valor', 'DECLARE @n INT\nSET @n = @n + 1\nSELECT @n', 'VARIABLE_SIN_VALOR'),
    ('sin valor ok ISNULL', 'DECLARE @n INT\nSET @n = ISNULL(@n, 0) + 1\nSELECT @n', None),
    ('sin valor ok IS NULL', 'DECLARE @n INT\nIF @n IS NULL SET @n = 1\nSELECT @n', None),
    ('sin valor ok EXEC OUTPUT', 'DECLARE @n INT\nEXEC dbo.PA_Y @n OUTPUT\nSELECT @n', None),
    ('sin valor ok SELECT', 'DECLARE @n INT\nSELECT @n = COUNT(*) FROM #V\nSELECT @n', None),
    ('OUTPUT sin valor', 'CREATE PROCEDURE dbo.PA_X @pcRes VARCHAR(10) OUTPUT AS\nSELECT 1 WHERE @pcRes IS NULL', 'PARAMETRO_OUTPUT_SIN_VALOR'),
    ('OUTPUT ok', "CREATE PROCEDURE dbo.PA_X @pcRes VARCHAR(10) OUTPUT AS\nSET @pcRes = 'OK'", None),
    ('división', 'SELECT nMonto / nCuotas FROM dbo.Credito', 'DIVISION_SIN_NULLIF'),
    ('división ok NULLIF', 'SELECT nMonto / NULLIF(nCuotas, 0) FROM dbo.Credito', None),
    ('división ok número', 'SELECT nMonto / 100.0 FROM dbo.Credito', None),
    ('división ok CASE', 'SELECT CASE WHEN nCuotas = 0 THEN 0 ELSE nMonto / nCuotas END FROM dbo.Credito', None),
    ('ROLLBACK', 'BEGIN TRY\n BEGIN TRAN\n SELECT 1\n COMMIT\nEND TRY\nBEGIN CATCH\n ROLLBACK\nEND CATCH', 'ROLLBACK_SIN_VALIDAR'),
    ('ROLLBACK ok antes del TRY', 'BEGIN TRANSACTION\nBEGIN TRY\n INSERT INTO dbo.T (a) VALUES (1)\n COMMIT\nEND TRY\nBEGIN CATCH\n ROLLBACK TRANSACTION\nEND CATCH', None),
    ('ROLLBACK ok', 'BEGIN TRY\n BEGIN TRAN\n SELECT 1\n COMMIT\nEND TRY\nBEGIN CATCH\n IF @@TRANCOUNT > 0 ROLLBACK\nEND CATCH', None),
    ('TRAN sin TRY', 'BEGIN TRAN\nUPDATE dbo.T SET a = 1 WHERE b = 1\nCOMMIT', 'TRANSACCION_SIN_TRY'),
    ('TRAN ok antes del TRY', 'BEGIN TRANSACTION\nBEGIN TRY\n INSERT INTO dbo.T (a) VALUES (1)\n COMMIT\nEND TRY\nBEGIN CATCH\n ROLLBACK TRANSACTION\nEND CATCH', None),
    ('TRAN ok XACT_ABORT', 'SET XACT_ABORT ON\nBEGIN TRAN\nUPDATE dbo.T SET a = 1 WHERE b = 1\nCOMMIT', None),
    ('RETURN', 'SELECT 1\nRETURN\nSELECT 2', 'CODIGO_INALCANZABLE'),
    ('RETURN ok etiqueta', 'GOTO Fin\nRETURN\nFin:\nSELECT 2', None),
    ('APPLY', 'SELECT c.cCtaCod,\n (SELECT TOP 1 q.nMonto FROM dbo.CreditoCuota q WHERE q.cCtaCod = c.cCtaCod ORDER BY q.nCuota DESC) AS nMonto,\n (SELECT TOP 1 q.dVence FROM dbo.CreditoCuota q WHERE q.cCtaCod = c.cCtaCod ORDER BY q.nCuota DESC) AS dVence\nFROM dbo.Credito c', 'SUBCONSULTAS_A_APPLY'),
    ('APPLY ok una', 'SELECT c.cCtaCod, (SELECT TOP 1 q.nMonto FROM dbo.CreditoCuota q WHERE q.cCtaCod = c.cCtaCod ORDER BY q.nCuota DESC) AS nMonto FROM dbo.Credito c', None),
    ('APPLY ok distintas', 'SELECT c.cCtaCod, (SELECT MAX(q.nMonto) FROM dbo.CreditoCuota q WHERE q.cCtaCod = c.cCtaCod) AS a, (SELECT MAX(q.nMonto) FROM dbo.CreditoCuota q WHERE q.cCtaCod = c.cCtaCod AND q.nEstado = 1) AS b FROM dbo.Credito c', None),
    ('función YEAR', 'SELECT a FROM dbo.Mov m WHERE YEAR(m.dFecha) = 2026', 'FUNCION_SOBRE_COLUMNA'),
    ('función CONVERT', 'SELECT a FROM dbo.Mov m WHERE CONVERT(DATE, m.dFecha) = @d', 'FUNCION_SOBRE_COLUMNA'),
    ('función ok temporal', 'SELECT a FROM #Mov m WHERE YEAR(m.dFecha) = 2026', None),
    ('función ok SELECT', 'SELECT YEAR(m.dFecha) FROM dbo.Mov m', None),
    ('LIKE %', "SELECT a FROM dbo.Persona p WHERE p.cNombre LIKE '%ana%'", 'LIKE_COMODIN_INICIO'),
    ('LIKE ok', "SELECT a FROM dbo.Persona p WHERE p.cNombre LIKE 'ana%'", None),
    ('COUNT > 0', 'IF (SELECT COUNT(*) FROM dbo.T WHERE a = 1) > 0 SELECT 1', 'COUNT_EN_LUGAR_DE_EXISTS'),
    ('COUNT = 0', 'IF (SELECT COUNT(*) FROM dbo.T WHERE a = 1) = 0 SELECT 1', 'COUNT_EN_LUGAR_DE_EXISTS'),
    ('COUNT ok = 41', 'IF (SELECT COUNT(*) FROM @R) <> 41 SELECT 1', None),
    ('función escalar', 'SELECT dbo.fn_Saldo(c.cCtaCod) FROM dbo.Credito c', 'FUNCION_ESCALAR_POR_FILA'),
    ('función escalar ok XML', "SELECT R.X.value('(@Id)[1]', 'INT') FROM @x.nodes('/r') R(X)", None),
    ('función escalar ok variable', 'SELECT dbo.fn_Actual(@c) FROM dbo.Credito c', None),
    ('función escalar ok SET', "DECLARE @n INT\nSET @n = dbo.fn_Saldo('1')\nSELECT @n", None),
    ('conversión número', 'SELECT a FROM dbo.Cuenta c WHERE c.cCtaCod = 109', 'CONVERSION_PREVISIBLE'),
    ('conversión ok NVARCHAR tabla real', "DECLARE @c NVARCHAR(20) = N'x'\nSELECT a FROM dbo.Cuenta c WHERE c.cCtaCod = @c", None),
    ('conversión temporal', "CREATE TABLE #C (cCod VARCHAR(10))\nSELECT 1 FROM #C WHERE cCod = N'x'", 'CONVERSION_PREVISIBLE'),
    ('conversión ok', "DECLARE @c VARCHAR(20) = 'x'\nSELECT a FROM dbo.Cuenta c WHERE c.cCtaCod = @c AND c.nEstado = 1", None),
    ('OR columnas', 'SELECT a FROM dbo.T WHERE cA = 1 OR cB = 2', 'OR_ENTRE_COLUMNAS'),
    ('OR ok misma', 'SELECT a FROM dbo.T WHERE cA = 1 OR cA = 2', None),
    ('OR ok catch-all', 'SELECT a FROM dbo.T WHERE @p IS NULL OR cA = @p', None),
    ('UNION', 'SELECT 1 UNION SELECT 2', 'UNION_SIN_ALL'),
    ('UNION ok ALL', 'SELECT 1 UNION ALL SELECT 2', None),
    ('DISTINCT JOIN', 'SELECT DISTINCT a.n FROM dbo.A a JOIN dbo.B b ON b.n = a.n', 'DISTINCT_CON_JOIN'),
    ('DISTINCT ok', 'SELECT DISTINCT a.n FROM dbo.A a', None),
    ('ORDER en INSERT', 'INSERT INTO #T (a) SELECT a FROM dbo.T ORDER BY a', 'ORDER_BY_EN_INSERT'),
    ('inyección', "CREATE PROCEDURE dbo.PA_X @pcCod VARCHAR(20) AS\nDECLARE @s NVARCHAR(500) = 'SELECT * FROM dbo.T WHERE c = ''' + @pcCod + ''''\nEXEC (@s)", 'SQL_DINAMICO_CONCATENA_PARAMETRO'),
    ('inyección ok sp_executesql param', "CREATE PROCEDURE dbo.PA_X @pcCod VARCHAR(20) AS\nDECLARE @s NVARCHAR(500) = N'SELECT * FROM dbo.T WHERE c = @p'\nEXEC sp_executesql @s, N'@p VARCHAR(20)', @p = @pcCod", None),
    ('xp_cmdshell', "EXEC master.dbo.xp_cmdshell 'dir'", 'XP_CMDSHELL'),
    ('credencial', "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=x;UID=sa;PWD=Clave123;', 'SELECT 1')", 'CREDENCIAL_EN_CODIGO'),
    ('anidamiento', 'IF 1=1 BEGIN IF 2=2 BEGIN IF 3=3 BEGIN IF 4=4 SELECT 1 END END END', 'ANIDAMIENTO_EXCESIVO'),
    ('anidamiento ok ELSE IF', 'IF 1=1 SELECT 1 ELSE IF 2=2 SELECT 2 ELSE IF 3=3 SELECT 3 ELSE IF 4=4 SELECT 4 ELSE IF 5=5 SELECT 5', None),
    ('bloque repetido', "UPDATE dbo.Credito SET nEstado = 2, dFechaMod = GETDATE(), cUsuario = 'x' WHERE cCtaCod = '1' AND nEstado = 1 AND nSaldo = 0 AND dVence < GETDATE() AND cAgencia IN ('01', '02', '03')\nUPDATE dbo.Credito SET nEstado = 2, dFechaMod = GETDATE(), cUsuario = 'x' WHERE cCtaCod = '1' AND nEstado = 1 AND nSaldo = 0 AND dVence < GETDATE() AND cAgencia IN ('01', '02', '03')\n", 'BLOQUE_REPETIDO'),
    ('parámetro sin uso', 'CREATE PROCEDURE dbo.PA_X @pnNoUsado INT, @pnId INT AS SELECT @pnId', 'PARAMETRO_SIN_USO'),
    ('CASE sin ELSE', "SELECT CASE WHEN a = 1 THEN 'x' END FROM dbo.T", 'CASE_SIN_ELSE'),
    ('procedimiento largo', 'CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\n  SELECT 1\nEND', 'PROCEDIMIENTO_MUY_LARGO'),
]


@unittest.skipUnless(HAY_SCRIPTDOM, "ScriptDom no está en esta PC (viene con SSMS)")
class GruposTest(unittest.TestCase):
    def test_cada_caso(self):
        for nombre, sql, esperado in CASOS:
            with self.subTest(caso=nombre):
                lectura = LECTOR_SCRIPTDOM.leer(sql)
                self.assertEqual(lectura["errores"], [])
                tipos = {h["tipo"] for h in lectura["hechos"] if mensaje_hecho(h)}
                if esperado:
                    self.assertIn(esperado, tipos)
                else:
                    base = nombre.split(" ok")[0]
                    prohibidos = {t for n, _, t in CASOS if t and n.split(" ok")[0] == base}
                    self.assertFalse(tipos & prohibidos)

    def test_varios_casos_en_una_observacion(self):
        hallazgos = validar_estructura("SELECT TOP 1 a FROM dbo.T\nSELECT TOP 1 b FROM dbo.U\nSELECT TOP 1 c FROM dbo.V")
        top = [h for h in hallazgos if h.regla == "TOP_SIN_ORDER_BY"]
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0].lineas, [1, 2, 3])
        self.assertEqual(top[0].severidad.value, "medio")
        self.assertTrue(top[0].mensaje.startswith("Se identificaron 3 casos, en las líneas 1, 2, 3: se identificó un TOP 1"))

    def test_isnull_se_reescribe_sin_perder_los_null(self):
        hallazgo = next(h for h in validar_estructura("SELECT a FROM dbo.T WHERE ISNULL(bEvaluado, 0) = 0")
                        if h.regla == "ISNULL_EN_CONDICION")
        self.assertIn("se puede reescribir sin la función: (bEvaluado = 0 OR bEvaluado IS NULL)", hallazgo.mensaje)

    def test_mensajes_de_errores_silenciosos(self):
        mensajes = {h.regla: h.mensaje for h in validar_estructura(
            "DECLARE @c VARCHAR(5) = 'Lima Norte'\nDECLARE @d VARCHAR(3) = NULL\nSELECT @c, ISNULL(@d, 'Sin dato')")}
        self.assertEqual(
            mensajes["TEXTO_MAS_LARGO_QUE_VARIABLE"],
            "Se identificó que a @c, de 5 caracteres, se le asigna 'Lima Norte', por lo que queda 'Lima '. Ampliar el "
            "tamaño de la variable, ya que SQL Server corta el texto sin avisar.",
        )
        self.assertIn("por lo que devuelve 'Sin'", mensajes["ISNULL_TRUNCA"])


if __name__ == "__main__":
    unittest.main()
