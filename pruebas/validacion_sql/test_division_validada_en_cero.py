"""División entre una variable que el código ya compara con 0 antes (usuaria, 25 nov., PA_CuentasOrden_Ins_AjusteCapital:
IF ISNULL(@nTipoCambio, 0) = 0 … y luego M.nMovImporte / @nTipoCambio)."""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _divisiones(sql):
    return [h for h in validar_estructura(sql) if h.regla == "DIVISION_SIN_NULLIF"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class DivisionValidadaEnCero(unittest.TestCase):
    def test_validada_antes_no_se_marca(self):
        for condicion in ("ISNULL(@nTipoCambio, 0) = 0", "@nTipoCambio = 0", "@nTipoCambio <= 0.00"):
            with self.subTest(condicion):
                sql = (f"DECLARE @nTipoCambio DECIMAL(18, 8), @nValida INT = 1, @nMonto MONEY = 10, @nR MONEY\n"
                       f"IF {condicion} SET @nValida = 4\n"
                       f"IF @nValida = 1 SET @nR = @nMonto / @nTipoCambio")
                self.assertEqual(_divisiones(sql), [])

    def test_sin_validar_se_sigue_marcando(self):
        sql = ("DECLARE @nTipoCambio DECIMAL(18, 8), @nMonto MONEY = 10, @nR MONEY\n"
               "SET @nR = @nMonto / @nTipoCambio")
        self.assertEqual(len(_divisiones(sql)), 1)


if __name__ == "__main__":
    unittest.main()
