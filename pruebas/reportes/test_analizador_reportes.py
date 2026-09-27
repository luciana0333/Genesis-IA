import unittest

from app.analizadores.analizador_reportes import verificar_reporte


class TestAnalizadorReportes(unittest.TestCase):
    def test_tabla_fisica_requiere_nolock_y_temporal_no_debe_usarlo(self):
        sql = """
        CREATE TABLE #Tmp (cNombre VARCHAR(50));
        SELECT cNombre FROM dbo.Cliente;
        SELECT cNombre FROM #Tmp WITH(NOLOCK);
        """
        reglas = [hallazgo.regla for hallazgo in verificar_reporte(sql)]

        self.assertIn("TABLA_FISICA_SIN_NOLOCK", reglas)
        self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", reglas)
        self.assertIn("TEMPORAL_TEXTO_SIN_COLLATE", reglas)

    def test_agrupa_tablas_fisicas_sin_nolock(self):
        sql = """
        SELECT cNombre FROM dbo.Cliente;
        SELECT cNombre FROM dbo.Persona;
        SELECT cNombre FROM DBCMACICA.dbo.Agencias;
        """

        hallazgos = [
            hallazgo for hallazgo in verificar_reporte(sql)
            if hallazgo.regla == "TABLA_FISICA_SIN_NOLOCK"
        ]

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("3 observaciones", hallazgos[0].mensaje)
        self.assertIn("líneas 2, 3, 4", hallazgos[0].mensaje)
        self.assertIn("dbo.Cliente", hallazgos[0].mensaje)
        self.assertIn("dbo.Persona", hallazgos[0].mensaje)
        self.assertIn("DBCMACICA.dbo.Agencias", hallazgos[0].mensaje)

    def test_agrupa_cualquier_regla_repetida(self):
        sql = """
        SELECT * FROM dbo.Cliente WITH(NOLOCK);
        SELECT * FROM dbo.Persona WITH(NOLOCK);
        SELECT * FROM dbo.Agencias WITH(NOLOCK);
        """

        hallazgos = [
            hallazgo for hallazgo in verificar_reporte(sql)
            if hallazgo.regla == "SELECT_ESTRELLA_PROHIBIDO"
        ]

        self.assertEqual(len(hallazgos), 1)
        self.assertIn("3 observaciones", hallazgos[0].mensaje)
        self.assertIn("líneas 2, 3, 4", hallazgos[0].mensaje)

    def test_temporal_texto_con_collate_y_tabla_fisica_con_nolock(self):
        sql = """
        CREATE TABLE #Tmp (cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS);
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK);
        SELECT cNombre FROM #Tmp;
        """

        self.assertEqual(verificar_reporte(sql), [])

    def test_prohibe_select_into_select_estrellay_in_unitario(self):
        sql = """
        SELECT * INTO #Tmp FROM dbo.Cliente WITH(NOLOCK);
        SELECT * FROM dbo.Cliente WITH(NOLOCK) WHERE nTipo IN (30);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_reporte(sql)}

        self.assertIn("SELECT_INTO_PROHIBIDO", reglas)
        self.assertIn("SELECT_ESTRELLA_PROHIBIDO", reglas)
        self.assertIn("IN_CON_UN_SOLO_VALOR", reglas)

    def test_no_confunde_select_con_insert_into_de_otra_sentencia(self):
        sql = """
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK);
        INSERT INTO #Tmp (cNombre)
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK);
        """

        reglas = [hallazgo.regla for hallazgo in verificar_reporte(sql)]
        self.assertNotIn("SELECT_INTO_PROHIBIDO", reglas)

    def test_detecta_select_into_en_la_misma_sentencia(self):
        sql = "SELECT cNombre INTO #Tmp FROM dbo.Cliente WITH(NOLOCK);"

        reglas = [hallazgo.regla for hallazgo in verificar_reporte(sql)]
        self.assertIn("SELECT_INTO_PROHIBIDO", reglas)

    def test_prohibe_hints_catalogos_y_modificaciones_fisicas(self):
        sql = """
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK, FORCESEEK)
        WHERE EXISTS (SELECT 1 FROM sys.objects);
        UPDATE dbo.Cliente SET cNombre = 'x';
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK) OPTION(RECOMPILE);
        """
        reglas = {hallazgo.regla for hallazgo in verificar_reporte(sql)}

        self.assertIn("HINT_PLAN_PROHIBIDO", reglas)
        self.assertIn("CATALOGO_SISTEMA_PROHIBIDO", reglas)
        self.assertIn("MODIFICACION_TABLA_FISICA", reglas)

    def test_from_de_update_no_exige_nolock_pero_update_fisico_se_prohibe(self):
        sql = """
        UPDATE dbo.Cliente
        SET cNombre = C.cNombre
        FROM #Tmp T
        INNER JOIN dbo.Cliente C ON C.nId = T.nId;
        """
        reglas = {hallazgo.regla for hallazgo in verificar_reporte(sql)}

        self.assertNotIn("TABLA_FISICA_SIN_NOLOCK", reglas)
        self.assertIn("MODIFICACION_TABLA_FISICA", reglas)

    def test_variable_declarada_debe_usarse(self):
        sql = """
        DECLARE @nNoUsada INT;
        DECLARE @nUsada INT = 1;
        SELECT @nUsada AS nValor FROM dbo.Cliente WITH(NOLOCK);
        """
        reglas = [hallazgo.regla for hallazgo in verificar_reporte(sql)]

        self.assertEqual(reglas.count("VARIABLE_DECLARADA_SIN_USO"), 1)

    def test_detecta_codigo_sql_comentado_sin_marcar_encabezado(self):
        sql = """
        /* Propósito: reporte de clientes */
        -- SELECT cNombre FROM dbo.Cliente;
        SELECT cNombre FROM dbo.Cliente WITH(NOLOCK);
        """

        reglas = [hallazgo.regla for hallazgo in verificar_reporte(sql)]
        self.assertEqual(reglas, ["CODIGO_SQL_COMENTADO"])

    def test_prohibe_sql_dinamico_y_varchar_max(self):
        sql = """
        DECLARE @sql VARCHAR(MAX) = 'SELECT 1 FROM sys.objects';
        EXEC sp_executesql @sql;
        """
        reglas = {hallazgo.regla for hallazgo in verificar_reporte(sql)}

        self.assertIn("CATALOGO_SISTEMA_PROHIBIDO", reglas)
        self.assertIn("SQL_DINAMICO_PROHIBIDO", reglas)
        self.assertIn("VARCHAR_MAX_PROHIBIDO", reglas)

    def test_identifica_varbinary_para_documentos(self):
        reglas = {
            hallazgo.regla
            for hallazgo in verificar_reporte("DECLARE @documento VARBINARY(MAX);")
        }

        self.assertIn("VARBINARY_DOCUMENTO_IDENTIFICADO", reglas)
        self.assertNotIn("VARCHAR_MAX_PROHIBIDO", reglas)


    def test_while_solo_se_observa_al_crear_el_procedimiento(self):
        cuerpo = "AS BEGIN DECLARE @i INT = 0; WHILE @i < 3 SET @i = @i + 1; END"
        crear = [h for h in verificar_reporte(f"CREATE PROCEDURE dbo.R {cuerpo}") if h.regla == "WHILE_PROHIBIDO"]
        self.assertEqual(len(crear), 1)
        self.assertEqual(crear[0].severidad.value, "alto")
        alterar = {h.regla for h in verificar_reporte(f"ALTER PROCEDURE dbo.R {cuerpo}")}
        self.assertNotIn("WHILE_PROHIBIDO", alterar)

    def test_varchar_max_permitido_para_json_o_xml(self):
        casos_permitidos = [
            "DECLARE @cJson NVARCHAR(MAX);",
            "DECLARE @datos NVARCHAR(MAX); SET @datos = (SELECT a FROM #T FOR JSON PATH);",
            "DECLARE @d VARCHAR(MAX); SELECT * FROM OPENJSON(@d);",
            "DECLARE @d VARCHAR(MAX); SELECT CAST(@d AS XML);",
            "SELECT CAST((SELECT a FROM #T FOR XML PATH('')) AS VARCHAR(MAX));",
        ]
        for sql in casos_permitidos:
            with self.subTest(sql=sql):
                self.assertNotIn("VARCHAR_MAX_PROHIBIDO", {h.regla for h in verificar_reporte(sql)})
        observado = [h for h in verificar_reporte("DECLARE @cNombre VARCHAR(MAX);") if h.regla == "VARCHAR_MAX_PROHIBIDO"]
        self.assertEqual(len(observado), 1)
        self.assertIn("@cNombre", observado[0].mensaje)

    def test_recomienda_throw_y_prohibe_waitfor(self):
        sql = "RAISERROR('Error', 16, 1); WAITFOR DELAY '00:00:01';"
        hallazgos = {h.regla: h for h in verificar_reporte(sql)}
        self.assertEqual(hallazgos["RAISERROR_USAR_THROW"].severidad.value, "medio")
        self.assertIn("THROW", hallazgos["RAISERROR_USAR_THROW"].mensaje)
        self.assertEqual(hallazgos["WAITFOR_DELAY_PROHIBIDO"].severidad.value, "alto")

    def test_severidad_sale_del_catalogo(self):
        hallazgos = {h.regla: h for h in verificar_reporte("UPDATE dbo.Cliente SET a = 1; DECLARE @doc VARBINARY(MAX);")}
        self.assertEqual(hallazgos["MODIFICACION_TABLA_FISICA"].severidad.value, "critico")
        self.assertEqual(hallazgos["VARBINARY_DOCUMENTO_IDENTIFICADO"].severidad.value, "bajo")


    def test_exige_esquema_al_consultar_otra_base(self):
        sql = """
        SELECT a.cNombre
        FROM dbo.Cliente c WITH(NOLOCK)
        INNER JOIN DBCMACICA..Agencias a WITH(NOLOCK) ON a.nAgenciaId = c.nAgenciaId
        INNER JOIN [DBCMACICA] . . [Zonas] z WITH(NOLOCK) ON z.nZonaId = a.nZonaId
        """
        hallazgos = verificar_reporte(sql)
        omitidos = [h for h in hallazgos if h.regla == "ESQUEMA_OMITIDO_ENTRE_BASES"]
        self.assertEqual(len(omitidos), 1)
        self.assertIn("DBCMACICA.dbo.Agencias", omitidos[0].mensaje)
        self.assertIn("2 observaciones", omitidos[0].mensaje)

    def test_referencia_completa_entre_bases_es_valida(self):
        sql = "SELECT a.cNombre FROM DBCMACICA.dbo.Agencias a WITH(NOLOCK)"
        self.assertNotIn("ESQUEMA_OMITIDO_ENTRE_BASES", {h.regla for h in verificar_reporte(sql)})


    def test_nolock_con_alias_es_valido(self):
        casos = [
            "SELECT c.cNombre FROM dbo.TB_Clientes c WITH(NOLOCK)",
            "SELECT c.cNombre FROM dbo.TB_Clientes AS c WITH (NOLOCK)",
            "SELECT c.cNombre FROM dbo.TB_Cuentas a WITH(NOLOCK) INNER JOIN dbo.TB_Clientes c WITH(NOLOCK) ON c.nId = a.nId",
            "SELECT c.cNombre FROM dbo.TB_Clientes c (NOLOCK)",
        ]
        for sql in casos:
            with self.subTest(sql=sql):
                self.assertNotIn("TABLA_FISICA_SIN_NOLOCK", {h.regla for h in verificar_reporte(sql)})

    def test_alias_sin_nolock_se_observa(self):
        sql = "SELECT c.cNombre FROM dbo.TB_Clientes c INNER JOIN dbo.TB_Cuentas a ON a.nId = c.nId WHERE c.nId = 1"
        hallazgos = [h for h in verificar_reporte(sql) if h.regla == "TABLA_FISICA_SIN_NOLOCK"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("2 observaciones", hallazgos[0].mensaje)

    def test_cte_no_exige_nolock_y_temporal_con_alias_no_debe_usarlo(self):
        cte = "WITH Base AS (SELECT a FROM dbo.T WITH(NOLOCK)) SELECT b.a FROM Base b"
        self.assertNotIn("TABLA_FISICA_SIN_NOLOCK", {h.regla for h in verificar_reporte(cte)})
        temporal = "SELECT t.a FROM #Temp t WITH(NOLOCK)"
        self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", {h.regla for h in verificar_reporte(temporal)})


    def test_order_by_por_posicion(self):
        casos = {
            "SELECT cNombre, dFecha FROM #T ORDER BY 1, 2": "ORDER BY 1, 2",
            "SELECT cNombre, dFecha FROM #T ORDER BY cNombre, 2 DESC;": "ORDER BY 2",
        }
        for sql, texto in casos.items():
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_reporte(sql) if h.regla == "ORDER_BY_NUMERICO_PROHIBIDO"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(texto, hallazgos[0].mensaje)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
        valido = "SELECT cNombre FROM #T ORDER BY cNombre DESC, dFecha"
        self.assertNotIn("ORDER_BY_NUMERICO_PROHIBIDO", {h.regla for h in verificar_reporte(valido)})


    def test_comandos_que_le_dicen_al_motor_que_hacer(self):
        casos = ["DBCC FREEPROCCACHE;", "SELECT a FROM #T OPTION (MAXDOP 1);", "SELECT a FROM dbo.T WITH(NOLOCK, FORCESEEK)"]
        for sql in casos:
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_reporte(sql) if h.regla == "HINT_PLAN_PROHIBIDO"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("No está permitido emplear sintaxis que fuerce al motor", hallazgos[0].mensaje)

    def test_collate_en_where_y_join(self):
        where = "SELECT Nombre FROM #T WHERE Nombre COLLATE SQL_Latin1_General_CP1_CI_AS = 'Juan';"
        join = "SELECT a.x FROM #A a INNER JOIN #B b ON a.c COLLATE SQL_Latin1_General_CP1_CI_AS = b.c;"
        for sql, texto in ((where, "del WHERE"), (join, "del JOIN")):
            with self.subTest(sql=sql):
                hallazgos = [h for h in verificar_reporte(sql) if h.regla == "COLLATE_EN_PREDICADO"]
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(texto, hallazgos[0].mensaje)
        creacion = "CREATE TABLE #T (cNombre VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL);"
        self.assertNotIn("COLLATE_EN_PREDICADO", {h.regla for h in verificar_reporte(creacion)})

    def test_recomienda_trim_string_agg_y_string_split(self):
        sql = """
        SELECT LTRIM(RTRIM(Calif0)) FROM #T;
        SELECT STUFF((SELECT ',' + Nombre FROM #E FOR XML PATH(''), TYPE).value('.', 'NVARCHAR(MAX)'), 1, 1, '') AS Lista;
        SELECT items FROM dbo.fn_Split('Juan,Pedro', ',');
        """
        hallazgos = {h.regla: h for h in verificar_reporte(sql)}
        self.assertIn("TRIM", hallazgos["LTRIM_RTRIM_PROHIBIDO"].mensaje)
        self.assertIn("FOR XML PATH y STUFF", hallazgos["STUFF_FOR_XML_PATH_PROHIBIDO"].mensaje)
        self.assertIn("STRING_SPLIT", hallazgos["FN_SPLIT_PROHIBIDO"].mensaje)
        for regla in ("LTRIM_RTRIM_PROHIBIDO", "STUFF_FOR_XML_PATH_PROHIBIDO", "FN_SPLIT_PROHIBIDO"):
            self.assertEqual(hallazgos[regla].severidad.value, "medio")

    def test_funciones_nativas_no_generan_hallazgo(self):
        sql = """
        SELECT TRIM(Calif0) FROM #T;
        SELECT STRING_AGG(Nombre, ',') FROM #E;
        SELECT value FROM STRING_SPLIT('Juan,Pedro', ',');
        """
        reglas = {h.regla for h in verificar_reporte(sql)}
        for regla in ("LTRIM_RTRIM_PROHIBIDO", "STUFF_FOR_XML_PATH_PROHIBIDO", "FN_SPLIT_PROHIBIDO"):
            self.assertNotIn(regla, reglas)


if __name__ == "__main__":
    unittest.main()