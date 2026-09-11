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


if __name__ == "__main__":
    unittest.main()