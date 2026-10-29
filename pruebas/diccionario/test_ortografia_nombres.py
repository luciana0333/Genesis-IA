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


class AbreviaturasYCompuestasEnDescripcionesTest(unittest.TestCase):
    def test_palabras_del_nombre_documentado_no_se_marcan(self):
        from app.analizadores.ortografia import palabras_mal_escritas
        self.assertEqual(palabras_mal_escritas("Código de la Trx registrada.", {"@cCodTrx"}), [])
        self.assertEqual(palabras_mal_escritas("Identificador del microservicio.", {"@nMicroservicioId"}), [])

    def test_sin_vocales_es_abreviatura_y_prefijos_compuestos(self):
        from app.analizadores.ortografia import palabras_mal_escritas
        self.assertEqual(palabras_mal_escritas("Código Trx del registro Nro"), [])
        self.assertEqual(palabras_mal_escritas("Operación interbancaria multimoneda del microservicio"), [])

    def test_los_errores_reales_se_siguen_marcando(self):
        from app.analizadores.ortografia import palabras_mal_escritas
        self.assertEqual(palabras_mal_escritas("Código de la trasaccion", {"@cCodTrx"}),
                         [("trasaccion", ["transacción"])])
