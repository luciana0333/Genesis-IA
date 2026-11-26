"""SELECT @x = … FROM #T sin WHERE, cuando #T se llena una sola vez con un SELECT de puros agregados sin GROUP BY:
#T tiene exactamente una fila (usuaria, 25 nov., #RECAUDO_TOTAL de PA_PagosSeguros_Ins_PagosSeguros)."""
import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")

BASE = """DECLARE @nTipo INT
CREATE TABLE #Total (nCantidad INT, nMonto MONEY)
INSERT INTO #Total (nCantidad, nMonto)
SELECT CAST(COUNT_BIG(a.nId) AS INT), SUM(ISNULL(a.nMonto, 0)) FROM dbo.T a WITH (NOLOCK)
{extra}SELECT @nTipo = CASE WHEN nCantidad > 0 THEN 1 ELSE 2 END FROM #Total"""


def _asignaciones(sql):
    return [h for h in validar_estructura(sql) if h.regla == "ASIGNACION_VARIAS_FILAS"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class TemporalDeUnaFila(unittest.TestCase):
    def test_temporal_de_agregados_no_se_marca(self):
        self.assertEqual(_asignaciones(BASE.format(extra="")), [])

    def test_si_se_inserta_otra_vez_se_sigue_marcando(self):
        sql = BASE.format(extra="INSERT INTO #Total (nCantidad, nMonto) SELECT 1, 2\n")
        self.assertEqual(len(_asignaciones(sql)), 1)

    def test_temporal_con_group_by_se_sigue_marcando(self):
        sql = BASE.replace("FROM dbo.T a WITH (NOLOCK)", "FROM dbo.T a WITH (NOLOCK) GROUP BY a.nTipo").format(extra="")
        self.assertEqual(len(_asignaciones(sql)), 1)


if __name__ == "__main__":
    unittest.main()
