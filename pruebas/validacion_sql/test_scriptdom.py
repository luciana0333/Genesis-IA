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
            "DECLARE @n INT = 1\nWITH C AS (SELECT 1 AS n) SELECT n FROM C": [(2, "PUNTO_Y_COMA_ANTES_DE_WITH")],  # 319
            "DECLARE @i INT = 0; WHILE @i < 1 BEGIN SET @i += 1 END\nWITH C AS (SELECT 1 AS n) SELECT n FROM C":
                [(2, "PUNTO_Y_COMA_ANTES_DE_WITH")],
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


# Casos de la usuaria (9 nov.), probados en SQL Server (PARSEONLY y ejecución real en su SQL Express).
_CATCH = "BEGIN TRY\n SELECT 1/0;\nEND TRY\nBEGIN CATCH\n IF @@TRANCOUNT > 0\n"


@unittest.skipUnless(HAY_SCRIPTDOM, "ScriptDom no está en esta PC (viene con SSMS)")
class PuntoYComaThrowTest(unittest.TestCase):
    def _hallazgos(self, sql):
        return [(h.linea, h.regla, h.mensaje) for h in validar_estructura(sql)]

    def test_falta_punto_y_coma_tras_end_senala_la_linea_del_end(self):
        # Su script: el «;» va después del END (línea 8), no en el IF (línea 5) donde empieza la instrucción.
        sql = _CATCH + " BEGIN\n  ROLLBACK TRANSACTION\n END\n THROW\nEND CATCH"
        self.assertEqual(self._hallazgos(sql), [(
            9, "PUNTO_Y_COMA_FALTANTE",
            "Se identificó la ausencia de «;» al finalizar el bloque END, antes de la instrucción THROW. Se recomienda "
            "agregar el punto y coma (;) al finalizar el bloque (END;), para evitar el error de sintaxis 102 durante "
            "la ejecución del procedimiento.")])

    def test_otra_instruccion_antes_del_throw_dice_su_linea(self):
        mensaje = self._hallazgos("BEGIN TRY\n SELECT 1/0;\nEND TRY\nBEGIN CATCH\n PRINT 1\n THROW\nEND CATCH")[0][2]
        self.assertEqual(mensaje, "Se identificó la ausencia de «;» al finalizar la instrucción de la línea 5, antes de "
                                  "la instrucción THROW. Se recomienda agregar el punto y coma (;) al finalizar esa "
                                  "instrucción, para evitar el error de sintaxis 102 durante la ejecución del "
                                  "procedimiento.")

    def test_punto_y_coma_dentro_del_bloque_no_basta(self):
        sql = _CATCH + " BEGIN\n  ROLLBACK TRANSACTION;\n END\n THROW\nEND CATCH"
        self.assertEqual([(l, r) for l, r, _ in self._hallazgos(sql)], [(9, "PUNTO_Y_COMA_FALTANTE")])

    def test_con_punto_y_coma_en_su_lugar_no_se_marca(self):
        for sql in (_CATCH + " BEGIN\n  ROLLBACK TRANSACTION\n END;\n THROW\nEND CATCH",
                    _CATCH + " BEGIN\n  ROLLBACK TRANSACTION\n END\n ;THROW\nEND CATCH",
                    _CATCH + "  ROLLBACK TRANSACTION;\n THROW\nEND CATCH",
                    "BEGIN TRAN T1;\nROLLBACK TRANSACTION T1;"):
            with self.subTest(sql=sql):
                self.assertNotIn("PUNTO_Y_COMA_FALTANTE", [r for _, r, _ in self._hallazgos(sql)])
                self.assertNotIn("THROW_TOMADO_COMO_TRANSACCION", [r for _, r, _ in self._hallazgos(sql)])

    def test_rollback_seguido_de_throw_lo_toma_como_nombre(self):
        hallazgos = self._hallazgos(_CATCH + "  ROLLBACK TRANSACTION\n THROW\nEND CATCH")
        self.assertEqual(hallazgos, [(
            7, "THROW_TOMADO_COMO_TRANSACCION",
            "Se identificó un THROW después de un ROLLBACK TRANSACTION sin «;» (línea 6), por lo que SQL Server lo "
            "toma como el nombre de la transacción y el error nunca se relanza. Agregar «;» al final del ROLLBACK "
            "TRANSACTION, ya que sin él falla al ejecutarse (error 6401) y el error original se pierde.")])
        self.assertEqual(validar_estructura(_CATCH + "  ROLLBACK TRANSACTION\n THROW\nEND CATCH")[0].severidad.value,
                         "critico")

    def test_commit_seguido_de_throw_continua_sin_error(self):
        mensaje = [m for _, r, m in self._hallazgos("BEGIN TRY\n SELECT 1;\nEND TRY\nBEGIN CATCH\n COMMIT TRANSACTION\n"
                                                     " THROW\nEND CATCH") if r == "THROW_TOMADO_COMO_TRANSACCION"][0]
        self.assertTrue(mensaje.endswith("ya que sin él el error original se pierde y el código continúa como si no "
                                         "hubiera fallado."))

    def test_with_tiene_su_propia_regla_y_error_319(self):
        regla, mensaje = self._hallazgos("DECLARE @n INT = 1\nWITH C AS (SELECT 1 AS n) SELECT n FROM C")[0][1:]
        self.assertEqual(regla, "PUNTO_Y_COMA_ANTES_DE_WITH")
        self.assertEqual(mensaje, "Se identificó la ausencia de «;» al finalizar la instrucción de la línea 1, antes de "
                                  "la instrucción WITH. Se recomienda agregar el punto y coma (;) al finalizar esa "
                                  "instrucción, para evitar el error de sintaxis 319 durante la ejecución del "
                                  "procedimiento.")


if __name__ == "__main__":
    unittest.main()
