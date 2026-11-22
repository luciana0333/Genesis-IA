"""Diccionarios: el mismo error en varias sentencias sale una vez, sin «Se encontraron N observaciones de este tipo»
(usuaria, 22 nov.)."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.diccionario_agrupar import agrupar
from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad

_TABLA = "CREATE TABLE CLICKTOPAY.Cliente (\n nClienteId INT NOT NULL,\n cNombre VARCHAR(50) NOT NULL\n)"


def _dicc(esquema, nombre, columna=None, descripcion="Tabla que almacena los clientes"):
    texto = (f"EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'{descripcion}', @level0type=N'SCHEMA', "
             f"@level0name=N'{esquema}', @level1type=N'TABLE', @level1name=N'{nombre}'")
    if columna:
        texto += f", @level2type=N'COLUMN', @level2name=N'{columna}'"
    return texto + "\n"


class AgrupadoSinRepetirTest(unittest.TestCase):
    def test_el_mismo_esquema_equivocado_en_todas_las_sentencias(self):
        diccionario = (_dicc("DBO", "Cliente") + _dicc("DBO", "Cliente", "nClienteId", "Identificador del cliente")
                       + _dicc("DBO", "Cliente", "cNombre", "Nombre del cliente"))
        esquema = [h for h in verificar_diccionario_tablas(_TABLA, diccionario) if h.regla == "ESQUEMA_NO_COINCIDE"]
        self.assertEqual(len(esquema), 1)
        self.assertTrue(esquema[0].mensaje.startswith(
            "El diccionario indica el esquema 'DBO', pero la tabla está en 'CLICKTOPAY'."), esquema[0].mensaje)
        self.assertNotIn("Se encontraron", esquema[0].mensaje)
        self.assertEqual(esquema[0].lineas, [1, 2, 3])

    def test_valores_distintos_en_una_sola_frase(self):
        def hallazgo(linea, valor):
            return Hallazgo(linea=linea, origen=OrigenAnalisis.DICCIONARIO, severidad=Severidad.ALTO,
                            regla="ESQUEMA_NO_COINCIDE",
                            mensaje=f"El diccionario indica el esquema '{valor}', pero la tabla está en 'CLICKTOPAY'. "
                                    f"Corregir el esquema en el diccionario por 'CLICKTOPAY'.")
        resultado = agrupar([hallazgo(1, "DBO"), hallazgo(5, "VENTAS"), hallazgo(9, "DBO")], {})
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].mensaje,
                         "El diccionario indica los esquemas 'DBO' y 'VENTAS', pero la tabla está en 'CLICKTOPAY'. "
                         "Corregir el esquema en el diccionario por 'CLICKTOPAY'.")
        self.assertEqual(resultado[0].lineas, [1, 5, 9])

    def test_nombre_de_procedimiento_repetido_una_vez(self):
        pa = "CREATE PROCEDURE dbo.PA_Cliente_Sel_Datos\n @nClienteId INT\nAS\nSELECT 1"
        diccionario = (
            "EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'Procedimiento que consulta clientes', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Sel_Dato'\n"
            "EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'Identificador del cliente', "
            "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Sel_Dato', "
            "@level2type=N'PARAMETER', @level2name=N'@nClienteId'\n")
        nombre = [h for h in verificar_diccionario(pa, diccionario) if h.regla == "NOMBRE_NO_COINCIDE"]
        self.assertEqual(len(nombre), 1)
        self.assertNotIn("Se encontraron", nombre[0].mensaje)
        self.assertIn("'PA_Cliente_Sel_Dato'", nombre[0].mensaje)


if __name__ == "__main__":
    unittest.main()
