"""Ortografía dentro de nombres de columnas y parámetros, y sugerencias con letras faltantes."""

import unittest

from app.analizadores.ortografia import errores_en_nombre, sugerencias


class OrtografiaEnNombresTest(unittest.TestCase):
    def test_detecta_palabras_mal_escritas(self):
        self.assertEqual(errores_en_nombre("@cCorreoDestinario"), [("Destinario", ["Destinatario"])])
        self.assertEqual(errores_en_nombre("bActivoo"), [("Activoo", ["Activo"])])
        self.assertEqual(errores_en_nombre("dFechaRegsitro"), [("Regsitro", ["Registro"])])

    def test_abreviaturas_siglas_y_nombres_correctos_no_se_marcan(self):
        for nombre in ("nNumGarant", "cPersCodUsuario", "cCtaCod", "nTEAMinima", "nEnvioOpcionalEECCFisico",
                       "cCorrelacionIdTestimonio", "nSeguroDesgravamenMensual", "nTasaMoratorioAnual", "@jData",
                       "@profile_name", "@recipients"):
            with self.subTest(nombre=nombre):
                self.assertEqual(errores_en_nombre(nombre), [])


class SugerenciasTest(unittest.TestCase):
    def test_errores_tipicos(self):
        casos = {
            "Destinario": "Destinatario", "vencdos": "vencidos", "Cdigo": "Código", "clinete": "cliente",
            "logisitica": "logística", "descripcon": "descripción", "movimeinto": "movimiento",
            "garnatia": "garantía", "prestmo": "préstamo", "Desactiba": "Desactiva", "disponivle": "disponible",
        }
        for escrita, esperada in casos.items():
            with self.subTest(escrita=escrita):
                self.assertEqual(sugerencias(escrita), [esperada])


if __name__ == "__main__":
    unittest.main()
