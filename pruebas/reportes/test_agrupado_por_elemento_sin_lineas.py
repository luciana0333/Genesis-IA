"""Reportes: SELECT INTO y SELECT * agrupados sin «en las líneas …» en el texto (usuaria, 21 nov.)."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


class AgrupadoPorElementoSinLineasTest(unittest.TestCase):
    def test_select_into_agrupado(self):
        sql = ("SELECT a INTO #A FROM dbo.T WITH (NOLOCK)\nSELECT b INTO #B FROM dbo.T WITH (NOLOCK)\n"
               "SELECT a FROM #A\nSELECT b FROM #B")
        hallazgo = [h for h in verificar_reporte(sql) if h.regla == "SELECT_INTO_PROHIBIDO"][0]
        self.assertTrue(hallazgo.mensaje.startswith("Se identificaron 2 tablas creadas con SELECT INTO: #A; #B. "))
        self.assertNotIn("línea", hallazgo.mensaje)
        self.assertEqual(hallazgo.lineas, [1, 2])


if __name__ == "__main__":
    unittest.main()
