"""«Variables de tabla declaradas sin uso» en Reportes y Negocio (texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _sin_uso(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "VARIABLE_TABLA_SIN_USO"]


class VariablesTablaSinUsoTest(unittest.TestCase):
    def test_texto_de_la_usuaria(self):
        sql = ("DECLARE @CtasTmp TABLE (Id INT)\nINSERT INTO @CtasTmp SELECT 1\nSELECT Id FROM @CtasTmp\n"
               "Declare @TEstadoEmergencia TABLE (Id INT)\n"                # 4
               "Declare @TSuspensionPerfecta TABLE (Id INT)")                 # 5
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _sin_uso(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "bajo")
                self.assertEqual(hallazgos[0].lineas, [4, 5])
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que las siguientes variables de tipo tabla están declaradas en el procedimiento, "
                    "pero no se utilizan en ninguna parte del código: @TEstadoEmergencia; @TSuspensionPerfecta. Se "
                    "recomienda verificar si estas variables son necesarias y, de no ser así, retirar sus declaraciones "
                    "para evitar código innecesario.",
                )

    def test_una_sola_en_singular_y_solo_llenada_cuenta_como_sin_uso(self):
        hallazgo = _sin_uso("DECLARE @T TABLE (n INT)\nINSERT INTO @T SELECT 1\nUPDATE A SET A.n = 2 FROM @T A",
                            verificar_reporte)[0]
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificó que la variable de tipo tabla @T está declarada en el procedimiento, pero no se utiliza "
            "en ninguna parte del código. Se recomienda verificar si esta variable es necesaria"))

    def test_lo_que_no_se_marca(self):
        for sql in (
            "DECLARE @T TABLE (n INT)\nINSERT INTO @T SELECT 1\nSELECT n FROM @T",
            "DECLARE @T TABLE (n INT)\nIF EXISTS (SELECT 1 FROM @T) PRINT 1",
            "DECLARE @T TABLE (n INT)\nUPDATE B SET B.x = A.n FROM dbo.X B JOIN @T A ON A.n = B.n",
            "DECLARE @n INT\nSELECT 1",                                   # variable común: es otra regla
            "DECLARE @T TABLE (n INT)\n-- SELECT * FROM @T",              # en un comentario no cuenta... pero se marca
        ):
            for verificar in MODULOS:
                with self.subTest(sql=sql[:50], modulo=verificar.__name__):
                    esperado = 1 if "-- SELECT" in sql else 0
                    self.assertEqual(len(_sin_uso(sql, verificar)), esperado)


if __name__ == "__main__":
    unittest.main()
