"""«Dependencia con la base de datos BI» también en Reportes, igual que en Negocio (pedido de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.dependencia_bi import ACCION_DEPENDENCIA_BI


class DependenciaBiReportesTest(unittest.TestCase):
    def test_mismo_hallazgo_en_reportes_y_negocio(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS\nBEGIN\n"
               "    SELECT c.cCtaCod FROM BI.TABLON.CARTERACREDITOS c WITH (NOLOCK)\n"
               "    SELECT d.cCtaCod FROM [BI].[TABLON].[DESEMBOLSOS] d WITH (NOLOCK)\nEND")
        resultados = []
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            with self.subTest(modulo=verificar.__name__):
                hallazgos = [h for h in verificar(sql) if h.regla == "DEPENDENCIA_BASE_BI"]
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "alto")
                self.assertEqual(hallazgos[0].lineas, [3, 4])
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificaron 2 dependencias con la base de datos BI: BI.TABLON.CARTERACREDITOS; "
                    "[BI].[TABLON].[DESEMBOLSOS]. "))
                self.assertTrue(hallazgos[0].mensaje.endswith(ACCION_DEPENDENCIA_BI))
                resultados.append(hallazgos[0].mensaje)
        self.assertEqual(resultados[0], resultados[1])

    def test_alias_bi_no_es_la_base(self):
        sql = "SELECT bi.cCtaCod FROM dbo.Producto bi WITH (NOLOCK)"
        self.assertNotIn("DEPENDENCIA_BASE_BI", {h.regla for h in verificar_reporte(sql)})


if __name__ == "__main__":
    unittest.main()
