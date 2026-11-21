"""Observaciones agrupadas: las líneas van solo arriba de la observación, no en el texto (usuaria, 21 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal


class AgrupadoSinLineasTest(unittest.TestCase):
    def test_correo_repetido_sin_lineas_en_el_texto(self):
        sql = ("CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n"
               "EXEC msdb.dbo.sp_send_dbmail @recipients = 'a@b.pe', @body = 'x'\n"
               "SELECT 1\n"
               "EXEC msdb.dbo.sp_send_dbmail @recipients = 'c@d.pe', @body = 'y'\nEND")
        for verificar in (verificar_procedimiento_normal,):
            with self.subTest(modulo=verificar.__name__):
                correo = [h for h in verificar(sql) if h.regla == "ENVIO_CORREO_DESDE_BD"]
                self.assertEqual(len(correo), 1)
                self.assertTrue(correo[0].mensaje.startswith("Se encontraron 2 observaciones de este tipo: "))
                self.assertNotIn("línea", correo[0].mensaje)
                self.assertEqual(correo[0].lineas, [3, 5])


if __name__ == "__main__":
    unittest.main()
