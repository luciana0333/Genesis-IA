"""El número del mensaje agrupado es la cantidad real de casos (usuaria, 22 nov.).

Caso real FluGenSol_InsPropuesta_SP: salía «2 TOP sin ORDER BY: top 1 y TOP 1» con 29 casos, «2 comparaciones» con 5
y, en Motor_CalcularConfiguracionProductos_SP, «10 divisiones» con 17: se contaban los valores distintos.
"""
import unittest

from app.analizadores.scriptdom import validar_estructura


def _mensaje(sql, regla):
    return next(h.mensaje for h in validar_estructura(sql) if h.regla == regla)


class CantidadesReales(unittest.TestCase):
    def test_top_mayusculas_y_minusculas_es_lo_mismo(self):
        sql = "SELECT TOP 1 a FROM dbo.T WITH (NOLOCK)\nselect top 1 b FROM dbo.U WITH (NOLOCK)\nSELECT TOP 1 c FROM dbo.V WITH (NOLOCK)"
        self.assertTrue(_mensaje(sql, "TOP_SIN_ORDER_BY").startswith("Se identificaron 3 TOP sin ORDER BY: TOP 1. "))

    def test_division_cuenta_cada_una_y_nombra_el_divisor(self):
        sql = ("DECLARE @n MONEY = 3, @t MONEY = 2\nSELECT 20000.00 / @n, 25000.00 / @n\nSELECT 300000.00 /  @n\n"
               "SELECT 1 / @t")
        self.assertTrue(_mensaje(sql, "DIVISION_SIN_NULLIF").startswith(
            "Se identificaron 4 divisiones sin proteger el divisor: @n (3 veces) y @t. "))

    def test_mismo_divisor_usa_su_nullif(self):
        sql = "DECLARE @n MONEY = 3\nSELECT 20000.00 / @n\nSELECT 25000.00 / @n"
        self.assertEqual(_mensaje(sql, "DIVISION_SIN_NULLIF"),
                         "Se identificaron 2 divisiones sin proteger el divisor: @n. Se recomienda usar NULLIF(@n, 0), "
                         "ya que si el divisor es 0 el procedimiento falla con error de división entre cero.")

    def test_conversion_repetida_dice_las_veces_sin_parentesis_doble(self):
        sql = ("CREATE TABLE #B (cNumGarant BIGINT)\nDECLARE @g BIGINT = 1, @p INT = 1\n"
               "SELECT 1 FROM dbo.PersID WITH (NOLOCK) WHERE cPersIDTpo = @p\n"
               "SELECT 1 FROM dbo.G WITH (NOLOCK) WHERE cNumGarant = @g\n"
               "SELECT 1 FROM dbo.G WITH (NOLOCK) WHERE cNumGarant = @g")
        mensaje = _mensaje(sql, "CONVERSION_PREVISIBLE_VALIDAR")  # tablas físicas: se pide validar (22 nov.)
        self.assertIn("Se identificaron 3 comparaciones", mensaje)
        self.assertIn("(BIGINT, 2 veces)", mensaje)
        self.assertNotIn(") (", mensaje)

    def test_funciones_escalares_cuenta_usos(self):
        sql = ("SELECT dbo.FN_A(c) FROM dbo.T WITH (NOLOCK)\nSELECT dbo.FN_B(c) FROM dbo.T WITH (NOLOCK)\n"
               "SELECT dbo.FN_B(d) FROM dbo.T WITH (NOLOCK)")
        self.assertTrue(_mensaje(sql, "FUNCION_ESCALAR_POR_FILA").startswith(
            "Se identificaron 3 usos de funciones escalares dentro de una consulta: dbo.FN_A y dbo.FN_B (2 veces). "))

    def test_cosas_distintas_se_cuentan_una_vez(self):
        # Variables: cuenta variables, no apariciones; @A y @a son la misma para SQL Server.
        mensaje = _mensaje("SET @a = 1\nSET @b = 2\nSET @A = 3", "VARIABLE_NO_DECLARADA")
        self.assertTrue(mensaje.startswith("Se identificaron 2 variables"), mensaje)


if __name__ == "__main__":
    unittest.main()
