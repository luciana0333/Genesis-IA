"""ISNULL sobre columnas (3 nov., idea de la usuaria): validar si la columna acepta NULL con una consulta lista.

La consulta va sobre la tabla física (la temporal solo existe mientras corre el procedimiento): si la columna
es de una temporal que se llena desde una tabla física, se sigue ese camino. No se marca lo que sí puede traer
NULL aunque la tabla no lo tenga: el lado opcional de un LEFT JOIN u OUTER APPLY, agregados, subconsultas,
variables y columnas calculadas.
"""

import unittest

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura
from app.analizadores.scriptdom_mensajes import consulta_de_nulos

HAY_SCRIPTDOM = LECTOR_SCRIPTDOM.estado().get("disponible", False) and LECTOR_SCRIPTDOM.estado().get("revisor", False)


def _isnull(sql):
    return [h for h in validar_estructura(sql) if h.regla.startswith("ISNULL_")]


@unittest.skipUnless(HAY_SCRIPTDOM, "ScriptDom no está en esta PC (viene con SSMS)")
class IsnullTest(unittest.TestCase):
    def test_se_marca(self):
        casos = {
            "SELECT ISNULL(c.nSaldo, 0) FROM dbo.Credito c": ("ISNULL_VALIDAR_NULOS", "bajo"),
            "SELECT a FROM dbo.Examen e WHERE ISNULL(e.bEvaluado, 0) = 0": ("ISNULL_EN_CONDICION", "medio"),
            "SELECT ISNULL(c.nSaldo, 0) FROM dbo.Credito c LEFT JOIN dbo.CreditoCuota q ON q.cCtaCod = c.cCtaCod":
                ("ISNULL_VALIDAR_NULOS", "bajo"),
            "CREATE TABLE #R (nSaldo DECIMAL(18,2) NOT NULL)\nSELECT ISNULL(nSaldo, 0) FROM #R":
                ("ISNULL_EN_COLUMNA_NOT_NULL", "medio"),
            "CREATE TABLE #R (cCtaCod VARCHAR(18), nSaldo DECIMAL(18,2))\n"
            "INSERT INTO #R (cCtaCod, nSaldo) SELECT c.cCtaCod, c.nSaldo FROM dbo.Credito c\n"
            "SELECT ISNULL(r.nSaldo, 0) FROM #R r": ("ISNULL_VALIDAR_NULOS", "bajo"),
            "SELECT c.cCtaCod, c.nSaldo AS nSaldoActual INTO #R FROM dbo.Credito c\nSELECT ISNULL(nSaldoActual, 0) FROM #R":
                ("ISNULL_VALIDAR_NULOS", "bajo"),
        }
        for sql, (regla, severidad) in casos.items():
            with self.subTest(sql=sql):
                hallazgos = _isnull(sql)
                self.assertEqual([(h.regla, h.severidad.value) for h in hallazgos], [(regla, severidad)])

    def test_no_se_marca(self):
        for sql in (
            "SELECT ISNULL(q.nMonto, 0) FROM dbo.Credito c LEFT JOIN dbo.CreditoCuota q ON q.cCtaCod = c.cCtaCod",
            "SELECT ISNULL(x.nMonto, 0) FROM dbo.Credito c OUTER APPLY (SELECT TOP 1 nMonto FROM dbo.CreditoCuota q "
            "WHERE q.cCtaCod = c.cCtaCod ORDER BY nCuota) x",
            "SELECT ISNULL(SUM(c.nSaldo), 0) FROM dbo.Credito c",
            "DECLARE @n INT = NULL\nSELECT ISNULL(@n, 0)",
            "SELECT ISNULL((SELECT MAX(nSaldo) FROM dbo.Credito), 0)",
            "CREATE TABLE #R (nTotal DECIMAL(18,2))\nINSERT INTO #R (nTotal) SELECT SUM(c.nSaldo) FROM dbo.Credito c\n"
            "SELECT ISNULL(nTotal, 0) FROM #R",
            "CREATE TABLE #R (nMonto DECIMAL(18,2))\nINSERT INTO #R (nMonto) SELECT q.nMonto FROM dbo.Credito c "
            "LEFT JOIN dbo.CreditoCuota q ON q.cCtaCod = c.cCtaCod\nSELECT ISNULL(nMonto, 0) FROM #R",
            "CREATE TABLE #R (nMonto DECIMAL(18,2))\nINSERT INTO #R (nMonto) SELECT a.nMonto FROM dbo.A a\n"
            "INSERT INTO #R (nMonto) SELECT b.nOtro FROM dbo.B b\nSELECT ISNULL(nMonto, 0) FROM #R",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(_isnull(sql), [])

    def test_temporal_dice_de_donde_se_llena_y_una_consulta_para_todo(self):
        sql = ("CREATE TABLE #R (cCtaCod VARCHAR(18), nSaldo DECIMAL(18,2))\n"
               "INSERT INTO #R (cCtaCod, nSaldo) SELECT c.cCtaCod, c.nSaldo FROM dbo.Credito c\n"
               "SELECT ISNULL(r.nSaldo, 0), ISNULL(c.nMora, 0) FROM #R r JOIN dbo.Credito c ON c.cCtaCod = r.cCtaCod")
        hallazgo = _isnull(sql)[0]
        self.assertIn("sobre la columna nSaldo de #R, que se llena desde dbo.Credito.nSaldo", hallazgo.mensaje)
        self.assertIn("TABLE_NAME = 'Credito' AND COLUMN_NAME IN ('nSaldo', 'nMora')", hallazgo.consulta)

    def test_condicion_propone_la_reescritura(self):
        hallazgo = _isnull("SELECT a FROM dbo.Examen e WHERE ISNULL(e.bEvaluado, 0) = 0")[0]
        self.assertTrue(hallazgo.mensaje.endswith(
            "(si los acepta, se puede reescribir sin la función: (e.bEvaluado = 0 OR e.bEvaluado IS NULL))."))


class ConsultaTest(unittest.TestCase):
    def test_otra_base_y_sin_esquema(self):
        consulta = consulta_de_nulos([
            {"tabla": "dbo.Credito", "columna": "nSaldo"},
            {"tabla": "DBCMACICA.dbo.RHCargos", "columna": "cRHAreaCod"},
            {"tabla": "Agencia", "columna": "cNombre"},
        ])
        self.assertIn("FROM INFORMATION_SCHEMA.COLUMNS", consulta)
        self.assertIn("FROM DBCMACICA.INFORMATION_SCHEMA.COLUMNS", consulta)
        self.assertIn("(TABLE_NAME = 'Agencia' AND COLUMN_NAME IN ('cNombre'))", consulta)
        self.assertIn("\nUNION ALL\n", consulta)
        self.assertTrue(consulta.endswith("ORDER BY TABLE_NAME, COLUMN_NAME;"))


if __name__ == "__main__":
    unittest.main()
