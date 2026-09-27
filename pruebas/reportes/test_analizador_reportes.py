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


if __name__ == "__main__":
    unittest.main()