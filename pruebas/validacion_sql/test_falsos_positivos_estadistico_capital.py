"""Falsos positivos de PA_CuentasOrden_Ajuste_EstadisticoCapitalMensual (usuaria, 25 nov.)."""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _reglas(sql):
    return [h.regla for h in validar_estructura(sql)]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class FalsosPositivosEstadisticoCapital(unittest.TestCase):
    def test_begin_tran_en_un_if_justo_antes_del_try(self):
        sql = """DECLARE @n INT = @@TRANCOUNT
IF @n = 0
    BEGIN TRANSACTION P
ELSE
    SAVE TRANSACTION P
BEGIN TRY
    UPDATE dbo.T SET a = 1 WHERE b = 2
    IF @n = 0 COMMIT TRANSACTION P
END TRY
BEGIN CATCH
    IF XACT_STATE() <> 0 AND @n = 0 ROLLBACK TRANSACTION P
END CATCH"""
        self.assertNotIn("TRANSACCION_SIN_TRY", _reglas(sql))

    def test_begin_tran_lejos_del_try_se_sigue_marcando(self):
        sql = """BEGIN TRANSACTION
UPDATE dbo.T SET a = 1 WHERE b = 2
COMMIT TRANSACTION"""
        self.assertIn("TRANSACCION_SIN_TRY", _reglas(sql))

    def test_top_de_todas_las_filas(self):
        for top in ("TOP (2147483647)", "TOP 100 PERCENT"):
            with self.subTest(top):
                sql = f"SELECT {top} a.nId FROM dbo.T a WITH (NOLOCK) WHERE a.b = 1"
                self.assertNotIn("TOP_SIN_ORDER_BY", _reglas(sql))
        self.assertIn("TOP_SIN_ORDER_BY", _reglas("SELECT TOP 10 a.nId FROM dbo.T a WITH (NOLOCK) WHERE a.b = 1"))

    def test_like_con_comodin_en_el_select_no_se_marca(self):
        sql = ("SELECT CASE WHEN M.cMovDesc LIKE '%covid%' THEN 1 ELSE 0 END FROM dbo.Mov M WITH (NOLOCK) "
               "WHERE M.nMovNro = 1")
        self.assertNotIn("LIKE_COMODIN_INICIO", _reglas(sql))
        self.assertIn("LIKE_COMODIN_INICIO", _reglas(
            "SELECT M.nMovNro FROM dbo.Mov M WITH (NOLOCK) WHERE M.cMovDesc LIKE '%covid%'"))

    def test_funcion_sobre_columna_de_un_cross_apply(self):
        sql = """SELECT P.nId
FROM dbo.T P WITH (NOLOCK)
CROSS APPLY (SELECT P.nMonto AS nImporte UNION ALL SELECT P.nOtro) C
WHERE ISNULL(C.nImporte, 0) > 0"""
        self.assertNotIn("FUNCION_SOBRE_COLUMNA", _reglas(sql))


if __name__ == "__main__":
    unittest.main()
