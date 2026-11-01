"""Reportes, uso de GOTO (1 nov.): igual que el WHILE, solo en un procedimiento nuevo (CREATE)."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte

_CUERPO = ("\nAS\nBEGIN\n    DECLARE @nIntento INT = 0\nREINTENTAR:\n    SET @nIntento = @nIntento + 1\n"
           "    IF @nIntento < 3\n        GOTO REINTENTAR\n    SELECT @nIntento\nEND")


def _goto(verbo: str, cuerpo: str = _CUERPO):
    sql = f"{verbo} PROCEDURE dbo.PA_GDD_Cliente_Sel_Resumen" + cuerpo
    return [h for h in verificar_reporte(sql) if h.regla == "GOTO_PROHIBIDO"]


class GotoEnReportesTest(unittest.TestCase):
    def test_create_se_observa_con_el_texto_de_la_usuaria(self):
        hallazgos = _goto("CREATE")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "medio")
        self.assertEqual(hallazgos[0].linea, 8)
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó una instrucción GOTO hacia la etiqueta REINTENTAR. Se recomienda evitar el uso de GOTO, "
            "ya que altera el flujo de ejecución y dificulta la lectura, el mantenimiento y la depuración del "
            "procedimiento. Se sugiere evaluar alternativas de control de flujo.",
        )

    def test_create_or_alter_cuenta_como_create(self):
        self.assertEqual(len(_goto("CREATE OR ALTER")), 1)

    def test_alter_no_se_observa(self):
        self.assertEqual(_goto("ALTER"), [])

    def test_goto_comentado_o_en_un_texto_no_se_observa(self):
        cuerpo = ("\nAS\nBEGIN\n    -- GOTO Fin\n    /* GOTO Inicio */\n"
                  "    SELECT 'No usar GOTO' AS cMensaje\nEND")
        self.assertEqual(_goto("CREATE", cuerpo), [])


if __name__ == "__main__":
    unittest.main()
