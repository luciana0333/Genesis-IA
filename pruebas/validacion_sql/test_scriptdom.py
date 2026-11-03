"""Validación SQL Server, etapa 1: errores de estructura leídos con ScriptDom (el lector de SSMS).

Las pruebas que necesitan ScriptDom se saltan si la PC no lo tiene (viene con SSMS).
"""

import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, mensaje_error_sintaxis, validar_estructura

HAY_SCRIPTDOM = LECTOR_SCRIPTDOM.estado().get("disponible", False)


class MensajeTest(unittest.TestCase):
    def test_mensaje_con_linea_columna_y_texto_de_sql_server(self):
        self.assertEqual(
            mensaje_error_sintaxis({"linea": 10, "columna": 1, "mensaje": "Sintaxis incorrecta cerca de 'END'."}),
            "Se identificó un error de sintaxis en la línea 10, columna 1: Sintaxis incorrecta cerca de 'END'. "
            "Corregir la estructura en esa línea o justo antes (comas, paréntesis, comillas, BEGIN/END), ya que "
            "SQL Server no podrá crear ni ejecutar el código con este error.",
        )


@unittest.skipUnless(HAY_SCRIPTDOM, "ScriptDom no está en esta PC (viene con SSMS)")
class EstructuraTest(unittest.TestCase):
    def _lineas(self, sql):
        return [(h.linea, h.regla, h.severidad.value) for h in validar_estructura(sql)]

    def test_codigo_correcto_no_tiene_errores(self):
        sql = ("CREATE PROCEDURE dbo.PA_Cliente_Sel_Datos\n @pnId INT\nAS\nBEGIN\n IF @pnId > 0\n"
               "  SELECT 'Año' AS cTexto\nEND\nGO\nCREATE PROCEDURE dbo.PA_Agencia_Sel_Datos AS SELECT 1\nGO")
        self.assertEqual(self._lineas(sql), [])

    def test_errores_de_estructura(self):
        casos = {
            "SELECT a,, b FROM dbo.T": 1,                                    # coma de más
            "SELECT a, b, FROM dbo.T": 1,                                    # coma antes del FROM
            "SELECT 1\nSELECT a FROM dbo.T WHERE (x = 1 AND (y = 2)": 2,     # paréntesis sin cerrar
            "SELECT 1\nSELECT 'hola FROM dbo.T": 2,                          # comilla sin cerrar
            "CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n SELECT 1": 3,             # BEGIN sin END
            "SELECT 1\nELSE\n SELECT 2": 2,                                  # ELSE sin IF
        }
        for sql, linea in casos.items():
            with self.subTest(sql=sql):
                self.assertEqual(self._lineas(sql), [(linea, "ERROR_SINTAXIS", "critico")])

    def test_cada_error_en_su_linea_con_go(self):
        sql = "CREATE PROCEDURE dbo.PA_A AS SELECT 1\nGO\nSELECT a,, b FROM T\nGO\nSELECT (1 FROM T\nGO"
        self.assertEqual([linea for linea, _, _ in self._lineas(sql)], [3, 5])

    def test_sintaxis_valida_que_sql_server_rechaza(self):
        # Cada caso se comprobó en SQL Server (error indicado al lado).
        casos = {
            "CREATE TABLE #T (a INT, b INT, c INT)\nINSERT INTO #T (a, b, c) VALUES (1, 2)":                 # 109
                [(2, "INSERT_COLUMNAS_NO_COINCIDEN")],
            "INSERT INTO dbo.T (a, b) SELECT 1, 2, 3": [(1, "INSERT_COLUMNAS_NO_COINCIDEN")],             # 121
            "CREATE TABLE #T (a INT,\n A INT)": [(2, "COLUMNA_REPETIDA_EN_TABLA")],                       # 2705
            "DECLARE @T TABLE (a INT, a INT)": [(1, "COLUMNA_REPETIDA_EN_TABLA")],
            "CREATE PROCEDURE dbo.PA_X AS BEGIN\nCREATE TABLE #T (a INT)\nDROP TABLE #T\nCREATE TABLE #T (a INT)\nEND":
                [(4, "TEMPORAL_CREADA_DOS_VECES")],                                                       # 2714
            "CREATE PROCEDURE dbo.PA_X @n INT AS BEGIN\nIF @n = 1 CREATE TABLE #T (a INT)\nELSE CREATE TABLE #T (b INT)\nEND":
                [(3, "TEMPORAL_CREADA_DOS_VECES")],
            "SELECT 1 AS a INTO #T\nDROP TABLE #T\nSELECT 2 AS a INTO #T": [(3, "TEMPORAL_CREADA_DOS_VECES")],
            "CREATE TABLE #T (a INT PRIMARY KEY, b INT,\n PRIMARY KEY (b))": [(2, "DOS_PRIMARY_KEY")],      # 8110
            "SELECT 1 FROM #A x\nJOIN #B x ON 1 = 1": [(2, "ALIAS_REPETIDO_EN_FROM")],                    # 1011
            "SELECT 1 FROM #C JOIN #C ON 1 = 1": [(1, "ALIAS_REPETIDO_EN_FROM")],                          # 1013
            "DECLARE @n INT = 1\nWITH C AS (SELECT 1 AS n) SELECT n FROM C": [(2, "PUNTO_Y_COMA_FALTANTE")],  # 319
            "DECLARE @i INT = 0; WHILE @i < 1 BEGIN SET @i += 1 END\nWITH C AS (SELECT 1 AS n) SELECT n FROM C":
                [(2, "PUNTO_Y_COMA_FALTANTE")],
            "BEGIN TRY SELECT 1/0 END TRY BEGIN CATCH DECLARE @x INT SET @x = 1\nTHROW END CATCH":         # 102
                [(2, "PUNTO_Y_COMA_FALTANTE")],
            # Sin error, pero THROW queda como nombre de columna y el error no se relanza.
            "BEGIN TRY SELECT 1/0 END TRY BEGIN CATCH SELECT 2\nTHROW END CATCH": [(2, "THROW_TOMADO_COMO_ALIAS")],
        }
        for sql, esperado in casos.items():
            with self.subTest(sql=sql):
                self.assertEqual([(linea, regla) for linea, regla, _ in self._lineas(sql)], esperado)

    def test_casos_validos_no_se_marcan(self):
        for sql in (
            "INSERT INTO dbo.T (a, b) SELECT * FROM #X",
            "INSERT INTO dbo.T (a, b) SELECT 1, 2 UNION ALL SELECT 3, 4",
            "CREATE TABLE #T (a INT)\nGO\nCREATE TABLE #T (a INT)",
            "SELECT 1 FROM #D x WHERE EXISTS (SELECT 1 FROM #D x WHERE x.n = 1)",
            "SELECT 1 FROM (SELECT n FROM #D x) x JOIN #E y ON 1 = 1",
            "IF 1 = 1 BEGIN WITH C AS (SELECT 1 AS n) SELECT n FROM C; END",
            "IF 1 = 1 WITH C AS (SELECT 1 AS n) SELECT n FROM C",
            "SELECT 1;\nWITH C AS (SELECT 1 AS n) SELECT n FROM C",
            "BEGIN TRY SELECT 1/0 END TRY BEGIN CATCH THROW END CATCH",
            "CREATE PROCEDURE dbo.PA_X AS WITH C AS (SELECT 1 AS n) SELECT n FROM C",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(self._lineas(sql), [])

    def test_mensajes(self):
        mensajes = {h.regla: h.mensaje for h in validar_estructura(
            "INSERT INTO #T (a, b, c) VALUES (1, 2)")}
        self.assertEqual(
            mensajes["INSERT_COLUMNAS_NO_COINCIDEN"],
            "Se identificó un INSERT INTO #T que indica 3 columnas, pero envía 2 valores. Igualar la cantidad de "
            "columnas y de valores, ya que SQL Server no ejecutará el INSERT (error 109).",
        )
        temporal = validar_estructura("SELECT 1 AS a INTO #T\nDROP TABLE #T\nSELECT 2 AS a INTO #T")[0].mensaje
        self.assertIn("se crea dos veces en el mismo bloque (líneas 1 y 3)", temporal)

    def test_mensaje_de_sql_server(self):
        hallazgo = validar_estructura("SELECT 1\nELSE\n SELECT 2")[0]
        self.assertIn("en la línea 2, columna 1:", hallazgo.mensaje)
        self.assertIn("'ELSE'", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
