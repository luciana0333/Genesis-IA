"""«Palabra repetida en la descripción» en los dos diccionarios (caso de la usuaria, 11 nov.: «repositorio de de RRHH»)."""

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
            "Se identificó la palabra «de» repetida en la descripción del procedimiento "
            "dbo.PA_RHCargosTabla_Sel_ObtenerCargosNuevos («…el repositorio de de RRHH.EstructuraCAPDetalle»). Se "
            "recomienda corregir la descripción, ya que la palabra repetida afecta la claridad de la documentación.",
        )

    def test_en_el_procedimiento_y_en_un_parametro_va_en_una_observacion(self):
        hallazgos = _repetidas(verificar_diccionario(
            _PA, _dicc_pa(_SU_DESCRIPCION, "Código del del área de recursos humanos")))
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("Se identificaron 2 descripciones con palabras repetidas", hallazgos[0].mensaje)
        self.assertIn("parámetro @cRHAreaCod: «Código del del área…»", hallazgos[0].mensaje)

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
        self.assertIn("tabla dbo.Cargo", hallazgos[0].mensaje)
        self.assertIn("columna cNombre: «Nombre del del cargo»", hallazgos[0].mensaje)

    def test_que_detecta_y_que_no(self):
        self.assertEqual(palabras_repetidas("El el monto"), [("el", "El el monto")])
        self.assertEqual([p for p, _ in palabras_repetidas("Indica que que el valor de de la tasa")], ["que", "de"])
        for texto in ("Monto 1 1 total",                 # números
                      "Código del cliente",              # sin repetición
                      "nana banana",                     # parte de otra palabra
                      "Lee la tabla RRHH.de de",          # parte de un nombre con punto
                      "Columna cod_de de x"):              # parte de un nombre con guion bajo
            with self.subTest(texto=texto):
                self.assertEqual(palabras_repetidas(texto), [])


if __name__ == "__main__":
    unittest.main()
