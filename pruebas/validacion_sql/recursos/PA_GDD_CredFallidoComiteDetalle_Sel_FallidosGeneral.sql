/*******************************************************************************
PROCEDIMIENTO : dbo.PA_Rpt_ObtenerCredFallidoComiteDetalle
PROPOSITO     : Obtener la información de las actas de comités de
                créditos fallidos
AUTOR         : JDRH
FECHA         : 2026-10-28
REPORTE       : Reporte de Actas de Comités de Créditos Fallidos
CONTROL DE CAMBIOS
FECHA       USUARIO   DESCRIPCION
2026-11-20  JDRH   Creación del SP 

EJEMPLO EJECUCION:
EXEC DBO.PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral
    '2026-01-01',
    '2026-12-31',
    '27,28,31,33,34,38,39,37,40,36,35,41,42,43,44,46,47,49,48,98,51',
    1

*******************************************************************************/
ALTER PROCEDURE DBO.PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral(
	@dFechaInicio DATETIME,
	@dFechaFin DATETIME,
	@cTiendas VARCHAR(1000),
	@nFiltroCreditos INT
	)
AS
BEGIN
	SET NOCOUNT ON

	-- DECLARE @dFechaInicio       DATETIME     = '2026-01-01'; -- Fecha inicial del filtro    
	-- DECLARE @dFechaFin          DATETIME     = '2026-12-31'; -- Fecha final del filtro    
	-- DECLARE @cTiendas           VARCHAR(MAX) = '27,28,31,33,34,38,39,37,40,36,35,41,42,43,44,46,47,49,48,98,51,52,99,62,64,53,54,55,00,63,56,65,66,67,45,68,69,70,76,75,57,74,72,71,77,78,58,79,80,81,83,97,60,50,82,84,59,01,13,02,04,07,08,06,05,03,14,15,17,18,19,20,21,22,23,25,26,29,30,32,73,85';     
	-- DECLARE @nFiltroCreditos    INT          = -1; 
	
	DECLARE @dFechaDesde DATETIME = CONVERT(DATETIME, CONVERT(DATE, @dFechaInicio)),
		@dFechaHastaMasUno DATETIME = DATEADD(DAY, 1, CONVERT(DATETIME, CONVERT(DATE, @dFechaFin))),
		@dFechaDesdeDate DATE = CONVERT(DATE, @dFechaInicio),
		@dFechaHastaMasUnoDate DATE = DATEADD(DAY, 1, CONVERT(DATE, @dFechaFin)),
		@dFechaDesdeBI DATE = EOMONTH(CONVERT(DATE, @dFechaInicio), - 1),
		@dFechaInicioBI DATE,
		@dFechaProceso DATE,
		@dFechaLimite DATETIME,
		@nRolPresidente INT = 1,
		@nRolSecretario INT = 2,
		@nConsCodEstadoComite INT = 2059,
		@nConsCodPrdEstado INT = 3001,
		@nPrdEstadoDesembolso INT = 2002,
		@nRelacTitular INT = 20,
		@nRelacAsesorActual INT = 28,
		@nRelacAsesorOrigen INT = 38,
		@nCalendarioAplicado INT = 1,
		@nCuotaPagada INT = 1,
		@dFechaVacia DATETIME = '1900-01-01'

	SET @dFechaInicioBI = IIF(@nFiltroCreditos = 2, @dFechaDesdeDate, @dFechaDesdeBI)

	SELECT @dFechaProceso = CONVERT(DATE, CS.nConsSisValor, 103)
	FROM dbo.ConstSistema CS WITH (NOLOCK)
	WHERE CS.nConsSisCod = 16

	SET @dFechaLimite = DATEADD(DAY, 1, CONVERT(DATETIME, @dFechaProceso))

	DROP TABLE

	IF EXISTS #TmpAgencias
		CREATE TABLE #TmpAgencias (
			cAgeCod VARCHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cTienda VARCHAR(40) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cZonaRegional VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS
			)

	DROP TABLE

	IF EXISTS #TmpSesion
		CREATE TABLE #TmpSesion (
			nCredFallidoComiteId INT,
			cNomComite VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cNroActa VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nEstadoComite INT,
			cEstadoComite VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cZonaRegional VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cAgeCod VARCHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cTienda VARCHAR(40) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cPresidente VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cSecretario VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cHoraInicio VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cHoraCierre VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cFechaComite VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS,
			dFechaCreacion DATETIME,
			dFechaPeriodo DATE,
			cIntegrantesSesion VARCHAR(1000) COLLATE SQL_Latin1_General_CP1_CI_AS
			)

	DROP TABLE

	IF EXISTS #TmpIntegrantes
		CREATE TABLE #TmpIntegrantes (
			nCredFallidoComiteIntegranteId INT,
			nCredFallidoComiteId INT,
			nCredFallidoRolId INT,
			cPersCod VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cPersNombre VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cUser VARCHAR(4) COLLATE SQL_Latin1_General_CP1_CI_AS
			)

	DROP TABLE

	IF EXISTS #TmpFuenteBI
		CREATE TABLE #TmpFuenteBI (
			nComiteCreditoFallidoCandidatoId INT,
			dFechaProceso DATE,
			cAgeCod VARCHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCtaCod VARCHAR(18) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodCliente VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodAsesorActual VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodAsesorOrigen VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nDiasAtraso INT,
			nNroCalen INT,
			nCuotasPagadas INT,
			cTipoProducto CHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nPrdEstado INT,
			nSaldo MONEY,
			nComiteCreditoFallidoReglaId INT
			)

	DROP TABLE

	IF EXISTS #TmpCandidatos
		CREATE TABLE #TmpCandidatos (
			nCredFallidoComiteDetalleId INT,
			cCtaCod VARCHAR(18) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cAgeCod VARCHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodCliente VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodAsesorActual VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodAsesorOrigen VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nDiasAtraso INT,
			nNroCalen INT,
			nCuotasPagadas INT,
			cTipoProducto CHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nPrdEstado INT,
			nSaldoCap MONEY,
			nComiteCreditoFallidoReglaId INT
			)

	DROP TABLE

	IF EXISTS #TmpCreditoActa
		CREATE TABLE #TmpCreditoActa (
			nCredFallidoComiteDetalleId INT,
			nCredFallidoComiteId INT,
			cAgeCod VARCHAR(3) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCtaCod VARCHAR(18) COLLATE SQL_Latin1_General_CP1_CI_AS,
			bElegido BIT,
			cComentarioInclusion VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodResponsable VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cNombreResponsable VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			dFechaFinAnterior DATE,
			dPenultimoDiaMesActual DATE,
			dFechaInicioMes DATE,
			dUltimoDiaMesActual DATE,
			nCredFallidoChecklistId INT,
			bPuedeGenerar BIT,
			cCodCliente VARCHAR(13) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cNomCliente VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cProducto VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cTipoCredito VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cFechaDesembolso VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nSaldoCapitalOrigen MONEY,
			cCampana VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nMontoDesembolsado MONEY,
			cCuotaAtrasadaActa VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nDiasAtraso INT,
			cEstadoCredito VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cAsesorOrigen VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cAsesorActual VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cMotivoInclusionRegla VARCHAR(200) COLLATE SQL_Latin1_General_CP1_CI_AS,
			nTotalObservaciones INT,
			nVotosFallido INT,
			nVotosNoFallido INT,
			nVotoPresidente INT,
			cResolucionComite VARCHAR(30) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cOpinionRecuperaciones VARCHAR(30) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cSustentoRecuperaciones VARCHAR(1000) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cAcuerdos VARCHAR(4000) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cRecomendaciones VARCHAR(4000) COLLATE SQL_Latin1_General_CP1_CI_AS
			)

	DROP TABLE

	IF EXISTS #TmpChecklistCat
		CREATE TABLE #TmpChecklistCat (
			nCredFallidoComiteDetalleId INT,
			nCredFallidoChecklistId INT,
			nOrden INT,
			cCategoria VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cCodigo VARCHAR(15) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cObservacion VARCHAR(500) COLLATE SQL_Latin1_General_CP1_CI_AS,
			bRespuesta BIT,
			cCumplimiento VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AS,
			cDetalle VARCHAR(500) COLLATE SQL_Latin1_General_CP1_CI_AS
			)

	INSERT INTO #TmpAgencias (cAgeCod,cTienda)
	SELECT AGE.cAgeCod,
		AGE.cAgeDescripcion
	FROM STRING_SPLIT(@cTiendas, ',') S
	INNER JOIN dbo.Agencias AGE WITH (NOLOCK) ON AGE.cAgeCod = TRIM(S.value)
	WHERE TRIM(S.value) <> ''

	UPDATE AGF
	SET AGF.cZonaRegional = Z.cDesZona
	FROM #TmpAgencias AGF
	INNER JOIN dbo.ZonaAgencia ZA WITH (NOLOCK) ON ZA.cCodAge = AGF.cAgeCod
	INNER JOIN dbo.Zona Z WITH (NOLOCK) ON Z.cCodZona = ZA.cCodZona

	IF @nFiltroCreditos IN (1,0,- 1)
	BEGIN
		INSERT INTO #TmpSesion (
			nCredFallidoComiteId,
			cNomComite,
			cNroActa,
			nEstadoComite,
			cZonaRegional,
			cAgeCod,
			cTienda,
			cHoraInicio,
			cHoraCierre,
			cFechaComite,
			dFechaCreacion,
			dFechaPeriodo
			)
		SELECT CM.nCredFallidoComiteId,
			CM.cNomComite,
			'',
			CM.nEstado,
			AGF.cZonaRegional,
			CM.cAgeCod,
			AGF.cTienda,
			IIF(CM.dFechaInicio = @dFechaVacia, '', CONVERT(VARCHAR(5), CM.dFechaInicio, 108)),
			IIF(CM.dFechaFin = @dFechaVacia, '', CONVERT(VARCHAR(5), CM.dFechaFin, 108)),
			IIF(CM.dFechaInicio = @dFechaVacia, '', CONVERT(VARCHAR(10), CM.dFechaInicio, 23)),
			CM.dFechaCreacion,
			ISNULL(CONVERT(DATE, CM.dFechaCreacion), @dFechaProceso)
		FROM COLOCACIONES.CredFallidoComite CM WITH (NOLOCK)
		INNER JOIN #TmpAgencias AGF ON AGF.cAgeCod = CM.cAgeCod
		WHERE CM.bEstado = 1
			AND (
				(
					CM.dFechaInicio >= @dFechaDesde
					AND CM.dFechaInicio < @dFechaHastaMasUno
					)
				OR (
					CM.dFechaInicio = @dFechaVacia
					AND CM.dFechaCreacion >= @dFechaDesde
					AND CM.dFechaCreacion < @dFechaHastaMasUno
					)
				)

		UPDATE SES
		SET SES.cNroActa = CONCAT (
				RIGHT(CONCAT (
						'000',
						ISNULL(TRY_CAST(RIGHT(TRIM(SES.cNomComite), 4) AS INT), 0)
						), 3),
				'-',
				YEAR(SES.dFechaCreacion)
				)
		FROM #TmpSesion SES

		UPDATE SES
		SET SES.cEstadoComite = ISNULL(CES.cConsDescripcion, '')
		FROM #TmpSesion SES
		INNER JOIN dbo.Constante CES WITH (NOLOCK) ON CES.nConsValor = SES.nEstadoComite
			AND CES.nConsCod = @nConsCodEstadoComite

		INSERT INTO #TmpIntegrantes (
			nCredFallidoComiteIntegranteId,
			nCredFallidoComiteId,
			nCredFallidoRolId,
			cPersCod,
			cUser
			)
		SELECT ITG.nCredFallidoComiteIntegranteId,
			ITG.nCredFallidoComiteId,
			ITG.nCredFallidoRolId,
			ITG.cPersCod,
			ITG.cUser
		FROM COLOCACIONES.CredFallidoComiteIntegrante ITG WITH (NOLOCK)
		INNER JOIN #TmpSesion SES ON SES.nCredFallidoComiteId = ITG.nCredFallidoComiteId
		WHERE ITG.bEstado = 1

		UPDATE ITG
		SET ITG.cPersNombre = PER.cPersNombre
		FROM #TmpIntegrantes ITG
		INNER JOIN dbo.Persona PER WITH (NOLOCK) ON PER.cPersCod = ITG.cPersCod

		UPDATE SES
		SET SES.cPresidente = P.cPersNombre,
			SES.cSecretario = S.cPersNombre
		FROM #TmpSesion SES
		OUTER APPLY (
			SELECT TOP 1 I.cPersNombre
			FROM #TmpIntegrantes I
			WHERE I.nCredFallidoComiteId = SES.nCredFallidoComiteId
				AND I.nCredFallidoRolId = @nRolPresidente
			ORDER BY I.nCredFallidoComiteIntegranteId ASC
			) P
		OUTER APPLY (
			SELECT TOP 1 I.cPersNombre
			FROM #TmpIntegrantes I
			WHERE I.nCredFallidoComiteId = SES.nCredFallidoComiteId
				AND I.nCredFallidoRolId = @nRolSecretario
			ORDER BY I.nCredFallidoComiteIntegranteId ASC
			) S
		WHERE P.cPersNombre IS NOT NULL
			OR S.cPersNombre IS NOT NULL

		UPDATE SES
		SET SES.cIntegrantesSesion = L.cLista
		FROM #TmpSesion SES
		CROSS APPLY (
			SELECT STRING_AGG(I.cUser, '-') WITHIN
			GROUP (
					ORDER BY I.nCredFallidoRolId,
						I.cPersNombre
					) AS cLista
			FROM #TmpIntegrantes I
			WHERE I.nCredFallidoComiteId = SES.nCredFallidoComiteId
			) L
		WHERE L.cLista IS NOT NULL

		INSERT INTO #TmpCreditoActa (
			nCredFallidoComiteDetalleId,
			nCredFallidoComiteId,
			cAgeCod,
			cCtaCod,
			bElegido,
			cComentarioInclusion,
			cCodResponsable,
			dFechaFinAnterior,
			dPenultimoDiaMesActual,
			dFechaInicioMes,
			dUltimoDiaMesActual,
			nCredFallidoChecklistId,
			bPuedeGenerar,
			cCampana,
			cResolucionComite,
			nTotalObservaciones,
			nVotosFallido,
			nVotosNoFallido,
			nVotoPresidente
			)
		SELECT DET.nCredFallidoComiteDetalleId,
			DET.nCredFallidoComiteId,
			SES.cAgeCod,
			DET.cCtaCod,
			DET.bElegido,
			DET.cComentario,
			DET.cCodResponsable,
			EOMONTH(SES.dFechaPeriodo, - 1),
			DATEADD(DAY, - 1, EOMONTH(SES.dFechaPeriodo)),
			DATEADD(DAY, 1, EOMONTH(SES.dFechaPeriodo, - 1)),
			EOMONTH(SES.dFechaPeriodo),
			0,0,'SIN CAMPAÑA','',0,0,0,0
		FROM COLOCACIONES.CredFallidoComiteDetalle DET WITH (NOLOCK)
		INNER JOIN #TmpSesion SES ON SES.nCredFallidoComiteId = DET.nCredFallidoComiteId
		WHERE DET.bEstado = 1
			AND (
				DET.bElegido = @nFiltroCreditos
				OR @nFiltroCreditos = - 1
				)
	END

	IF @nFiltroCreditos IN (2,- 1)
	BEGIN
		INSERT INTO #TmpFuenteBI (
			nComiteCreditoFallidoCandidatoId,
			dFechaProceso,
			cAgeCod,
			cCtaCod,
			cCodCliente,
			cCodAsesorActual,
			cCodAsesorOrigen,
			nDiasAtraso,
			nNroCalen,
			nCuotasPagadas,
			cTipoProducto,
			nPrdEstado,
			nSaldo,
			nComiteCreditoFallidoReglaId
			)
		SELECT FC.nComiteCreditoFallidoCandidatoId,
			FC.dFechaProceso,
			SUBSTRING(FC.cCtaCod, 4, 2),
			FC.cCtaCod,
			FC.cCodCliente,
			FC.cCodAsesorActual,
			FC.cCodAsesorOrigen,
			FC.nDiasAtraso,
			FC.nNroCalen,
			FC.nCuotasPagadas,
			ISNULL(NULLIF(TRIM(FC.cTipoProducto), ''), SUBSTRING(FC.cCtaCod, 6, 3)),
			FC.nPrdEstado,
			FC.nSaldo,
			FC.nComiteCreditoFallidoReglaId
		FROM DBCMACICABI.dbo.ComiteCreditoFallidoCandidato FC WITH (NOLOCK)
		WHERE FC.dFechaProceso >= @dFechaInicioBI
			AND FC.dFechaProceso < @dFechaHastaMasUnoDate

		IF ISNULL(TRIM(@cTiendas), '') <> ''
		BEGIN
			DELETE FBI
			FROM #TmpFuenteBI FBI
			WHERE NOT EXISTS (
					SELECT 1
					FROM #TmpAgencias AGF
					WHERE AGF.cAgeCod = FBI.cAgeCod
					)
		END
	END
	ELSE IF @nFiltroCreditos IN (1,0)
	BEGIN
		INSERT INTO #TmpFuenteBI (
			nComiteCreditoFallidoCandidatoId,
			dFechaProceso,
			cAgeCod,
			cCtaCod,
			cCodCliente,
			cCodAsesorActual,
			cCodAsesorOrigen,
			nDiasAtraso,
			nNroCalen,
			nCuotasPagadas,
			cTipoProducto,
			nPrdEstado,
			nSaldo,
			nComiteCreditoFallidoReglaId
			)
		SELECT FC.nComiteCreditoFallidoCandidatoId,
			FC.dFechaProceso,
			SUBSTRING(FC.cCtaCod, 4, 2),
			FC.cCtaCod,
			FC.cCodCliente,
			FC.cCodAsesorActual,
			FC.cCodAsesorOrigen,
			FC.nDiasAtraso,
			FC.nNroCalen,
			FC.nCuotasPagadas,
			FC.cTipoProducto,
			FC.nPrdEstado,
			FC.nSaldo,
			FC.nComiteCreditoFallidoReglaId
		FROM DBCMACICABI.dbo.ComiteCreditoFallidoCandidato FC WITH (NOLOCK)
		INNER JOIN (
			SELECT DISTINCT cCtaCod
			FROM #TmpCreditoActa
			) CA ON CA.cCtaCod = FC.cCtaCod
		WHERE FC.dFechaProceso >= @dFechaDesdeBI
			AND FC.dFechaProceso < @dFechaHastaMasUnoDate
	END

	IF @nFiltroCreditos IN (1,0,- 1)
	BEGIN
		INSERT INTO #TmpCandidatos (
			nCredFallidoComiteDetalleId,
			cCtaCod,
			cCodCliente,
			cCodAsesorActual,
			cCodAsesorOrigen,
			nDiasAtraso,
			nNroCalen,
			nCuotasPagadas,
			cTipoProducto,
			nPrdEstado,
			nSaldoCap,
			nComiteCreditoFallidoReglaId
			)
		SELECT BI.nCredFallidoComiteDetalleId,
			BI.cCtaCod,
			BI.cCodCliente,
			BI.cCodAsesorActual,
			BI.cCodAsesorOrigen,
			BI.nDiasAtraso,
			BI.nNroCalen,
			BI.nCuotasPagadas,
			BI.cTipoProducto,
			BI.nPrdEstado,
			BI.nSaldoCap,
			BI.nComiteCreditoFallidoReglaId
		FROM (
			SELECT CA.nCredFallidoComiteDetalleId,
				CAN.cCtaCod,
				CAN.cCodCliente,
				CAN.cCodAsesorActual,
				CAN.cCodAsesorOrigen,
				CAN.nDiasAtraso,
				CAN.nNroCalen,
				CAN.nCuotasPagadas,
				CAN.cTipoProducto,
				CAN.nPrdEstado,
				CAN.nSaldo AS nSaldoCap,
				CAN.nComiteCreditoFallidoReglaId,
				ROW_NUMBER() OVER (
					PARTITION BY CA.nCredFallidoComiteDetalleId ORDER BY CAN.dFechaProceso DESC
					) AS nFila
			FROM #TmpCreditoActa CA
			INNER JOIN #TmpFuenteBI CAN ON CAN.cCtaCod = CA.cCtaCod
			WHERE CAN.dFechaProceso >= CA.dFechaFinAnterior
				AND CAN.dFechaProceso <= CA.dPenultimoDiaMesActual
			) BI
		WHERE BI.nFila = 1

		INSERT INTO #TmpCandidatos (
			nCredFallidoComiteDetalleId,
			cCtaCod,
			cCodCliente,
			cCodAsesorActual,
			cCodAsesorOrigen,
			nDiasAtraso,
			nNroCalen,
			nCuotasPagadas,
			cTipoProducto,
			nPrdEstado,
			nSaldoCap,
			nComiteCreditoFallidoReglaId
			)
		SELECT MANF.nCredFallidoComiteDetalleId,
			MANF.cCtaCod,
			MANF.cCodCliente,
			MANF.cCodAsesorActual,
			MANF.cCodAsesorOrigen,
			MANF.nDiasAtraso,
			MANF.nNroCalen,
			MANF.nCuotasPagadas,
			MANF.cTipoProducto,
			MANF.nPrdEstado,
			MANF.nSaldoCap,
			MANF.nComiteCreditoFallidoReglaId
		FROM (
			SELECT CA.nCredFallidoComiteDetalleId,
				MAN.cCtaCod,
				MAN.cCodCliente,
				MAN.cCodAsesorActual,
				MAN.cCodAsesorOrigen,
				MAN.nDiasAtraso,
				MAN.nNroCalen,
				MAN.nCuotasPagadas,
				MAN.cTipoProducto,
				MAN.nPrdEstado,
				MAN.nSaldo nSaldoCap,
				MAN.nComiteCreditoFallidoReglaId,
				ROW_NUMBER() OVER (
					PARTITION BY CA.nCredFallidoComiteDetalleId ORDER BY MAN.dFechaProceso DESC
					) AS nFila
			FROM #TmpCreditoActa CA
			INNER JOIN COLOCACIONES.ComiteCreditoFallidoCandidatoManual MAN WITH (NOLOCK) ON MAN.cCtaCod = CA.cCtaCod
			WHERE MAN.dFechaProceso >= CA.dFechaInicioMes
				AND MAN.dFechaProceso <= CA.dUltimoDiaMesActual
				AND NOT EXISTS (
					SELECT 1
					FROM #TmpCandidatos C
					WHERE C.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
					)
			) MANF
		WHERE MANF.nFila = 1

		INSERT INTO #TmpCandidatos (
			nCredFallidoComiteDetalleId,
			cCtaCod,
			cTipoProducto
			)
		SELECT CA.nCredFallidoComiteDetalleId,
			CA.cCtaCod,
			SUBSTRING(CA.cCtaCod, 6, 3)
		FROM #TmpCreditoActa CA
		WHERE NOT EXISTS (
				SELECT 1
				FROM #TmpCandidatos C
				WHERE C.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
				)

		IF EXISTS (
				SELECT 1
				FROM #TmpCandidatos
				WHERE nPrdEstado IS NULL
				)
		BEGIN
			UPDATE C
			SET C.nPrdEstado = COALESCE(C.nPrdEstado, PRD.nPrdEstado),
				C.cTipoProducto = COALESCE(C.cTipoProducto, SUBSTRING(PRD.cCtaCod, 6, 3))
			FROM #TmpCandidatos C
			INNER JOIN dbo.Producto PRD WITH (NOLOCK) ON PRD.cCtaCod = C.cCtaCod
			WHERE C.nPrdEstado IS NULL

			UPDATE C
			SET C.nNroCalen = COALESCE(C.nNroCalen, CRE.nNroCalen, 0),
				C.nDiasAtraso = COALESCE(C.nDiasAtraso, CRE.nDiasAtraso, 0)
			FROM #TmpCandidatos C
			INNER JOIN dbo.ColocacCred CRE WITH (NOLOCK) ON CRE.cCtaCod = C.cCtaCod
			WHERE C.nNroCalen IS NULL

			UPDATE C
			SET C.cCodCliente = COALESCE(NULLIF(C.cCodCliente, ''), PP.cCodCliente, ''),
				C.cCodAsesorActual = COALESCE(NULLIF(C.cCodAsesorActual, ''), PP.cCodAsesorActual, ''),
				C.cCodAsesorOrigen = COALESCE(NULLIF(C.cCodAsesorOrigen, ''), PP.cCodAsesorOrigen, '')
			FROM #TmpCandidatos C
			INNER JOIN (
				SELECT REL.cCtaCod,
					MAX(CASE 
							WHEN REL.nPrdPersRelac = @nRelacTitular
								THEN REL.cPersCod
							END) AS cCodCliente,
					MAX(CASE 
							WHEN REL.nPrdPersRelac = @nRelacAsesorActual
								THEN REL.cPersCod
							END) AS cCodAsesorActual,
					MAX(CASE 
							WHEN REL.nPrdPersRelac = @nRelacAsesorOrigen
								THEN REL.cPersCod
							END) AS cCodAsesorOrigen
				FROM dbo.ProductoPersona REL WITH (NOLOCK)
				INNER JOIN (
					SELECT DISTINCT cCtaCod
					FROM #TmpCandidatos
					WHERE cCodCliente IS NULL
						OR cCodCliente = ''
					) CF ON CF.cCtaCod = REL.cCtaCod
				WHERE REL.nPrdPersRelac IN (
						@nRelacTitular,
						@nRelacAsesorActual,
						@nRelacAsesorOrigen
						)
				GROUP BY REL.cCtaCod
				) PP ON PP.cCtaCod = C.cCtaCod

			UPDATE C
			SET C.nCuotasPagadas = CAL.nCuotasPagadas
			FROM #TmpCandidatos C
			INNER JOIN (
				SELECT C2.nCredFallidoComiteDetalleId,
					SUM(IIF(CL.nColocCalendEstado = @nCuotaPagada
							AND CL.dPago < @dFechaLimite, 1, 0)) AS nCuotasPagadas
				FROM #TmpCandidatos C2
				INNER JOIN dbo.ColocCalendario CL WITH (NOLOCK) ON CL.cCtaCod = C2.cCtaCod
					AND CL.nNroCalen = C2.nNroCalen
					AND CL.nColocCalendApl = @nCalendarioAplicado
				WHERE C2.nCuotasPagadas IS NULL
				GROUP BY C2.nCredFallidoComiteDetalleId
				) CAL ON CAL.nCredFallidoComiteDetalleId = C.nCredFallidoComiteDetalleId

			UPDATE C
			SET C.nSaldoCap = S.nSaldoCap
			FROM #TmpCandidatos C
			INNER JOIN (
				SELECT SLD.cCtaCod,
					SLD.nSaldoCap,
					ROW_NUMBER() OVER (
						PARTITION BY SLD.cCtaCod ORDER BY SLD.dFecha DESC
						) AS nFila
				FROM dbo.ColocacSaldo SLD WITH (NOLOCK)
				INNER JOIN (
					SELECT DISTINCT cCtaCod
					FROM #TmpCandidatos
					WHERE nSaldoCap IS NULL
					) CF ON CF.cCtaCod = SLD.cCtaCod
				WHERE SLD.dFecha < @dFechaLimite
				) S ON S.cCtaCod = C.cCtaCod
				AND S.nFila = 1
			WHERE C.nSaldoCap IS NULL
		END
	END

	IF @nFiltroCreditos IN (2,- 1)
	BEGIN
		INSERT INTO #TmpCandidatos (
			nCredFallidoComiteDetalleId,
			cAgeCod,
			cCtaCod,
			cCodCliente,
			cCodAsesorActual,
			cCodAsesorOrigen,
			nDiasAtraso,
			nNroCalen,
			nCuotasPagadas,
			cTipoProducto,
			nPrdEstado,
			nSaldoCap,
			nComiteCreditoFallidoReglaId
			)
		SELECT CSC.nDetalleIdNegativo,
			CSC.cAgeCod,
			CSC.cCtaCod,
			CSC.cCodCliente,
			CSC.cCodAsesorActual,
			CSC.cCodAsesorOrigen,
			CSC.nDiasAtraso,
			CSC.nNroCalen,
			CSC.nCuotasPagadas,
			CSC.cTipoProducto,
			CSC.nPrdEstado,
			CSC.nSaldo,
			CSC.nComiteCreditoFallidoReglaId
		FROM (
			SELECT - FBI.nComiteCreditoFallidoCandidatoId AS nDetalleIdNegativo,
				FBI.cAgeCod,
				FBI.cCtaCod,
				FBI.cCodCliente,
				FBI.cCodAsesorActual,
				FBI.cCodAsesorOrigen,
				FBI.nDiasAtraso,
				FBI.nNroCalen,
				FBI.nCuotasPagadas,
				FBI.cTipoProducto,
				FBI.nPrdEstado,
				FBI.nSaldo,
				FBI.nComiteCreditoFallidoReglaId,
				ROW_NUMBER() OVER (
					PARTITION BY FBI.cCtaCod ORDER BY FBI.dFechaProceso DESC,
						FBI.nComiteCreditoFallidoCandidatoId DESC
					) AS nFila
			FROM #TmpFuenteBI FBI
			WHERE FBI.dFechaProceso >= @dFechaDesdeDate
				AND NOT EXISTS (
					SELECT 1
					FROM #TmpCreditoActa CA
					WHERE CA.cCtaCod = FBI.cCtaCod
					)
			) CSC
		WHERE CSC.nFila = 1

		INSERT INTO #TmpCreditoActa (
			nCredFallidoComiteDetalleId,
			nCredFallidoComiteId,
			cAgeCod,
			cCtaCod,
			cCampana
			)
		SELECT C.nCredFallidoComiteDetalleId,
			NULL,
			C.cAgeCod,
			C.cCtaCod,
			'SIN CAMPAÑA'
		FROM #TmpCandidatos C
		WHERE C.nCredFallidoComiteDetalleId < 0
	END

	UPDATE CA
	SET CA.cCodCliente = CAN.cCodCliente,
		CA.nSaldoCapitalOrigen = CAN.nSaldoCap,
		CA.cCuotaAtrasadaActa = IIF(CAN.nCuotasPagadas IS NULL, '', CAST(CAN.nCuotasPagadas + 1 AS VARCHAR(10))),
		CA.cMotivoInclusionRegla = REG.cDescripcion,
		CA.cProducto = ISNULL(PRO.cDescripcion, ''),
		CA.cEstadoCredito = ISNULL(CPE.cConsDescripcion, '')
	FROM #TmpCreditoActa CA
	INNER JOIN #TmpCandidatos CAN ON CAN.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
	LEFT JOIN DBCMACICABI.dbo.ComiteCreditoFallidoRegla REG WITH (NOLOCK) ON REG.nComiteCreditoFallidoReglaId = CAN.nComiteCreditoFallidoReglaId
	LEFT JOIN dbo.CredProductos PRO WITH (NOLOCK) ON PRO.cCredProductos = ISNULL(CAN.cTipoProducto, SUBSTRING(CA.cCtaCod, 6, 3))
	LEFT JOIN dbo.Constante CPE WITH (NOLOCK) ON CPE.nConsValor = CAN.nPrdEstado
		AND CPE.nConsCod = @nConsCodPrdEstado

	UPDATE CA
	SET CA.nDiasAtraso = CRE.nDiasAtraso
	FROM #TmpCreditoActa CA
	INNER JOIN dbo.ColocacCred CRE WITH (NOLOCK) ON CRE.cCtaCod = CA.cCtaCod

	UPDATE CA
	SET CA.cTipoCredito = ISNULL(TIP.cDescripcion, '')
	FROM #TmpCreditoActa CA
	INNER JOIN dbo.Colocaciones COL WITH (NOLOCK) ON COL.cCtaCod = CA.cCtaCod
	INNER JOIN dbo.TipoCreditos TIP WITH (NOLOCK) ON TIP.nTipoCreditos = COL.nTipoCreditos

	UPDATE CA
	SET CA.cNomCliente = PCL.cPersNombre,
		CA.cAsesorActual = PAA.cPersNombre,
		CA.cAsesorOrigen = PAO.cPersNombre
	FROM #TmpCreditoActa CA
	INNER JOIN #TmpCandidatos CAN ON CAN.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
	LEFT JOIN dbo.Persona PCL WITH (NOLOCK) ON PCL.cPersCod = CAN.cCodCliente
	LEFT JOIN dbo.Persona PAA WITH (NOLOCK) ON PAA.cPersCod = CAN.cCodAsesorActual
	LEFT JOIN dbo.Persona PAO WITH (NOLOCK) ON PAO.cPersCod = CAN.cCodAsesorOrigen

	UPDATE CA
	SET CA.cCampana = ISNULL(CMP.cDescripcion, 'SIN CAMPAÑA')
	FROM #TmpCreditoActa CA
	LEFT JOIN (
		SELECT CCA.cCtaCod,
			CAM.cDescripcion,
			ROW_NUMBER() OVER (
				PARTITION BY CCA.cCtaCod ORDER BY CCA.idCampana ASC
				) AS nFila
		FROM dbo.ColocCredCampana CCA WITH (NOLOCK)
		INNER JOIN dbo.Campanas CAM WITH (NOLOCK) ON CAM.IdCampana = CCA.idCampana
		WHERE EXISTS (
				SELECT 1
				FROM #TmpCreditoActa CA2
				WHERE CA2.cCtaCod = CCA.cCtaCod
				)
		) CMP ON CMP.cCtaCod = CA.cCtaCod
		AND CMP.nFila = 1

	UPDATE CA
	SET CA.cFechaDesembolso = CONVERT(VARCHAR(10), DES.dPrdEstado, 103),
		CA.nMontoDesembolsado = DES.nMonto
	FROM #TmpCreditoActa CA
	INNER JOIN (
		SELECT EST.cCtaCod,
			EST.dPrdEstado,
			EST.nMonto,
			ROW_NUMBER() OVER (
				PARTITION BY EST.cCtaCod ORDER BY EST.dPrdEstado ASC
				) AS nFila
		FROM dbo.ColocacEstado EST WITH (NOLOCK)
		INNER JOIN (
			SELECT DISTINCT cCtaCod
			FROM #TmpCreditoActa
			WHERE cCtaCod IS NOT NULL
			) CA2 ON CA2.cCtaCod = EST.cCtaCod
		WHERE EST.nPrdEstado = @nPrdEstadoDesembolso
		) DES ON DES.cCtaCod = CA.cCtaCod
		AND DES.nFila = 1

	IF @nFiltroCreditos IN (1,0,- 1)
	BEGIN
		UPDATE CA
		SET CA.cNombreResponsable = ISNULL(PRE.cPersNombre, '')
		FROM #TmpCreditoActa CA
		INNER JOIN dbo.Persona PRE WITH (NOLOCK) ON PRE.cPersCod = CA.cCodResponsable
		WHERE CA.nCredFallidoComiteId IS NOT NULL

		UPDATE CA
		SET CA.nCredFallidoChecklistId = C.nCredFallidoChecklistId
		FROM #TmpCreditoActa CA
		INNER JOIN (
			SELECT CHK.nCredFallidoComiteDetalleId,
				CHK.nCredFallidoChecklistId,
				ROW_NUMBER() OVER (
					PARTITION BY CHK.nCredFallidoComiteDetalleId ORDER BY CHK.nCredFallidoChecklistId ASC
					) AS nFila
			FROM COLOCACIONES.CredFallidoChecklist CHK WITH (NOLOCK)
			INNER JOIN #TmpCreditoActa CA2 ON CA2.nCredFallidoComiteDetalleId = CHK.nCredFallidoComiteDetalleId
			WHERE CA2.nCredFallidoComiteId IS NOT NULL
				AND CHK.bEstado = 1
			) C ON C.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
			AND C.nFila = 1

		UPDATE CA
		SET CA.bPuedeGenerar = 1,
			CA.cOpinionRecuperaciones = IIF(RES.bVotoRecuperaciones = 1, 'CRÉDITO FALLIDO', 'CRÉDITO NO FALLIDO'),
			CA.cSustentoRecuperaciones = RES.cComentarioRecuperaciones
		FROM #TmpCreditoActa CA
		INNER JOIN COLOCACIONES.CredFallidoComiteResolucion RES WITH (NOLOCK) ON RES.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
			AND RES.bEstado = 1
		WHERE CA.nCredFallidoComiteId IS NOT NULL

		UPDATE CA
		SET CA.cAcuerdos = REV.cAcuerdos,
			CA.cRecomendaciones = REV.cRecomendaciones
		FROM #TmpCreditoActa CA
		INNER JOIN COLOCACIONES.CredFallidoComiteRevision REV WITH (NOLOCK) ON REV.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
			AND REV.bEstado = 1
		WHERE CA.nCredFallidoComiteId IS NOT NULL

		UPDATE CA
		SET CA.nVotosFallido = ISNULL(VOT.nVotosFallido, 0),
			CA.nVotosNoFallido = ISNULL(VOT.nVotosNoFallido, 0),
			CA.nVotoPresidente = ISNULL(VOT.nVotoPresidente, 0)
		FROM #TmpCreditoActa CA
		INNER JOIN (
			SELECT CA2.nCredFallidoComiteDetalleId,
				SUM(IIF(VTO.bVoto = 1, 1, 0)) AS nVotosFallido,
				SUM(IIF(VTO.nCredFallidoComiteVotoId IS NOT NULL
						AND VTO.bVoto = 0, 1, 0)) AS nVotosNoFallido,
				MAX(IIF(ITG.nCredFallidoRolId = @nRolPresidente
						AND VTO.bVoto = 1, 1, 0)) AS nVotoPresidente
			FROM #TmpCreditoActa CA2
			INNER JOIN #TmpIntegrantes ITG ON ITG.nCredFallidoComiteId = CA2.nCredFallidoComiteId
			INNER JOIN COLOCACIONES.CredFallidoRol RLL WITH (NOLOCK) ON RLL.nCredFallidoRolId = ITG.nCredFallidoRolId
				AND RLL.bPuedeVotar = 1
			LEFT JOIN COLOCACIONES.CredFallidoComiteVoto VTO WITH (NOLOCK) ON VTO.nCredFallidoComiteDetalleId = CA2.nCredFallidoComiteDetalleId
				AND VTO.cPersCod = ITG.cPersCod
			WHERE CA2.nCredFallidoComiteId IS NOT NULL
			GROUP BY CA2.nCredFallidoComiteDetalleId
			) VOT ON VOT.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId
		WHERE CA.nCredFallidoComiteId IS NOT NULL

		UPDATE CA
		SET CA.cResolucionComite = CASE 
				WHEN CA.nVotosFallido > CA.nVotosNoFallido
					THEN 'CRÉDITO FALLIDO'
				WHEN CA.nVotosFallido < CA.nVotosNoFallido
					THEN 'CRÉDITO NO FALLIDO'
				WHEN CA.nVotoPresidente = 1
					THEN 'CRÉDITO FALLIDO'
				ELSE 'CRÉDITO NO FALLIDO'
				END
		FROM #TmpCreditoActa CA
		WHERE CA.bPuedeGenerar = 1

		INSERT INTO #TmpChecklistCat (
			nCredFallidoComiteDetalleId,
			nCredFallidoChecklistId,
			nOrden,
			cCategoria,
			cCodigo,
			cObservacion,
			bRespuesta,
			cCumplimiento,
			cDetalle
			)
		SELECT CA.nCredFallidoComiteDetalleId,
			R.nCredFallidoChecklistId,
			ITE.nOrden,
			CASE 
				WHEN ITE.nOrden >= 1
					AND ITE.nOrden <= 6
					THEN 'Capacidad de Pago'
				WHEN ITE.nOrden >= 7
					AND ITE.nOrden <= 9
					THEN 'Determinación del Patrimonio'
				WHEN ITE.nOrden >= 10
					AND ITE.nOrden <= 12
					THEN 'Análisis de Unidad Familiar'
				WHEN ITE.nOrden >= 13
					AND ITE.nOrden <= 14
					THEN 'Cumplimiento Normativo'
				ELSE 'Doc. Falsa y/o Información Falsa'
				END,
			CONCAT (
				'O',
				ITE.nOrden
				),
			ITE.cDescripcion,
			R.bRespuesta,
			CASE 
				WHEN R.bRespuesta IS NULL
					THEN ''
				WHEN R.bRespuesta = 1
					THEN 'SI'
				ELSE 'NO'
				END,
			R.cComentario
		FROM #TmpCreditoActa CA
		INNER JOIN COLOCACIONES.CredFallidoChecklistRespuesta R WITH (NOLOCK) ON R.nCredFallidoChecklistId = CA.nCredFallidoChecklistId
		INNER JOIN COLOCACIONES.CredFallidoChecklistItem ITE WITH (NOLOCK) ON ITE.nCredFallidoChecklistItemId = R.nCredFallidoChecklistItemId
		WHERE CA.nCredFallidoChecklistId > 0
			AND ITE.bActivo = 1

		UPDATE CA
		SET CA.nTotalObservaciones = ISNULL(T.nTotalObservaciones, 0)
		FROM #TmpCreditoActa CA
		INNER JOIN (
			SELECT CK.nCredFallidoComiteDetalleId,
				SUM(IIF(CK.bRespuesta = 0, 1, 0)) AS nTotalObservaciones
			FROM #TmpChecklistCat CK
			GROUP BY CK.nCredFallidoComiteDetalleId
			) T ON T.nCredFallidoComiteDetalleId = CA.nCredFallidoComiteDetalleId

		INSERT INTO #TmpCreditoActa (
			nCredFallidoComiteDetalleId,
			nCredFallidoComiteId,
			cAgeCod
			)
		SELECT - 1000000000 - S1.nCredFallidoComiteId,
			S1.nCredFallidoComiteId,
			S1.cAgeCod
		FROM #TmpSesion S1
		WHERE NOT EXISTS (
				SELECT 1
				FROM #TmpCreditoActa CA
				WHERE CA.nCredFallidoComiteId = S1.nCredFallidoComiteId
				)
	END

	SELECT S1.cNomComite,
		S1.cEstadoComite,
		S1.cNroActa,
		AGF.cZonaRegional,
		AGF.cTienda,
		S1.cPresidente,
		S1.cSecretario,
		S1.cHoraInicio,
		S1.cHoraCierre,
		S1.dFechaCreacion,
		S1.cFechaComite,
		S1.cIntegrantesSesion,
		S2.cCtaCod,
		S2.cCodCliente,
		S2.cNomCliente,
		S2.cProducto,
		S2.cTipoCredito,
		S2.cFechaDesembolso,
		S2.nSaldoCapitalOrigen,
		S2.cCampana,
		S2.nMontoDesembolsado,
		S2.cCuotaAtrasadaActa,
		S2.nDiasAtraso,
		S2.cEstadoCredito,
		S2.cAsesorOrigen,
		S2.cAsesorActual,
		S2.cNombreResponsable,
		S2.cMotivoInclusionRegla,
		S2.cComentarioInclusion,
		S2.nTotalObservaciones,
		CK.nOrden,
		CK.cCategoria,
		CK.cCodigo,
		CK.cObservacion,
		CK.cCumplimiento,
		CK.cDetalle,
		S2.cResolucionComite,
		S2.cOpinionRecuperaciones,
		S2.cSustentoRecuperaciones,
		S2.cAcuerdos,
		S2.cRecomendaciones
	FROM #TmpCreditoActa S2
	LEFT JOIN #TmpSesion S1 ON S1.nCredFallidoComiteId = S2.nCredFallidoComiteId
	LEFT JOIN #TmpAgencias AGF ON AGF.cAgeCod = S2.cAgeCod
	LEFT JOIN #TmpChecklistCat CK ON CK.nCredFallidoComiteDetalleId = S2.nCredFallidoComiteDetalleId
END