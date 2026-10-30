"""Reportes: «Modificación de tabla física» resuelve el alias en su propia sentencia (aunque no haya «;»)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

REPORTE = """CREATE PROCEDURE dbo.PA_Colocaciones_Sel_Reporte
AS
BEGIN
    SELECT A.cCtaCod
    FROM DBCMACICA.dbo.colocacsaldo A WITH (NOLOCK)

    DELETE A
    FROM #colocacsaldo A
    WHERE A.nProducto IN (121,221)

    UPDATE A
    SET A.nSaldo = 0
    FROM #colocacsaldo A
    WHERE A.nSaldo < 0

    ;WITH CTE AS (
        SELECT nSaldo, ROW_NUMBER() OVER(ORDER BY nSaldo) AS nFila FROM #colocacsaldo
    )
    UPDATE CTE SET nSaldo = 1 WHERE nFila = 1
END
"""


def modificaciones(sql):
    return [h for h in verificar_reporte(sql) if h.regla == "MODIFICACION_TABLA_FISICA"]


class TestModificacionTablaFisica(unittest.TestCase):
    def test_alias_de_temporal_no_se_confunde_con_el_from_de_arriba(self):
        self.assertEqual(modificaciones(REPORTE), [])

    def test_alias_de_tabla_fisica_si_se_marca(self):
        sql = REPORTE.replace("DELETE A\n    FROM #colocacsaldo A", "DELETE A\n    FROM dbo.Colocacion A")
        hallazgos = modificaciones(sql)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("modifica la tabla dbo.Colocacion con DELETE", hallazgos[0].mensaje)

    def test_cte_sobre_tabla_fisica_si_se_marca(self):
        sql = REPORTE.replace("AS nFila FROM #colocacsaldo", "AS nFila FROM dbo.Colocacion")
        hallazgos = modificaciones(sql)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("dbo.Colocacion (mediante la CTE CTE)", hallazgos[0].mensaje)

    def test_update_con_case_resuelve_el_alias_en_el_from(self):
        # Caso de la usuaria: el END (y el ELSE) del CASE cortaban la sentencia antes del FROM #ReporteA R.
        sql = """    UPDATE R
    SET
        R.SaldoTCF = CASE
                        WHEN SUBSTRING(R.NroCredito, 9, 1) = '1'
                        THEN C.Saldo
                        ELSE ROUND(C.Saldo * DBCMACICA.DBO.FN_ObtenerTCFijoDiario(@DFECHA), 2)
                     END,
        R.Moneda   = CASE
                        WHEN SUBSTRING(R.NroCredito, 9, 1) = '1'
                        THEN 'SOLES'
                        ELSE 'DOLARES'
                     END
    FROM #ReporteA R
"""
        self.assertEqual(modificaciones(sql), [])
        hallazgos = modificaciones(sql.replace("FROM #ReporteA R", "FROM dbo.Reporte R"))
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("modifica la tabla dbo.Reporte con UPDATE", hallazgos[0].mensaje)

    def test_observacion_agrupada_trae_sus_lineas_para_recorrerlas(self):
        sql = "SELECT a FROM #A ORDER BY 1;\nSELECT b FROM #B ORDER BY 1;\nSELECT c FROM #C ORDER BY 1;\n"
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            agrupadas = [h for h in verificar(sql) if len(getattr(h, "lineas", None) or []) > 1]
            self.assertTrue(agrupadas, verificar.__name__)


if __name__ == "__main__":
    unittest.main()
