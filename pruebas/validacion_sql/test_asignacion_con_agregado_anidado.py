"""SELECT @x = ISNULL(SUM(col), 0) FROM … sin WHERE no es «asignación de varias filas» (usuaria, 24 nov.).

Caso real PA_RegistrosSeguros_Ins: «SELECT @nMontoInicialDetalle = ISNULL(SUM(nSaldoInicial),0), … FROM #RegistrosSeguros»
se marcaba porque el agregado estaba dentro de ISNULL. Con un agregado la consulta devuelve una sola fila.
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _reglas(sql):
    return [h.regla for h in validar_estructura(sql) if h.regla in ("ASIGNACION_VARIAS_FILAS", "TOP_SIN_ORDER_BY")]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class AgregadoAnidado(unittest.TestCase):
    def test_agregado_dentro_de_otra_funcion_no_se_marca(self):
        casos = {
            "caso real": "DECLARE @a MONEY, @b MONEY\nCREATE TABLE #R (n MONEY, m MONEY)\n"
                         "SELECT @a = ISNULL(SUM(n),0), @b = ISNULL(SUM(m),0) FROM #R",
            "CAST(COUNT_BIG)": "DECLARE @n INT\nSELECT @n = CAST(COUNT_BIG(1) AS INT) FROM dbo.T a WITH (NOLOCK)",
            "SUM directo": "DECLARE @a MONEY\nSELECT @a = SUM(a.n) FROM dbo.T a WITH (NOLOCK)",
            "TOP con SUM": "DECLARE @a MONEY\nSELECT TOP 1 @a = ISNULL(SUM(a.n),0) FROM dbo.T a WITH (NOLOCK)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_reglas(sql), [])

    def test_sin_agregado_se_sigue_marcando(self):
        casos = {
            "columna suelta": "DECLARE @a MONEY\nSELECT @a = a.n FROM dbo.T a WITH (NOLOCK)",
            "ISNULL de una columna": "DECLARE @a MONEY\nSELECT @a = ISNULL(a.n,0) FROM dbo.T a WITH (NOLOCK)",
            "agregado solo en una subconsulta": "DECLARE @a MONEY\nSELECT @a = (SELECT MAX(x.n) FROM dbo.X x WITH (NOLOCK)) "
                                                "+ a.n FROM dbo.T a WITH (NOLOCK)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_reglas(sql), ["ASIGNACION_VARIAS_FILAS"])


if __name__ == "__main__":
    unittest.main()
