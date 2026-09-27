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

    def test_identifica_varbinary_para_documentos(self):
        reglas = {
            hallazgo.regla
            for hallazgo in verificar_procedimiento_normal("DECLARE @documento VARBINARY(MAX);")
        }

        self.assertIn("VARBINARY_DOCUMENTO_IDENTIFICADO", reglas)
        self.assertNotIn("VARCHAR_MAX_PROHIBIDO", reglas)


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
            "SELECT * FROM #T ORDER BY 1; DECLARE @doc VARBINARY(MAX);")}
        self.assertEqual(hallazgos["SELECT_ESTRELLA_PROHIBIDO"], "medio")
        self.assertEqual(hallazgos["ORDER_BY_NUMERICO_PROHIBIDO"], "medio")
        self.assertEqual(hallazgos["VARBINARY_DOCUMENTO_IDENTIFICADO"], "bajo")


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

if __name__ == "__main__":
    unittest.main()