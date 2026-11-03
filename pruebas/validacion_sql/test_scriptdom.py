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

    def test_mensaje_de_sql_server(self):
        hallazgo = validar_estructura("SELECT 1\nELSE\n SELECT 2")[0]
        self.assertIn("en la línea 2, columna 1:", hallazgo.mensaje)
        self.assertIn("'ELSE'", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
