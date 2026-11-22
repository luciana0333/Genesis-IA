"""Encabezado con una etiqueta mal escrita (usuaria, 22 nov.): «DESCRPICION: VALORIZA EL CHEQUE…».

El dato está, solo mal rotulado: no se dice que falta. Se avisa en la misma observación de encabezado, que es de
severidad baja («muy secundario»: no rompe el flujo ni impacta la base).
"""
import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)
CUERPO = "CREATE PROCEDURE dbo.PA_Valoriza_Cheque @x INT\nAS\nBEGIN\n    SELECT 1\nEND"
HISTORIAL = "Control de Cambios:\nFecha\t\tAutor\tDescripción\n2016.11.18\tBJMS\tse cambio el calculo\n"


def _encabezado(cabecera, verificar):
    hallazgos = [h for h in verificar(f"/*\n{cabecera}*/\n{CUERPO}") if h.regla == "ENCABEZADO_PROCEDIMIENTO"]
    return hallazgos


class EtiquetaMalEscrita(unittest.TestCase):
    def test_caso_real_con_otros_datos_faltantes(self):
        cabecera = ("FECHA:2014-08-07\nAUTOR:GRSH\nDESCRPICION:VALORIZA EL CHEQUE SI ES QUE EL PLAZO SE HA CUMPLIDO\n"
                    + HISTORIAL)
        for verificar in MODULOS:
            with self.subTest(verificar.__name__):
                h = _encabezado(cabecera, verificar)[0]
                self.assertEqual(h.severidad.value, "bajo")
                self.assertEqual(h.mensaje,
                                 "Se identificó que el encabezado del procedimiento no indica el nombre del "
                                 "procedimiento ni el ejemplo de ejecución (EXEC). Además, la etiqueta DESCRPICION "
                                 "parece mal escrita (¿Descripción?). Se recomienda completar los datos del "
                                 "encabezado, ya que permiten identificar su propósito y facilitan su mantenimiento.")

    def test_solo_la_etiqueta_mal_escrita(self):
        cabecera = ("NOMBRE: dbo.PA_Valoriza_Cheque\nFECHA:2014-08-07\nAUTOR:GRSH\nDESCRPICION:VALORIZA EL CHEQUE\n"
                    + HISTORIAL + "EXEC dbo.PA_Valoriza_Cheque 1\n")
        h = _encabezado(cabecera, verificar_procedimiento_normal)[0]
        self.assertEqual(h.mensaje, "Se identificó que en el encabezado la etiqueta DESCRPICION parece mal escrita "
                                    "(¿Descripción?). Se recomienda corregir la etiqueta, ya que el encabezado debe ser "
                                    "claro para quien mantenga el procedimiento.")

    def test_variante_bien_escrita_no_se_observa(self):
        cabecera = ("NOMBRE: dbo.PA_Valoriza_Cheque\nFECHAS: 2014-08-07\nAUTOR:GRSH\nDESCRIPCIÓN: VALORIZA EL CHEQUE\n"
                    + HISTORIAL + "EXEC dbo.PA_Valoriza_Cheque 1\n")
        self.assertEqual(_encabezado(cabecera, verificar_procedimiento_normal), [])

    def test_palabra_distinta_no_se_toma_como_mal_escrita(self):
        # «DESTINO» no se parece a «Descripción»: la descripción sigue faltando.
        cabecera = "NOMBRE: dbo.PA_X\nFECHA:2014-08-07\nAUTOR:GRSH\nDESTINO: AGENCIAS\n" + HISTORIAL + "EXEC dbo.PA_X 1\n"
        h = _encabezado(cabecera, verificar_procedimiento_normal)[0]
        self.assertIn("no indica la descripción", h.mensaje)
        self.assertNotIn("mal escrita", h.mensaje)


if __name__ == "__main__":
    unittest.main()
