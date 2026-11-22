"""NOLOCK en subconsulta de UPDATE: un SET @variable después del UPDATE es otra sentencia (usuaria, 21 nov.).

Caso real (FluGenSol_InsPropuesta_SP, MICROSEGURO.Microseguro): sin ';', el «SET @dFechaVencAnualAP = (SELECT …
WITH (NOLOCK))» se tomaba como subconsulta del UPDATE anterior.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal

REGLAS = {"NOLOCK_EN_SUBCONSULTA_DE_UPDATE", "NOLOCK_EN_TABLA_FISICA"}


def _nolock(sql):
    return [h for h in verificar_procedimiento_normal(sql) if h.regla in REGLAS]


class NolockSetTrasUpdateTest(unittest.TestCase):
    def test_set_de_variable_despues_del_update_no_se_marca(self):
        sql = ("UPDATE MICROSEGURO.Microseguro SET\n"
               "    nEstadoCertificado = 2001,\n"
               "    dFechaAfiliacion = @dFechaSistema\n"
               "WHERE cNroCertificado = @cNroCertificadoMSAP\n"
               "--obteniendo la fecha de vencimiento en caso sea plan anual\n"
               "Set @dFechaVencAnualAP = (select dateadd(month,12,dFechaAfiliacion) from MICROSEGURO.Microseguro "
               "with(nolock) where cNroCertificado = @cNroCertificadoMSAP and nTipoPlan = 2)")
        self.assertEqual(_nolock(sql), [])

    def test_la_subconsulta_del_update_sigue_marcandose(self):
        sql = ("UPDATE MICROSEGURO.Microseguro\n"
               "SET nEstadoCertificado = 2001\n"
               "WHERE cNroCertificado = (SELECT TOP 1 cNroCertificado FROM MICROSEGURO.Microseguro WITH (NOLOCK) "
               "WHERE cCtaCod = @cCtaCod)\n"
               "SET @n = 1")
        self.assertEqual([h.regla for h in _nolock(sql)], ["NOLOCK_EN_SUBCONSULTA_DE_UPDATE"])

    def test_nolock_en_la_tabla_que_se_actualiza_sigue_marcandose(self):
        sql = ("UPDATE A\nSET A.n = 1\nFROM dbo.Credito A WITH (NOLOCK)\nWHERE A.cCtaCod = @c\n"
               "SET @d = (SELECT MAX(n) FROM dbo.Credito WITH (NOLOCK))")
        self.assertEqual([h.regla for h in _nolock(sql)], ["NOLOCK_EN_TABLA_FISICA"])


if __name__ == "__main__":
    unittest.main()
