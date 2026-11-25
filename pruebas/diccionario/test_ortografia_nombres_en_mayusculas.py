"""Nombres de tablas en mayúsculas dentro de una descripción no son errores de escritura (usuaria, 24 nov.).

Caso real (diccionario de 5 PA de conciliación): «IDENTIFICADOR DE LA TABLA NETTIPOCONCILIACION» y «… SU DETALLE EN
NETLOGCONCILIACION Y NETLOGCONCILIACIONDET» salían como «palabras mal escritas (revisar)».
Regla: en mayúsculas, 12 letras o más, sin corrección del corrector y con una palabra válida de 6 o más letras
adentro. Los errores reales tienen corrección y se siguen marcando.
"""
import unittest

from app.analizadores import ortografia
from app.analizadores.ortografia import palabras_mal_escritas


@unittest.skipUnless(ortografia.disponible(), "Esta PC no tiene el corrector instalado.")
class NombresEnMayusculas(unittest.TestCase):
    def test_nombres_de_tabla_no_se_marcan(self):
        casos = [
            "PROCEDIMIENTO QUE INSERTA EL ARCHIVO LOG DE OPERACIONES ELECTRONICAS Y SU DETALLE EN NETLOGCONCILIACION "
            "Y NETLOGCONCILIACIONDET",
            "IDENTIFICADOR DE LA TABLA NETTIPOCONCILIACION",
            "IDENTIFICADOR DE LA TABLA NETARCHIVOCONCILIACION",
        ]
        for texto in casos:
            with self.subTest(texto):
                self.assertEqual(palabras_mal_escritas(texto), [])

    def test_errores_reales_se_siguen_marcando(self):
        casos = {
            "FECHA DE LA CONCILIASION DEL ARCHIVO": ["CONCILIASION"],
            "INDICA EL PROCEDIMEINTO DEL CLIENTESS": ["PROCEDIMEINTO", "CLIENTESS"],
            "CONSULTA LA ROJSH DEL CLIENTE": ["ROJSH"],
            "DESCRIPSIONES DE LAS TRANSACCIONESS DEL CLIENTE": ["DESCRIPSIONES", "TRANSACCIONESS"],
        }
        for texto, esperadas in casos.items():
            with self.subTest(texto):
                self.assertEqual([palabra for palabra, _ in palabras_mal_escritas(texto)], esperadas)

    def test_solo_aplica_a_mayusculas_largas(self):
        self.assertFalse(ortografia._parece_nombre_en_mayusculas("NETCONCILIA"))  # menos de 12 letras
        self.assertFalse(ortografia._parece_nombre_en_mayusculas("Netlogconciliacion"))  # no todo en mayúsculas
        self.assertTrue(ortografia._parece_nombre_en_mayusculas("NETTIPOCONCILIACION"))


if __name__ == "__main__":
    unittest.main()
