"""«Caracteres especiales dañados» en Reportes y Negocio (texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
QUE_HACER = ("Se recomienda corregir los caracteres afectados y guardar el archivo con la codificación adecuada, para "
             "evitar que los textos se almacenen de forma incorrecta.")


def _danados(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "CARACTERES_DANADOS"]


class CaracteresDanadosTest(unittest.TestCase):
    def test_texto_de_la_usuaria(self):
        sql = ("EXEC InsMov_SP @cMovNro, '900098', 'Regularizaci�n de Cheque Intermoneda', 10\n"
               "EXEC InsMov_SP @cMovNro, '900099', 'Regularizaci�n de Transferencia Intermoneda', 10")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _danados(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertEqual(hallazgos[0].lineas, [1, 2])
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificaron caracteres dañados (�) en los textos 'Regularizaci�n de Cheque "
                    "Intermoneda' y 'Regularizaci�n de Transferencia Intermoneda', que se almacenarán de esa "
                    "manera en la base de datos. " + QUE_HACER,
                )

    def test_tilde_mal_leida_y_un_solo_texto(self):
        hallazgo = _danados("SELECT 'DepÃ³sito del aÃ±o' AS cGlosa", verificar_reporte)[0]
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificaron caracteres dañados (Ã³, Ã±) en el texto "
            "'DepÃ³sito del aÃ±o', que se almacenará de esa manera en la base de datos."))

    def test_lo_que_no_se_marca(self):
        for sql in (
            "SELECT 'Depósito del año', 'Señor', 'Árbol'",          # tildes y ñ bien escritas
            "-- DEP�SITO EN LOTE\nSELECT 1",                    # solo en un comentario: no se almacena
            "/* Regularizaci�n */ SELECT 1",
        ):
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(_danados(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
