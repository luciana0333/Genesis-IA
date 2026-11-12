"""«Palabra repetida en la descripción» en los dos diccionarios (caso de la usuaria, 11 nov.: «repositorio de de RRHH»).

Texto directo de la usuaria y UNA sola observación con todas las repeticiones del diccionario.
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.palabra_repetida import palabras_repetidas

_PA = ("CREATE PROCEDURE dbo.PA_RHCargosTabla_Sel_ObtenerCargosNuevos\n    @cRHAreaCod VARCHAR(10)\nAS\nBEGIN\n"
       "    SELECT 1;\nEND")


def _dicc_pa(descripcion, parametro="Código del área de recursos humanos"):
    return (f"EXEC SP_ADDEXTENDEDPROPERTY \n\t@name=N'MS_Description', \n\t@value=N'{descripcion}', \n"
            f"\t@level0type=N'SCHEMA', @level0name=N'DBO', \n"
            f"\t@level1type=N'PROCEDURE', @level1name=N'PA_RHCargosTabla_Sel_ObtenerCargosNuevos'\n"
            f"EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'{parametro}', "
            f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', "
            f"@level1name=N'PA_RHCargosTabla_Sel_ObtenerCargosNuevos', @level2type=N'PARAMETER', "
            f"@level2name=N'@cRHAreaCod'")


_SU_DESCRIPCION = ("Procedimiento encargado de obtener los cargos que no se encuentran en el repositorio de de "
                   "RRHH.EstructuraCAPDetalle")


def _repetidas(hallazgos):
    return [h for h in hallazgos if h.regla == "PALABRA_REPETIDA"]


class PalabraRepetidaTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        hallazgos = _repetidas(verificar_diccionario(_PA, _dicc_pa(_SU_DESCRIPCION)))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "bajo")
        self.assertEqual(hallazgos[0].linea, 3)  # la línea del @value
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó la palabra repetida «de de» en la descripción del diccionario. Se recomienda corregir la "
            "descripción eliminando la palabra repetida, ya que genera redundancia.",
        )

    def test_dos_en_la_misma_descripcion(self):
        hallazgo = _repetidas(verificar_diccionario(_PA, _dicc_pa("Procedimiento que que obtiene los del del cargos")))[0]
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificaron palabras repetidas en la descripción del diccionario: «que que» y «del del». Se "
            "recomienda corregir la descripción eliminando las palabras repetidas, ya que generan redundancia.",
        )

    def test_varias_descripciones_en_una_sola_observacion(self):
        hallazgos = _repetidas(verificar_diccionario(
            _PA, _dicc_pa(_SU_DESCRIPCION, "Código del del área de recursos humanos")))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].lineas, [3, 6])  # el @value de cada descripción
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificaron palabras repetidas en las descripciones del diccionario: «de de» y «del del». Se "
            "recomienda corregir las descripciones eliminando las palabras repetidas, ya que generan redundancia.",
        )

    def test_misma_repeticion_en_dos_descripciones_se_nombra_una_vez(self):
        hallazgo = _repetidas(verificar_diccionario(_PA, _dicc_pa(_SU_DESCRIPCION, "Código de de área")))[0]
        self.assertEqual(hallazgo.mensaje.count("«de de»"), 1)
        self.assertIn("las descripciones del diccionario", hallazgo.mensaje)

    def test_diccionario_de_tablas_columna_y_tabla(self):
        tabla = "CREATE TABLE dbo.Cargo (\n nCargoId INT NOT NULL,\n cNombre VARCHAR(50) NULL\n)"
        diccionario = (
            "EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'Tabla que que guarda los cargos', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cargo'\n"
            "EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'Identificador del cargo', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cargo', "
            "@level2type=N'COLUMN', @level2name=N'nCargoId'\n"
            "EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'Nombre del del cargo', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cargo', "
            "@level2type=N'COLUMN', @level2name=N'cNombre'")
        hallazgos = _repetidas(verificar_diccionario_tablas(tabla, diccionario))
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "bajo")
        self.assertIn("en las descripciones del diccionario: «que que» y «del del».", hallazgos[0].mensaje)

    def test_que_detecta_y_que_no(self):
        self.assertEqual(palabras_repetidas("El el monto"), ["El el"])
        self.assertEqual(palabras_repetidas("Indica que que el valor de de la tasa"), ["que que", "de de"])
        for texto in ("Monto 1 1 total",                 # números
                      "Código del cliente",              # sin repetición
                      "nana banana",                     # parte de otra palabra
                      "Lee la tabla RRHH.de de",          # parte de un nombre con punto
                      "Columna cod_de de x"):              # parte de un nombre con guion bajo
            with self.subTest(texto=texto):
                self.assertEqual(palabras_repetidas(texto), [])


if __name__ == "__main__":
    unittest.main()
