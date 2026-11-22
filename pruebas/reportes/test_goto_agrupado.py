"""Reportes: con dos GOTO aún salía «Se encontraron 2 observaciones de este tipo» (usuaria, 22 nov.)."""
import unittest

from app.analizadores.analizador_reportes import verificar_reporte

_DOS_GOTO = ("CREATE PROCEDURE dbo.PA_Rpt_X AS\nBEGIN\n IF 1=1 GOTO Fin\n IF 2=2 GOTO Salir\n Fin:\n SELECT 1\n"
             " Salir:\n SELECT 2\nEND")


class GotoAgrupadoReportes(unittest.TestCase):
    def test_dos_goto_una_frase(self):
        goto = [h for h in verificar_reporte(_DOS_GOTO) if h.regla == "GOTO_PROHIBIDO"]
        self.assertEqual(len(goto), 1)
        self.assertTrue(goto[0].mensaje.startswith(
            "Se identificaron instrucciones GOTO hacia las etiquetas Fin y Salir. Se recomienda evitar el uso de GOTO"),
            goto[0].mensaje)
        self.assertEqual(goto[0].lineas, [3, 4])


if __name__ == "__main__":
    unittest.main()
