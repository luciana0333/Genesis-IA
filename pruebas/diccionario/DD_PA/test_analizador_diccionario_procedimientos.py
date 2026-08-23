import unittest

from app.analizadores.diccionario import verificar_diccionario
from pruebas.diccionario.DD_PA.casos.test_caso1_perfecto import PROCEDIMIENTO as PROC_1, DICCIONARIO as DIC_1
from pruebas.diccionario.DD_PA.casos.test_caso2_parametros_faltantes import PROCEDIMIENTO as PROC_2, DICCIONARIO as DIC_2
from pruebas.diccionario.DD_PA.casos.test_caso3_texto_invalido import PROCEDIMIENTO as PROC_3, DICCIONARIO as DIC_3
from pruebas.diccionario.DD_PA.casos.test_caso4_sin_descripcion_procedimiento import PROCEDIMIENTO as PROC_4, DICCIONARIO as DIC_4
from pruebas.diccionario.DD_PA.casos.test_caso5_sucio import PROCEDIMIENTO as PROC_5, DICCIONARIO as DIC_5


class TestDiccionarioProcedimientos(unittest.TestCase):
    def test_casos_historicos(self):
        casos = [
            ("caso_1_perfecto", PROC_1, DIC_1, 0),
            ("caso_2_parametros_faltantes", PROC_2, DIC_2, 2),
            ("caso_3_texto_invalido", PROC_3, DIC_3, 0),
            ("caso_4_sin_descripcion_procedimiento", PROC_4, DIC_4, 1),
            ("caso_5_sucio", PROC_5, DIC_5, 6),
        ]

        for nombre, procedimiento, diccionario, esperado in casos:
            with self.subTest(caso=nombre):
                hallazgos = verificar_diccionario(procedimiento, diccionario)
                self.assertEqual(
                    len(hallazgos),
                    esperado,
                    f"Caso {nombre} devolvio {len(hallazgos)} hallazgos; se esperaban {esperado}."
                )


if __name__ == "__main__":
    unittest.main()
