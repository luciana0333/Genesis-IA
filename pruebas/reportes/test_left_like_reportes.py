"""Reportes, LEFT que puede reemplazarse por LIKE (2 nov.): la misma regla de Negocio (módulo compartido left_like)."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte


def _left(cuerpo: str):
    sql = ("CREATE PROCEDURE dbo.PA_GDD_Cuenta_Sel_Resumen\n    @pcPrefijo VARCHAR(5)\nAS\nBEGIN\n"
           f"{cuerpo}\nEND")
    return [h for h in verificar_reporte(sql) if h.regla == "LEFT_REEMPLAZABLE_POR_LIKE"]


class LeftLikeEnReportesTest(unittest.TestCase):
    def test_se_observa_con_el_mismo_texto_de_negocio(self):
        hallazgos = _left("    SELECT cCtaCod FROM dbo.Producto WITH (NOLOCK)\n    WHERE LEFT(cCtaCod, 5) = '10901'")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "medio")
        self.assertEqual(hallazgos[0].linea, 6)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó el uso de LEFT(cCtaCod, 5) = '10901' en una condición. Se recomienda evaluar el "
            "reemplazo de LEFT() por LIKE (ejemplo: cCtaCod LIKE '10901%'), permitiendo aprovechar los índices de "
            "la columna y mejorar el rendimiento de la consulta.",
        )

    def test_substring_in_y_parametro(self):
        casos = {
            "WHERE SUBSTRING(cCtaCod, 1, 5) = '10901'": "de SUBSTRING() por LIKE (ejemplo: cCtaCod LIKE '10901%'),",
            "WHERE LEFT(cCtaCod, 5) IN ('10901', '10902')": "(ejemplo: cCtaCod LIKE '10901%' OR cCtaCod LIKE '10902%'),",
            "WHERE LEFT(cCtaCod, 5) = @pcPrefijo": "(ejemplo: cCtaCod LIKE @pcPrefijo + '%'),",
        }
        for filtro, sugerencia in casos.items():
            with self.subTest(filtro=filtro):
                hallazgos = _left(f"    SELECT cCtaCod FROM dbo.Producto WITH (NOLOCK)\n    {filtro}")
                self.assertEqual(len(hallazgos), 1)
                self.assertIn(sugerencia, hallazgos[0].mensaje)

    def test_no_se_marca_cuando_like_no_aplica(self):
        for cuerpo in (
            "    SELECT cCtaCod FROM dbo.Producto WITH (NOLOCK) WHERE LEFT(cCtaCod, 5) = '109'",
            "    SELECT CASE WHEN LEFT(cCtaCod, 1) = '1' THEN 1 ELSE 0 END FROM dbo.Producto WITH (NOLOCK)",
            "    DECLARE @cMoneda CHAR(1)\n    SELECT @cMoneda = LEFT(cCtaCod, 1) FROM dbo.Producto WITH (NOLOCK)",
            "    -- WHERE LEFT(cCtaCod, 5) = '10901'\n    SELECT 1",
        ):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(_left(cuerpo), [])


if __name__ == "__main__":
    unittest.main()
