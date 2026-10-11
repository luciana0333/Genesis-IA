import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal


class TestAnalizadorProcedimientosNormales(unittest.TestCase):
    def test_detecta_control_flujo_y_hints(self):
        sql = """
        WHILE @nEstado = 1 BEGIN SELECT 1 END;
        GOTO Salir;
        MERGE dbo.Cliente AS C USING #Tmp AS T ON C.nId = T.nId;
        SELECT cNombre FROM dbo.Cliente WITH(FORCESEEK) OPTION(RECOMPILE);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertTrue({"WHILE_PROHIBIDO", "GOTO_PROHIBIDO", "MERGE_PROHIBIDO"}.issubset(reglas))
        self.assertIn("HINT_PLAN_PROHIBIDO", reglas)

    def test_temporal_no_nolock_y_collate_en_texto(self):
        sql = """
        CREATE TABLE #Tmp (
            cNombre VARCHAR(100),
            nId INT
        );
        SELECT cNombre FROM #Tmp WITH(NOLOCK);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", reglas)
        self.assertIn("TEMPORAL_TEXTO_SIN_COLLATE", reglas)

    def test_detecta_select_into_select_estrellay_funciones_obsoletas(self):
        sql = """
        SELECT * INTO #Tmp FROM dbo.Cliente;
        SELECT STUFF((SELECT ',' + cNombre FROM dbo.Cliente FOR XML PATH('')), 1, 1, '');
        SELECT value FROM dbo.FN_SPLIT(@cValores, ',');
        SELECT LTRIM(RTRIM(cNombre)) FROM dbo.Cliente;
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertIn("SELECT_INTO_PROHIBIDO", reglas)
        self.assertIn("SELECT_ESTRELLA_PROHIBIDO", reglas)
        self.assertIn("STUFF_FOR_XML_PATH_PROHIBIDO", reglas)
        self.assertIn("FN_SPLIT_PROHIBIDO", reglas)
        self.assertIn("LTRIM_RTRIM_PROHIBIDO", reglas)

    def test_collate_en_predicado_y_variable_sin_uso_y_comentario(self):
        sql = """
        -- SELECT * FROM dbo.Cliente;
        DECLARE @nNoUsada INT;
        SELECT cNombre FROM dbo.Cliente
        WHERE cNombre COLLATE SQL_Latin1_General_CP1_CI_AS = 'A';
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertIn("COLLATE_EN_PREDICADO", reglas)
        self.assertIn("VARIABLE_DECLARADA_SIN_USO", reglas)
        self.assertIn("CODIGO_SQL_COMENTADO", reglas)

    def test_reglas_nuevas_para_nolock_order_by_option_y_cast_en_join(self):
        sql = """
        CREATE TABLE #Tmp (
            cNombre VARCHAR(100) COLLATE SQL_Latin1_General_CP1_CI_AS,
            nId INT
        );

        SELECT cNombre
        FROM dbo.Cliente AS c WITH(NOLOCK)
        JOIN #Tmp AS t WITH(NOLOCK) ON CAST(c.nId AS INT) = t.nId
        ORDER BY 1;

        UPDATE c
        SET c.cNombre = 'X'
        FROM dbo.Cliente AS c WITH(NOLOCK)
        JOIN dbo.Detalle AS d ON d.nClienteId = CAST(c.nId AS INT)
        WHERE c.nId = 1
        OPTION (RECOMPILE);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", reglas)
        self.assertIn("NOLOCK_EN_TABLA_FISICA", reglas)
        self.assertIn("HINT_PLAN_PROHIBIDO", reglas)
        self.assertIn("ORDER_BY_NUMERICO_PROHIBIDO", reglas)
        self.assertIn("CAST_EN_JOIN_PROHIBIDO", reglas)

    def test_prohibe_catalogo_sistema_sql_dinamico_y_varchar_max(self):
        sql = """
        DECLARE @sql VARCHAR(MAX) = 'SELECT 1 FROM sys.objects';
        EXEC(@sql);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_procedimiento_normal(sql)}

        self.assertEqual(
            reglas & {"CATALOGO_SISTEMA_PROHIBIDO", "SQL_DINAMICO_PROHIBIDO", "VARCHAR_MAX_PROHIBIDO"},
            {"CATALOGO_SISTEMA_PROHIBIDO", "SQL_DINAMICO_PROHIBIDO", "VARCHAR_MAX_PROHIBIDO"},
        )

    def test_select_into_tras_begin_o_sin_punto_y_coma(self):
        tras_begin = "CREATE PROCEDURE dbo.PA_C_Sel\nAS\nBEGIN\n    SELECT c.n INTO #T FROM dbo.Cliente c;\nEND"
        self.assertIn(("SELECT_INTO_PROHIBIDO", 4), [(h.regla, h.linea) for h in verificar_procedimiento_normal(tras_begin)])
        sin_punto_y_coma = "DECLARE @x INT = 1\nSELECT c.n INTO #T FROM dbo.Cliente c WHERE c.n = @x"
        self.assertIn(("SELECT_INTO_PROHIBIDO", 2), [(h.regla, h.linea) for h in verificar_procedimiento_normal(sin_punto_y_coma)])
        for valido in ("INSERT INTO #T (n) SELECT c.n FROM dbo.Cliente c;", "DECLARE @n INT; SELECT @n = c.n FROM dbo.Cliente c;"):
            with self.subTest(sql=valido):
                self.assertNotIn("SELECT_INTO_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(valido)})

    def test_select_estrella_sobre_base_sin_esquema(self):
        hallazgo = next(h for h in verificar_procedimiento_normal("SELECT * FROM DBCMAICA..Cliente c WHERE c.n = 1;")
                        if h.regla == "SELECT_ESTRELLA_PROHIBIDO")
        self.assertIn("sobre la tabla DBCMAICA..Cliente", hallazgo.mensaje)

    def test_texto_entre_comillas_no_se_revisa_como_codigo(self):
        sql = ("SELECT 'Revisar SELECT * FROM sys.objects' AS cNota, 'COLLATE Modern_Spanish_CI_AS' AS cOtra,\n"
               "       c.cNombre FROM dbo.Cliente c WHERE c.nClienteId = 1;")
        self.assertEqual([h.regla for h in verificar_procedimiento_normal(sql)], [])

    def test_codigo_comentado_se_sigue_detectando(self):
        sql = "-- SELECT * FROM dbo.Cliente\n/* UPDATE dbo.Cliente SET a = 1 */\nSELECT 'nota' AS cNota;"
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "CODIGO_SQL_COMENTADO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("2 observaciones", hallazgos[0].mensaje)

    def test_sql_dinamico_si_se_revisa(self):
        sql = "DECLARE @s NVARCHAR(400) = N'SELECT * FROM dbo.Cliente WITH (UPDLOCK)';\nEXEC sp_executesql @s;"
        reglas = {h.regla for h in verificar_procedimiento_normal(sql)}
        self.assertTrue({"SELECT_ESTRELLA_PROHIBIDO", "HINT_BLOQUEO_PROHIBIDO", "SQL_DINAMICO_PROHIBIDO"} <= reglas)

    def test_mensajes_que_muestran_textos(self):
        casos = {
            "SELECT 1 FROM dbo.Cliente c WHERE c.cEstado IN ('A');": "IN ('A')",
            "WAITFOR DELAY '00:00:05';": "WAITFOR DELAY '00:00:05'",
            "SELECT 1 FROM dbo.Cliente c WHERE LEFT(c.cCodigo, 3) = 'ABC';": "LIKE 'ABC%'",
        }
        for sql, esperado in casos.items():
            with self.subTest(sql=sql):
                self.assertIn(esperado, verificar_procedimiento_normal(sql)[0].mensaje)

    def test_indice_forzado(self):
        sql = (
            "SELECT V.nVentaId, C.cNombre\n    FROM dbo.Venta AS V\n"
            "    INNER JOIN dbo.Cliente AS C WITH (INDEX(IX_Cliente_nClienteId))\n        ON V.nClienteId = C.nClienteId;"
        )
        hallazgo = next(h for h in verificar_procedimiento_normal(sql) if h.regla == "HINT_PLAN_PROHIBIDO")
        self.assertEqual(hallazgo.linea, 3)
        self.assertIn("usar el índice IX_Cliente_nClienteId en la tabla dbo.Cliente", hallazgo.mensaje)
        igual = "SELECT c.n FROM dbo.Cliente c WITH (NOLOCK, INDEX = IX_Cliente);"
        self.assertIn("HINT_PLAN_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(igual)})
        crear = "CREATE INDEX IX_T ON #T (nId);"
        self.assertNotIn("HINT_PLAN_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(crear)})

    def test_collate_distinto_al_de_la_empresa(self):
        sql = "CREATE TABLE #T (cNombre VARCHAR(50) COLLATE Modern_Spanish_CI_AS);\nSELECT t.cNombre FROM #T t;"
        hallazgo = next(h for h in verificar_procedimiento_normal(sql) if h.regla == "COLLATE_DISTINTO_AL_ESTANDAR")
        self.assertEqual((hallazgo.linea, hallazgo.severidad.value), (1, "medio"))
        self.assertIn("COLLATE Modern_Spanish_CI_AS, distinto al que usa la empresa", hallazgo.mensaje)
        self.assertIn("validar si el COLLATE es el correcto", hallazgo.mensaje)

    def test_collate_database_default(self):
        sql = "CREATE TABLE #T (cNombre VARCHAR(50) COLLATE DATABASE_DEFAULT);\nSELECT t.cNombre FROM #T t;"
        reglas = {h.regla: h for h in verificar_procedimiento_normal(sql)}
        self.assertEqual(reglas["COLLATE_DATABASE_DEFAULT"].severidad.value, "alto")
        self.assertIn("COLLATE SQL_Latin1_General_CP1_CI_AS", reglas["COLLATE_DATABASE_DEFAULT"].mensaje)
        self.assertNotIn("COLLATE_DISTINTO_AL_ESTANDAR", reglas)

    def test_collate_de_la_empresa_es_valido(self):
        sql = "CREATE TABLE #T (cNombre VARCHAR(50) COLLATE sql_latin1_general_cp1_ci_as);\nSELECT t.cNombre FROM #T t;"
        reglas = {h.regla for h in verificar_procedimiento_normal(sql)}
        self.assertFalse(reglas & {"COLLATE_DISTINTO_AL_ESTANDAR", "COLLATE_DATABASE_DEFAULT"})

    def test_nolock_recomendado_en_tablas_de_movimientos_y_constantes(self):
        sql = "SELECT m.nMonto FROM dbo.CuentaMov m\nJOIN dbo.Constante k ON k.nId = m.nTipo\nJOIN dbo.MovimientoCaja c ON c.nId = m.nId;"
        hallazgo = next(h for h in verificar_procedimiento_normal(sql) if h.regla == "TABLA_PESADA_SIN_NOLOCK")
        self.assertEqual(hallazgo.severidad.value, "medio")
        for texto in ("tabla de movimientos dbo.CuentaMov, que es pesada",
                      "tabla de constantes dbo.Constante, que se consulta en casi todos los procesos",
                      "tabla de movimientos dbo.MovimientoCaja"):
            self.assertIn(texto, hallazgo.mensaje)

    def test_nolock_opcional_en_las_demas_tablas(self):
        casos = (
            "SELECT c.n FROM dbo.Cliente c;",  # tabla física común: NOLOCK opcional
            "SELECT 1 FROM dbo.ClienteMovil a JOIN dbo.Removedor b ON 1 = 1;",  # Movil no es Mov
            "SELECT m.n FROM dbo.CuentaMov m WITH(NOLOCK) JOIN dbo.Constante k (NOLOCK) ON k.n = m.n;",
            "UPDATE m SET m.nEstado = 1 FROM dbo.CuentaMov m WHERE m.nId = 1;",  # la tabla que se actualiza
            "DELETE FROM dbo.CuentaMov WHERE nId = 1;",
            "SELECT 1 FROM #Mov m;",
        )
        for sql in casos:
            with self.subTest(sql=sql):
                self.assertNotIn("TABLA_PESADA_SIN_NOLOCK", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_misma_columna_con_distinto_tipo_en_temporales(self):
        collate = "COLLATE SQL_Latin1_General_CP1_CI_AS"
        sql = (
            f"CREATE TABLE #Clientes (nId INT, cNombre VARCHAR(40) {collate});\n"
            f"CREATE TABLE #Resumen (nId INT, cNombre VARCHAR(30) {collate});\n"
            f"DECLARE @T TABLE (cNombre VARCHAR(40) {collate});\nSELECT t.cNombre FROM @T t;"
        )
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "TIPO_DISTINTO_ENTRE_TEMPORALES"]
        self.assertEqual([(h.linea, h.severidad.value) for h in hallazgos], [(2, "alto")])
        self.assertIn("cNombre es VARCHAR(30) en #Resumen, pero VARCHAR(40) en #Clientes (línea 1)", hallazgos[0].mensaje)

    def test_misma_columna_con_el_mismo_tipo_es_valida(self):
        sql = "CREATE TABLE #A (nId INT, nMonto DECIMAL(18, 2));\nCREATE TABLE #B (nId INT, nMonto DECIMAL(18,2));"
        self.assertNotIn("TIPO_DISTINTO_ENTRE_TEMPORALES", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_varchar_max_menciona_tablas_heredadas(self):
        hallazgo = next(h for h in verificar_procedimiento_normal("DECLARE @cSQL NVARCHAR(MAX);\nSELECT @cSQL;")
                        if h.regla == "VARCHAR_MAX_PROHIBIDO")
        self.assertIn("@cSQL se declara como NVARCHAR(MAX)", hallazgo.mensaje)
        self.assertIn("tabla heredada", hallazgo.mensaje)

    def test_hints_de_bloqueo(self):
        sql = "SELECT c.cNombre FROM dbo.Cliente c WITH (UPDLOCK, HOLDLOCK) WHERE c.nId = 1;"
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "HINT_BLOQUEO_PROHIBIDO"]
        self.assertEqual(len(hallazgos), 1)  # agrupados en un solo mensaje
        self.assertIn("'UPDLOCK', que bloquea las filas leídas", hallazgos[0].mensaje)
        self.assertIn("'HOLDLOCK', que mantiene bloqueadas", hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertNotIn("HINT_PLAN_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(sql)})
        self.assertNotIn("HINT_BLOQUEO_PROHIBIDO",
                         {h.regla for h in verificar_procedimiento_normal("SELECT c.n FROM dbo.Cliente c WITH (NOLOCK);")})

    def test_varbinary_solo_se_marca_si_guarda_documentos(self):
        declarado = {h.regla for h in verificar_procedimiento_normal("DECLARE @documento VARBINARY(MAX);")}
        self.assertNotIn("DOCUMENTO_GUARDADO_EN_BD", declarado)
        self.assertNotIn("VARCHAR_MAX_PROHIBIDO", declarado)
        consulta = "SELECT d.vArchivo FROM dbo.Documento d WHERE d.nId = 1;"
        self.assertNotIn("DOCUMENTO_GUARDADO_EN_BD", {h.regla for h in verificar_procedimiento_normal(consulta)})

        sql = (
            "CREATE PROCEDURE dbo.PA_Documento_Ins_Archivo\n    @nId INT,\n    @vArchivo VARBINARY(MAX)\nAS\nBEGIN\n"
            "    INSERT INTO dbo.Documento (nId, vArchivo)\n    VALUES (@nId, @vArchivo);\nEND"
        )
        hallazgo = next(h for h in verificar_procedimiento_normal(sql) if h.regla == "DOCUMENTO_GUARDADO_EN_BD")
        self.assertEqual((hallazgo.linea, hallazgo.severidad.value), (7, "alto"))
        self.assertIn("@vArchivo (VARBINARY) se escribe en la tabla dbo.Documento con INSERT", hallazgo.mensaje)

    def test_varbinary_otras_formas_de_guardar_documentos(self):
        casos = (
            "UPDATE d SET d.vArchivo = CONVERT(VARBINARY(MAX), @cBase64) FROM dbo.Documento d;",
            "INSERT INTO dbo.Documento (vArchivo) SELECT BulkColumn FROM OPENROWSET(BULK 'C:\\a.pdf', SINGLE_BLOB) x;",
            "CREATE TABLE dbo.Documento (nId INT NOT NULL, vArchivo VARBINARY(MAX) NOT NULL);",
            "ALTER TABLE dbo.Documento ADD vFirma VARBINARY(MAX) NULL;",
        )
        for sql in casos:
            with self.subTest(sql=sql):
                self.assertIn("DOCUMENTO_GUARDADO_EN_BD", {h.regla for h in verificar_procedimiento_normal(sql)})
        temporal = "DECLARE @v VARBINARY(MAX); CREATE TABLE #Doc (vArchivo VARBINARY(MAX)); INSERT INTO #Doc VALUES (@v);"
        self.assertNotIn("DOCUMENTO_GUARDADO_EN_BD", {h.regla for h in verificar_procedimiento_normal(temporal)})


    def test_nombre_correcto_al_crear(self):
        for nombre in ("dbo.PA_Cliente_Sel_PorDocumento", "dbo.PA_Cliente_Upd", "dbo.PA_Credito_Calcular_Interes"):
            with self.subTest(nombre=nombre):
                reglas = {h.regla for h in verificar_procedimiento_normal(f"CREATE PROCEDURE {nombre} AS SELECT 1")}
                self.assertFalse(reglas & {"PROCEDIMIENTO_SIN_ESQUEMA", "PROCEDIMIENTO_SIN_PREFIJO_PA",
                                           "PROCEDIMIENTO_NOMBRE_INCOMPLETO", "PROCEDIMIENTO_ACCION_NO_ABREVIADA"})

    def test_nomenclatura_al_crear(self):
        casos = {
            "CREATE PROCEDURE PA_Cliente_Sel AS SELECT 1": "PROCEDIMIENTO_SIN_ESQUEMA",
            "CREATE PROCEDURE dbo.sp_ClienteConsultar AS SELECT 1": "PROCEDIMIENTO_SIN_PREFIJO_PA",
            "CREATE PROCEDURE dbo.PA_Cliente AS SELECT 1": "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            "CREATE PROCEDURE dbo.PA_Cliente_Consultar AS SELECT 1": "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
        }
        for sql, regla in casos.items():
            with self.subTest(sql=sql):
                self.assertIn(regla, {h.regla for h in verificar_procedimiento_normal(sql)})
        accion = [h for h in verificar_procedimiento_normal("CREATE PROCEDURE dbo.PA_Cliente_Consultar_PorId AS SELECT 1")
                  if h.regla == "PROCEDIMIENTO_ACCION_NO_ABREVIADA"][0]
        self.assertIn("PA_Cliente_Sel_PorId", accion.mensaje)

    def test_en_alter_solo_se_exige_el_esquema(self):
        sin_esquema = {h.regla for h in verificar_procedimiento_normal("ALTER PROCEDURE sp_Viejo AS SELECT 1")}
        self.assertIn("PROCEDIMIENTO_SIN_ESQUEMA", sin_esquema)
        self.assertFalse(sin_esquema & {"PROCEDIMIENTO_SIN_PREFIJO_PA", "PROCEDIMIENTO_NOMBRE_INCOMPLETO"})
        con_esquema = {h.regla for h in verificar_procedimiento_normal("ALTER PROCEDURE dbo.sp_Viejo AS SELECT 1")}
        self.assertNotIn("PROCEDIMIENTO_SIN_ESQUEMA", con_esquema)


    def test_agrupa_hallazgos_del_mismo_tipo(self):
        sql = """ALTER PROCEDURE dbo.PA_Cliente_Upd AS
BEGIN
SELECT * FROM #T;
SELECT * FROM #U;
END"""
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "SELECT_ESTRELLA_PROHIBIDO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("2 observaciones", hallazgos[0].mensaje)
        self.assertIn("las líneas 3, 4", hallazgos[0].mensaje)


    def test_varchar_max_es_medio_y_se_permite_para_json_o_xml(self):
        observado = [h for h in verificar_procedimiento_normal("DECLARE @cNombre VARCHAR(MAX);")
                     if h.regla == "VARCHAR_MAX_PROHIBIDO"]
        self.assertEqual(len(observado), 1)
        self.assertEqual(observado[0].severidad.value, "medio")
        self.assertIn("no guarda JSON ni XML", observado[0].mensaje)
        for sql in ("DECLARE @cJson NVARCHAR(MAX);",
                    "DECLARE @d NVARCHAR(MAX); SET @d = (SELECT a FROM #T FOR JSON PATH);"):
            with self.subTest(sql=sql):
                self.assertNotIn("VARCHAR_MAX_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_severidades_salen_del_catalogo(self):
        hallazgos = {h.regla: h.severidad.value for h in verificar_procedimiento_normal(
            "SELECT * FROM #T ORDER BY 1; DECLARE @doc VARBINARY(MAX); INSERT INTO dbo.Doc (v) VALUES (@doc);")}
        self.assertEqual(hallazgos["SELECT_ESTRELLA_PROHIBIDO"], "alto")
        self.assertEqual(hallazgos["ORDER_BY_NUMERICO_PROHIBIDO"], "medio")
        self.assertEqual(hallazgos["DOCUMENTO_GUARDADO_EN_BD"], "alto")


    def test_nombre_en_minusculas_mayusculas_y_sin_accion(self):
        hallazgos = {h.regla: h.mensaje for h in verificar_procedimiento_normal(
            "CREATE PROCEDURE dbo.pa_CLIENTE_completo AS SELECT 1")}
        self.assertNotIn("PROCEDIMIENTO_SIN_PREFIJO_PA", hallazgos)
        self.assertIn("PA_Cliente_Sel_Completo", hallazgos["PROCEDIMIENTO_SIN_ACCION"])
        self.assertIn("CLIENTE → Cliente", hallazgos["PROCEDIMIENTO_NOMBRE_NO_PASCALCASE"])

    def test_verbo_personalizado_y_siglas_son_validos(self):
        for nombre in ("dbo.PA_Credito_Calcular_Interes", "dbo.PA_BI_Sel_Resumen", "dbo.PA_TipoCambio_Upd"):
            with self.subTest(nombre=nombre):
                reglas = {h.regla for h in verificar_procedimiento_normal(f"CREATE PROCEDURE {nombre} AS SELECT 1")}
                self.assertFalse({r for r in reglas if r.startswith("PROCEDIMIENTO_")})


    def test_los_mensajes_indican_el_objeto(self):
        sql = """ALTER PROCEDURE dbo.PA_Cliente_Upd AS
BEGIN
SELECT * FROM dbo.TB_Estado;
SELECT * FROM #TMP_Clientes t;
SELECT a.x FROM #A a INNER JOIN dbo.B b ON a.n = b.n WHERE a.cNombre COLLATE SQL_Latin1_General_CP1_CI_AS = 'x';
END"""
        hallazgos = {h.regla: h.mensaje for h in verificar_procedimiento_normal(sql)}
        self.assertIn("sobre la tabla dbo.TB_Estado", hallazgos["SELECT_ESTRELLA_PROHIBIDO"])
        self.assertIn("sobre la tabla #TMP_Clientes", hallazgos["SELECT_ESTRELLA_PROHIBIDO"])
        self.assertIn("sobre a.cNombre en la condición del WHERE", hallazgos["COLLATE_EN_PREDICADO"])

    def test_collate_en_temporales_y_variables_de_tabla(self):
        correcto = "CREATE TABLE #T (cA VARCHAR(10) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL, nB INT)"
        self.assertNotIn("TEMPORAL_TEXTO_SIN_COLLATE", {h.regla for h in verificar_procedimiento_normal(correcto)})
        sin_collate = "CREATE TABLE #T (cA VARCHAR(10), cB NVARCHAR(20), nC INT); DECLARE @V TABLE (cD CHAR(1))"
        hallazgo = [h for h in verificar_procedimiento_normal(sin_collate) if h.regla == "TEMPORAL_TEXTO_SIN_COLLATE"][0]
        for columna in ("cA", "cB", "cD"):
            self.assertIn(columna, hallazgo.mensaje)
        self.assertIn("variable de tabla @V", hallazgo.mensaje)

    def test_goto_y_merge_son_medios_y_piden_validar(self):
        hallazgos = {h.regla: h for h in verificar_procedimiento_normal(
            "GOTO Fin; MERGE dbo.A AS t USING #B s ON t.n = s.n WHEN MATCHED THEN DELETE;")}
        for regla in ("GOTO_PROHIBIDO", "MERGE_PROHIBIDO"):
            self.assertEqual(hallazgos[regla].severidad.value, "medio")
            self.assertIn("validar si su uso está justificado", hallazgos[regla].mensaje)

    def test_while_se_observa_en_create_y_en_alter(self):
        for verbo in ("CREATE", "ALTER"):
            sql = f"{verbo} PROCEDURE dbo.PA_Cliente_Upd AS BEGIN WHILE 1 = 1 BREAK; END"
            self.assertIn("WHILE_PROHIBIDO", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_waitfor_esquema_omitido_y_convert_en_join(self):
        reglas = {h.regla for h in verificar_procedimiento_normal(
            "WAITFOR DELAY '00:00:01'; SELECT a.x FROM DBCMACICA..Agencias a; "
            "SELECT a.x FROM #A a JOIN #B b ON CONVERT(INT, a.n) = b.n;")}
        self.assertTrue({"WAITFOR_DELAY_PROHIBIDO", "ESQUEMA_OMITIDO_ENTRE_BASES", "CAST_EN_JOIN_PROHIBIDO"} <= reglas)

    def test_tabla_consultada_mas_de_tres_veces(self):
        sql = """SELECT c1.x FROM dbo.Cliente c1
JOIN dbo.Cliente c2 ON c2.n = c1.n
JOIN [dbo].[Cliente] c3 ON c3.n = c1.n
JOIN Cliente c4 ON c4.n = c1.n;"""
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "TABLA_REPETIDA_EN_CONSULTA"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("4 veces", hallazgos[0].mensaje)
        tres = "SELECT c1.x FROM dbo.Cliente c1 JOIN dbo.Cliente c2 ON c2.n = c1.n JOIN dbo.Cliente c3 ON c3.n = c1.n;"
        self.assertNotIn("TABLA_REPETIDA_EN_CONSULTA", {h.regla for h in verificar_procedimiento_normal(tres)})

    def test_recomienda_throw_en_lugar_de_raiserror(self):
        hallazgo = [h for h in verificar_procedimiento_normal("RAISERROR('Error', 16, 1);")
                    if h.regla == "RAISERROR_USAR_THROW"][0]
        self.assertEqual(hallazgo.severidad.value, "medio")
        self.assertIn("THROW", hallazgo.mensaje)

    def test_consultas_seguidas_sin_punto_y_coma_no_se_suman(self):
        sql = """ALTER PROCEDURE dbo.PA_X_Sel AS
BEGIN
    SELECT a FROM dbo.TB_Tabla WHERE n = 1
    SELECT b FROM dbo.TB_Tabla WHERE n = 2
    SELECT c FROM dbo.TB_Tabla WHERE n = 3
    SELECT d FROM dbo.TB_Tabla WHERE n = 4
END"""
        self.assertNotIn("TABLA_REPETIDA_EN_CONSULTA", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_in_con_un_solo_valor(self):
        casos = {
            "SELECT a FROM #T WHERE cCodigo IN ('34')": "cCodigo = '34'",
            "SELECT a FROM #T WHERE nEstado IN (1)": "nEstado = 1",
            "SELECT a FROM #T WHERE nEstado NOT IN (@nEstado)": "nEstado <> @nEstado",
        }
        for sql, sugerencia in casos.items():
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "IN_CON_UN_SOLO_VALOR"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(sugerencia, hallazgos[0].mensaje)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
        for sql in ("SELECT a FROM #T WHERE cCodigo IN ('34', '35')",
                    "SELECT a FROM #T WHERE nId IN (SELECT nId FROM #U)"):
            with self.subTest(sql=sql):
                self.assertNotIn("IN_CON_UN_SOLO_VALOR", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_left_en_condicion_sugiere_like(self):
        casos = {
            "SELECT a FROM #T WHERE LEFT(cCodigo, 3) = 'ABC'": "cCodigo LIKE 'ABC%'",
            "SELECT a FROM #A a JOIN #B b ON LEFT(a.cCuenta, 4) = @cPrefijo": "a.cCuenta LIKE @cPrefijo + '%'",
        }
        for sql, sugerencia in casos.items():
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "LEFT_REEMPLAZABLE_POR_LIKE"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(sugerencia, hallazgos[0].mensaje)
        en_select = "SELECT LEFT(cNombre, 10) AS cCorto FROM #T LEFT JOIN #U u ON u.n = 1"
        self.assertNotIn("LEFT_REEMPLAZABLE_POR_LIKE", {h.regla for h in verificar_procedimiento_normal(en_select)})

    def test_replace_anidados_sugieren_translate(self):
        sql = "SELECT REPLACE(REPLACE(REPLACE(cTelefono, '-', ''), '(', ''), ')', '') FROM #T"
        hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "REPLACE_ANIDADO_TRANSLATE"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("3 REPLACE anidados", hallazgos[0].mensaje)
        self.assertIn("REPLACE(TRANSLATE(cTelefono, '-()', '|||'), '|', '')", hallazgos[0].mensaje)
        exacto = "SELECT REPLACE(REPLACE(REPLACE(cTexto, 'á', 'a'), 'é', 'e'), 'í', 'i') FROM #T"
        mensaje = [h.mensaje for h in verificar_procedimiento_normal(exacto) if h.regla == "REPLACE_ANIDADO_TRANSLATE"][0]
        self.assertIn("TRANSLATE(cTexto, 'áéí', 'aei')", mensaje)
        dos = "SELECT REPLACE(REPLACE(cTexto, 'a', 'b'), 'c', 'd') FROM #T"
        self.assertNotIn("REPLACE_ANIDADO_TRANSLATE", {h.regla for h in verificar_procedimiento_normal(dos)})

    def test_transaccion_sin_commit(self):
        sin_commit = "BEGIN TRAN; UPDATE dbo.Cliente SET a = 1;"
        hallazgo = [h for h in verificar_procedimiento_normal(sin_commit) if h.regla == "TRANSACCION_SIN_COMMIT"]
        self.assertEqual(len(hallazgo), 1)
        self.assertEqual(hallazgo[0].severidad.value, "alto")
        faltante = "BEGIN TRAN; UPDATE dbo.A SET a = 1; COMMIT; BEGIN TRANSACTION; UPDATE dbo.B SET b = 1;"
        self.assertIn("solo 1 COMMIT para 2", [h.mensaje for h in verificar_procedimiento_normal(faltante)
                                                if h.regla == "TRANSACCION_SIN_COMMIT"][0])
        correcta = """BEGIN TRY
    BEGIN TRANSACTION
    UPDATE dbo.Cliente SET a = 1
    COMMIT TRANSACTION
END TRY
BEGIN CATCH
    ROLLBACK TRANSACTION
END CATCH"""
        self.assertNotIn("TRANSACCION_SIN_COMMIT", {h.regla for h in verificar_procedimiento_normal(correcta)})

    def test_nolock_en_fisicas_es_opcional_y_en_temporales_no(self):
        for sql in ("SELECT a FROM dbo.Cliente c", "SELECT a FROM dbo.Cliente c WITH(NOLOCK)",
                    "SELECT t.a FROM #T t JOIN dbo.Cliente c WITH(NOLOCK) ON c.n = t.n"):
            with self.subTest(sql=sql):
                self.assertNotIn("NOLOCK_EN_TABLA_TEMPORAL", {h.regla for h in verificar_procedimiento_normal(sql)})
        for sql in ("SELECT t.a FROM #T t WITH(NOLOCK)", "SELECT a FROM @T v WITH (NOLOCK)"):
            with self.subTest(sql=sql):
                self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_nolock_solo_en_la_tabla_que_se_actualiza(self):
        avisa = {
            "UPDATE c SET c.a = 1 FROM dbo.Cliente c WITH(NOLOCK) JOIN dbo.Zona z ON z.n = c.n": "dbo.Cliente",
            "UPDATE c SET c.a = 1 FROM dbo.Zona z JOIN dbo.Cliente c WITH(NOLOCK) ON z.n = c.n": "dbo.Cliente",
            "UPDATE dbo.Cliente WITH(NOLOCK) SET a = 1": "dbo.Cliente",
        }
        for sql, tabla in avisa.items():
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_procedimiento_normal(sql) if h.regla == "NOLOCK_EN_TABLA_FISICA"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(f"la tabla {tabla}, que es la que se actualiza", hallazgos[0].mensaje)
        for sql in ("UPDATE c SET c.a = 1 FROM dbo.Cliente c JOIN dbo.Zona z WITH(NOLOCK) ON z.n = c.n",
                    "UPDATE t SET t.a = 1 FROM #T t WITH(NOLOCK)",
                    "SELECT a FROM dbo.Cliente c WITH(NOLOCK)"):
            with self.subTest(sql=sql):
                self.assertNotIn("NOLOCK_EN_TABLA_FISICA", {h.regla for h in verificar_procedimiento_normal(sql)})

    def test_envio_de_correo_es_critico(self):
        sql = "EXEC msdb.dbo.sp_send_dbmail @profile_name = 'Avisos', @recipients = 'a@b.com'"
        hallazgo = [h for h in verificar_procedimiento_normal(sql) if h.regla == "ENVIO_CORREO_DESDE_BD"]
        self.assertEqual(len(hallazgo), 1)
        self.assertEqual(hallazgo[0].severidad.value, "critico")
        self.assertIn("msdb.dbo.sp_send_dbmail", hallazgo[0].mensaje)

    def test_accion_pegada_a_la_finalidad(self):
        casos = {
            "PA_Registro_SelEjecucionesDetalle": "PA_Registro_Sel_EjecucionesDetalle",
            "PA_Cliente_ConsultarDatos": "PA_Cliente_Sel_Datos",
        }
        for nombre, sugerido in casos.items():
            with self.subTest(nombre=nombre):
                hallazgos = [h for h in verificar_procedimiento_normal(f"CREATE PROCEDURE dbo.{nombre} AS SELECT a FROM #T")
                             if h.regla == "PROCEDIMIENTO_ACCION_SIN_SEPARAR"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(sugerido, hallazgos[0].mensaje)
        correcto = "CREATE PROCEDURE dbo.PA_Registro_Sel_EjecucionesDetalle AS SELECT a FROM #T"
        self.assertNotIn("PROCEDIMIENTO_ACCION_SIN_SEPARAR", {h.regla for h in verificar_procedimiento_normal(correcto)})

    def test_linea_es_la_del_elemento_que_causa_el_hallazgo(self):
        previo = "ALTER PROCEDURE dbo.PA_Cliente_Sel AS\nBEGIN\nDECLARE @n INT = 1;\n"
        casos = [
            ("SELECT_INTO_PROHIBIDO", "SELECT a FROM #T WHERE n = @n;\nSELECT a\nINTO #Y\nFROM #T;", 5),
            ("STUFF_FOR_XML_PATH_PROHIBIDO", "SELECT STUFF((SELECT ',' + c FROM #T\nFOR XML PATH('')), 1, 1, '');", 4),
            ("COLLATE_EN_PREDICADO", "SELECT a FROM #T\nWHERE n = @n\n  AND c COLLATE SQL_Latin1_General_CP1_CI_AS = 'x';", 6),
            ("CAST_EN_JOIN_PROHIBIDO", "SELECT a FROM #A a\nJOIN #B b\n  ON CAST(a.n AS INT) = b.n;", 6),
        ]
        for regla, cuerpo, esperada in casos:
            with self.subTest(regla=regla):
                hallazgos = [h for h in verificar_procedimiento_normal(previo + cuerpo + "\nEND") if h.regla == regla]
                self.assertTrue(hallazgos)
                self.assertEqual(hallazgos[0].linea, esperada)

if __name__ == "__main__":
    unittest.main()