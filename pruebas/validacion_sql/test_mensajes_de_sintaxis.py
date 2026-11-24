"""El error de sintaxis dice cuál es y dónde (usuaria, 23 nov.: «solo dice un posible pero no dice cuál es el error»).

Caso real (Diccionarios): «CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId;» con «@nClienteId INT» en la línea de
abajo: el ; separa el nombre de sus parámetros. Antes: «error de sintaxis en la columna 49: Sintaxis incorrecta cerca de
';'. Corregir la estructura (comas, paréntesis, comillas…)».
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM
from app.analizadores.validador_en_modulos import validar_para_modulo

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _errores(tipo, sql):
    return [h for h in validar_para_modulo(tipo, sql)["hallazgos"] if h.regla == "ERROR_SINTAXIS"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class MensajesDeSintaxis(unittest.TestCase):
    def test_punto_y_coma_despues_del_nombre(self):
        casos = {
            "caso real (Diccionarios)": ("procedimiento", "CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId;\n    @nClienteId INT",
                                         "del procedimiento", "crear el procedimiento"),
            "procedimiento completo": ("procedimiento_normal", "CREATE PROCEDURE dbo.PA_X;\n @a INT\nAS\nBEGIN\nSELECT @a\nEND",
                                       "del procedimiento", "crear el procedimiento"),
            "función": ("funcion", "CREATE FUNCTION dbo.fn_X; (@a INT) RETURNS INT", "de la función", "crear la función"),
        }
        for nombre, (tipo, sql, de, que) in casos.items():
            with self.subTest(nombre):
                errores = _errores(tipo, sql)
                self.assertEqual(len(errores), 1)
                self.assertEqual(errores[0].linea, 1)
                self.assertTrue(errores[0].mensaje.startswith(
                    f"Se identificó que sobra un punto y coma (;) después del nombre {de}: «{sql.splitlines()[0].strip()}» "
                    f"(línea 1). Retirarlo"), errores[0].mensaje)
                self.assertIn(f"SQL Server no podrá {que}", errores[0].mensaje)

    def test_punto_y_coma_entre_parametros(self):
        errores = _errores("procedimiento", "ALTER PROCEDURE DBO.PA_X(\n\t@a INT;\n\t@b INT\n)")
        self.assertIn("hay un punto y coma (;) entre los parámetros, donde va una coma: «@a INT;» (línea 2). "
                      "Reemplazarlo por una coma", errores[0].mensaje)

    def test_falta_una_coma_entre_parametros(self):
        casos = {
            "con comentario": ("ALTER PROCEDURE dbo.PA_X(\n\t@a INT -- id\n\t@b VARCHAR(10) = NULL\n\t)",
                               "«@a INT» (línea 2) no termina en coma antes de «@b VARCHAR(10) = NULL»"),
            "con valor y OUTPUT": ("ALTER PROCEDURE dbo.PA_X(\n\t@a VARCHAR(10) = '' OUTPUT\n\t@b INT\n\t)",
                                   "«@a VARCHAR(10) = '' OUTPUT» (línea 2) no termina en coma antes de «@b INT»"),
        }
        for nombre, (sql, esperado) in casos.items():
            with self.subTest(nombre):
                mensaje = _errores("procedimiento", sql)[0].mensaje
                self.assertTrue(mensaje.startswith("Se identificó que falta una coma entre los parámetros: "), mensaje)
                self.assertIn(esperado, mensaje)
                self.assertIn("Agregar la coma al final de la línea 2", mensaje)

    def test_cualquier_otro_muestra_el_texto_de_la_linea(self):
        errores = _errores("procedimiento_normal", "CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n  SELECT a.n FORM dbo.T a\nEND")
        self.assertEqual(errores[0].mensaje,
                         "Se identificó un error de sintaxis cerca de «dbo»: «SELECT a.n FORM dbo.T a» (línea 3). Revisar "
                         "esa parte o la línea anterior (comas, paréntesis, comillas, BEGIN/END), ya que SQL Server no "
                         "podrá crear el procedimiento con este error.")

    def test_linea_larga_muestra_el_tramo_del_error(self):
        sql = "SELECT " + ", ".join(f"a.columna{n}" for n in range(30)) + " FORM dbo.T a"
        mensaje = _errores("procedimiento_normal", sql)[0].mensaje
        self.assertIn("…", mensaje)
        self.assertIn("FORM dbo.T a", mensaje)

    def test_punto_y_coma_final_de_una_firma_sola_no_se_marca(self):
        self.assertEqual(_errores("procedimiento", "ALTER PROCEDURE dbo.PA_X(@a INT, @b INT);"), [])
        self.assertEqual(_errores("procedimiento", "ALTER PROCEDURE dbo.PA_X\n(\n\t@a INT\n);\n"), [])


if __name__ == "__main__":
    unittest.main()
