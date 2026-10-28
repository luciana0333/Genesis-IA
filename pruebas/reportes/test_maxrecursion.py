"""MAXRECURSION sigue sin permitirse en Reportes, pero con su propio título."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


class MaxrecursionTest(unittest.TestCase):
    def test_maxrecursion_tiene_su_propia_observacion(self):
        sql = "WITH M AS (SELECT 1 n) SELECT n FROM M OPTION (MAXRECURSION 0)"
        hallazgos = [h for h in verificar_reporte(sql) if "MAXRECURSION" in h.mensaje]
        self.assertEqual([h.regla for h in hallazgos], ["MAXRECURSION_PROHIBIDO"])
        self.assertEqual(hallazgos[0].severidad.value, "alto")

    def test_los_demas_hints_siguen_igual(self):
        reglas = {h.regla for h in verificar_reporte("SELECT 1 FROM T WITH(NOLOCK) OPTION (RECOMPILE)")}
        self.assertIn("HINT_PLAN_PROHIBIDO", reglas)
        self.assertNotIn("MAXRECURSION_PROHIBIDO", reglas)


if __name__ == "__main__":
    unittest.main()
