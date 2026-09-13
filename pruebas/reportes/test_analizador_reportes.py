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


if __name__ == "__main__":
    unittest.main()