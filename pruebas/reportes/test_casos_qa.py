"""Casos de borde encontrados en la auditoría de QA del módulo de Reportes."""
import unittest

from app.analizadores.analizador_reportes import verificar_reporte

ENCABEZADO = "CREATE PROCEDURE dbo.PA_Cliente_Sel_Resumen\n    @nAgenciaId INT\nAS\nBEGIN\n"


def procedimiento(cuerpo):
    return ENCABEZADO + cuerpo + "\nEND"


def reglas(sql):
    return [(h.regla, h.linea) for h in verificar_reporte(sql)]


class TestReportesQA(unittest.TestCase):
    def test_palabras_dentro_de_un_texto_no_son_codigo(self):
        sql = procedimiento(
            "    SELECT 'SELECT * FROM sys.objects IN (1)' AS cTexto, c.cNombre "
            "FROM dbo.Cliente c WITH(NOLOCK) WHERE c.nAgenciaId = @nAgenciaId;"
        )
        self.assertEqual(reglas(sql), [])

    def test_guiones_dentro_de_un_texto_no_son_comentario(self):
        for texto in ("'--'", "'O''Brien -- x'"):
            with self.subTest(texto=texto):
                sql = procedimiento(f"    SELECT {texto} + c.cNombre FROM dbo.Cliente c WHERE c.nAgenciaId = @nAgenciaId;")
                self.assertEqual(reglas(sql), [("TABLA_FISICA_SIN_NOLOCK", 5)])

    def test_select_into_sin_punto_y_coma(self):
        tras_begin = procedimiento("    SELECT c.cNombre INTO #T FROM dbo.Cliente c WITH(NOLOCK);")
        self.assertEqual(reglas(tras_begin), [("SELECT_INTO_PROHIBIDO", 5)])
        tras_sentencia = procedimiento(
            "    DECLARE @x INT = 1\n    SELECT c.cNombre INTO #T FROM dbo.Cliente c WITH(NOLOCK) WHERE c.nAgenciaId = @x"
        )
        self.assertEqual(reglas(tras_sentencia), [("SELECT_INTO_PROHIBIDO", 6)])

    def test_insert_into_select_no_es_select_into(self):
        sql = procedimiento("    INSERT INTO #T (n) SELECT c.nId FROM dbo.Cliente c WITH(NOLOCK);")
        self.assertEqual(reglas(sql), [])

    def test_select_top_y_alias_estrella(self):
        for select in ("SELECT TOP 10 *", "SELECT TOP (10) PERCENT *", "SELECT c.*"):
            with self.subTest(select=select):
                sql = procedimiento(f"    {select} FROM dbo.Cliente c WITH(NOLOCK);")
                self.assertEqual(reglas(sql), [("SELECT_ESTRELLA_PROHIBIDO", 5)])
        hallazgo = verificar_reporte(procedimiento("    SELECT c.*, a.cNombre FROM dbo.Cliente c WITH(NOLOCK) JOIN dbo.Agencia a WITH(NOLOCK) ON a.nId = c.nId;"))[0]
        self.assertIn("todas las columnas de la tabla dbo.Cliente", hallazgo.mensaje)

    def test_count_estrella_no_es_select_estrella(self):
        sql = procedimiento("    SELECT COUNT(*) FROM dbo.Cliente c WITH(NOLOCK);")
        self.assertEqual(reglas(sql), [])

    def test_otras_formas_de_modificar_tablas(self):
        for sentencia, tabla in (
            ("DELETE dbo.Cliente WHERE nId = 1;", "dbo.Cliente con DELETE"),
            ("INSERT dbo.Cliente (cNombre) VALUES ('x');", "dbo.Cliente con INSERT"),
            ("TRUNCATE TABLE dbo.Log;", "dbo.Log con TRUNCATE TABLE"),
            ("UPDATE c SET c.cNombre = 'x' FROM dbo.Cliente c;", "dbo.Cliente con UPDATE"),
        ):
            with self.subTest(sentencia=sentencia):
                hallazgo = verificar_reporte(procedimiento(f"    {sentencia}"))[0]
                self.assertEqual(hallazgo.regla, "MODIFICACION_TABLA_FISICA")
                self.assertIn(tabla, hallazgo.mensaje)

    def test_modificar_temporal_por_alias_es_valido(self):
        for sentencia in ("DELETE t FROM #T t WHERE t.nId = 1;", "UPDATE t SET t.n = 1 FROM #T t;"):
            with self.subTest(sentencia=sentencia):
                self.assertEqual(reglas(procedimiento(f"    {sentencia}")), [])

    def test_merge_join_es_hint_y_no_modificacion(self):
        sql = procedimiento("    SELECT c.cNombre FROM dbo.Cliente c WITH(NOLOCK) INNER MERGE JOIN dbo.Agencia a WITH(NOLOCK) ON a.nId = c.nId;")
        self.assertEqual(reglas(sql), [("HINT_PLAN_PROHIBIDO", 5)])

    def test_hint_dentro_de_sql_dinamico(self):
        sql = procedimiento(
            "    DECLARE @cSQL NVARCHAR(MAX);\n"
            "    SET @cSQL = N'\n"
            "        SELECT nClienteId FROM dbo.Cliente WITH (UPDLOCK)\n"
            "        WHERE nClienteId = @nClienteId';\n"
            "    EXEC sys.sp_executesql @cSQL, N'@nClienteId INT', @nClienteId = @nAgenciaId;"
        )
        hallazgos = {(h.regla, h.linea) for h in verificar_reporte(sql)}
        self.assertIn(("HINT_BLOQUEO_PROHIBIDO", 7), hallazgos)
        self.assertIn(("SQL_DINAMICO_PROHIBIDO", 9), hallazgos)
        # sys.sp_executesql es un procedimiento del sistema, no una tabla interna.
        self.assertNotIn("CATALOGO_SISTEMA_PROHIBIDO", {regla for regla, _ in hallazgos})

    def test_hints_de_bloqueo_explican_lo_que_hacen(self):
        sql = procedimiento(
            "    SELECT c.cNombre FROM dbo.Cliente c WITH (UPDLOCK)\n"
            "    JOIN dbo.Agencia a WITH (HOLDLOCK, ROWLOCK) ON a.nId = c.nId\n"
            "    JOIN dbo.Zona z (TABLOCK) ON z.nId = a.nId;"
        )
        hallazgo = next(h for h in verificar_reporte(sql) if h.regla == "HINT_BLOQUEO_PROHIBIDO")
        for texto in ("'UPDLOCK', que bloquea las filas leídas", "'HOLDLOCK', que mantiene bloqueadas",
                      "'ROWLOCK', que obliga", "'TABLOCK', que bloquea toda la tabla", "usar WITH(NOLOCK)"):
            self.assertIn(texto, hallazgo.mensaje)
        self.assertNotIn("HINT_PLAN_PROHIBIDO", {h.regla for h in verificar_reporte(sql)})

    def test_nolock_no_es_hint_de_bloqueo(self):
        sql = procedimiento("    SELECT c.cNombre FROM dbo.Cliente c WITH (NOLOCK);")
        self.assertEqual(reglas(sql), [])

    def test_tabla_sin_nolock_dentro_de_sql_dinamico(self):
        sql = (
            "ALTER PROCEDURE dbo.PA_Cliente_Sel_Reporte\n    @nClienteId INT\nAS\nBEGIN\n"
            "    DECLARE @cSQL NVARCHAR(500);\n"
            "    SET @cSQL = N'\n        SELECT nClienteId\n        FROM dbo.Cliente\n"
            "        WHERE nClienteId = @nClienteId';\n"
            "    EXEC sys.sp_executesql @cSQL, N'@nClienteId INT', @nClienteId = @nClienteId;\nEND"
        )
        self.assertIn(("TABLA_FISICA_SIN_NOLOCK", 8), reglas(sql))

    def test_texto_comun_no_es_sql_dinamico(self):
        sql = procedimiento("    DECLARE @cNota VARCHAR(50) = 'Pendiente de revisión';\n    SELECT @cNota;")
        self.assertEqual(reglas(sql), [])

    def test_transaccion_con_commit(self):
        sql = procedimiento("    BEGIN TRANSACTION;\n    SELECT c.cNombre FROM dbo.Cliente c WITH(NOLOCK);\n    COMMIT TRANSACTION;")
        self.assertEqual(reglas(sql), [("TRANSACCION_EN_REPORTE", 5)])

    def test_transaccion_sin_commit(self):
        sql = procedimiento("    BEGIN TRAN;\n    SELECT c.cNombre FROM dbo.Cliente c WITH(NOLOCK);")
        self.assertEqual(reglas(sql), [("TRANSACCION_EN_REPORTE", 5), ("TRANSACCION_SIN_CIERRE", 5)])
        self.assertEqual(verificar_reporte(sql)[1].severidad.value, "critico")

    def test_rollback_tambien_cierra_y_begin_try_no_es_transaccion(self):
        sql = procedimiento(
            "    BEGIN TRY\n        BEGIN TRANSACTION;\n        SELECT 1;\n        COMMIT;\n    END TRY\n"
            "    BEGIN CATCH\n        ROLLBACK TRANSACTION;\n    END CATCH"
        )
        self.assertEqual(reglas(sql), [("TRANSACCION_EN_REPORTE", 6)])

    def test_varchar_max_nombra_el_tipo_escrito(self):
        hallazgo = verificar_reporte(procedimiento("    DECLARE @cTexto NVARCHAR(MAX) = N'';\n    SELECT @cTexto;"))[0]
        self.assertIn("@cTexto se declara como NVARCHAR(MAX)", hallazgo.mensaje)

    def test_mensaje_de_ltrim_rtrim(self):
        sql = procedimiento("    SELECT LTRIM(RTRIM(c.cNombre)) FROM dbo.Cliente c WITH(NOLOCK);")
        self.assertIn("le da más legibilidad al código", verificar_reporte(sql)[0].mensaje)


if __name__ == "__main__":
    unittest.main()
