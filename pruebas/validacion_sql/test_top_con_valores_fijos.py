"""SELECT TOP 1 con solo valores fijos no necesita ORDER BY (usuaria, 24 nov.).

Caso real PA_PagosTramas_Ins: «SELECT TOP 1 CAST(3082.00 AS MONEY), '0000000000', … FROM #PagosTramas WHERE …»:
cualquier fila da el mismo resultado.
"""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _top(sql):
    return [h.regla for h in validar_estructura(sql) if h.regla == "TOP_SIN_ORDER_BY"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class TopConValoresFijos(unittest.TestCase):
    def test_solo_valores_fijos_no_se_marca(self):
        casos = {
            "caso real": "CREATE TABLE #P (nMovNro INT)\nCREATE TABLE #D (nMonto MONEY, c VARCHAR(10), p VARCHAR(20), f DATE)\n"
                         "INSERT INTO #D (nMonto, c, p, f)\nSELECT TOP 1 CAST(3082.00 AS MONEY), '0000000000', "
                         "CAST('31/93562' AS VARCHAR(20)), CAST('2026-04-10' AS DATE) FROM #P WHERE nMovNro = 194690543",
            "CONVERT y variable": "DECLARE @n INT = 1\nSELECT TOP 1 CONVERT(VARCHAR(8), 's/period'), @n FROM dbo.T a WITH (NOLOCK)",
            "asignación fija": "DECLARE @b BIT\nSELECT TOP 1 @b = 1 FROM dbo.T a WITH (NOLOCK)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_top(sql), [])

    def test_con_alguna_columna_se_sigue_marcando(self):
        casos = {
            "columna": "SELECT TOP 1 a.nId FROM dbo.T a WITH (NOLOCK) WHERE a.d = '2026-01-01'",
            "fijo y columna": "SELECT TOP 1 CAST(1 AS INT), a.nId FROM dbo.T a WITH (NOLOCK)",
            "CAST de columna": "SELECT TOP 1 CAST(a.nId AS VARCHAR(10)) FROM dbo.T a WITH (NOLOCK)",
            "asignación de columna": "DECLARE @n INT\nSET @n = ISNULL((SELECT TOP 1 a.nId FROM dbo.T a WITH (NOLOCK)), 0)",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_top(sql), ["TOP_SIN_ORDER_BY"])


if __name__ == "__main__":
    unittest.main()
