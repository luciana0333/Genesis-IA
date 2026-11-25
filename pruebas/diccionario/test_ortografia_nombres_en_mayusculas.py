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


FIRMAS = ("ALTER PROCEDURE [dbo].[PA_NET_INSERTA_LOG_TRANSACCIONES] (@PAGENCIA VARCHAR(4), @DETALLE XML)\n"
          "ALTER PROCEDURE [dbo].[PA_NET_InsertaDataFullCarga] (@pTipoConciliacion INT, @pTipoArchivoConciliacion INT)")


@unittest.skipUnless(ortografia.disponible(), "Esta PC no tiene el corrector instalado.")
class NombresArmadosConElScript(unittest.TestCase):
    """Idea de la usuaria (24 nov.): las piezas de los nombres del script (PA_NET_…, @pTipoConciliacion) arman los
    nombres de tabla de las descripciones. Va junto con la regla de la forma de la palabra."""

    def test_piezas_del_script(self):
        piezas = ortografia.vocabulario_de_nombres(FIRMAS)
        self.assertTrue({"NET", "LOG", "TIPO", "CONCILIACION", "ARCHIVO", "DETALLE", "INSERTA"} <= piezas)

    def test_se_arman_con_piezas_y_abreviaturas(self):
        with ortografia.usar_nombres_del_script(FIRMAS):
            for palabra in ("NETLOGCONCILIACION", "NETTIPOCONCILIACION", "NETARCHIVOCONCILIACION",
                            "NETLOGCONCILIACIONDET"):  # DET: abreviatura de DETALLE
                with self.subTest(palabra):
                    self.assertTrue(ortografia._armada_con_nombres_del_script(palabra))
            for palabra in ("CONCILIASION", "INFORMASIONDEL", "CONCILIACIONN", "NET"):
                with self.subTest(palabra):
                    self.assertFalse(ortografia._armada_con_nombres_del_script(palabra))

    def test_fuera_del_script_no_aplica(self):
        self.assertFalse(ortografia._armada_con_nombres_del_script("NETTIPOCONCILIACION"))

    def test_en_el_diccionario_real(self):
        from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
        diccionario = ("EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'IDENTIFICADOR DE LA TABLA "
                       "NETTIPOCONCILIACION Y SU DETALLE EN NETLOGCONCILIACIONDET', @level0type=N'schema', "
                       "@level0name=N'dbo', @level1type=N'PROCEDURE', @level1name=N'PA_NET_InsertaDataFullCarga', "
                       "@level2type=N'PARAMETER', @level2name=N'@pTipoConciliacion'")
        reglas = [h.regla for h in verificar_diccionario(FIRMAS, diccionario)]
        self.assertNotIn("ERROR_ORTOGRAFICO", reglas)


if __name__ == "__main__":
    unittest.main()
