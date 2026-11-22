"""Diccionario: un objeto es su esquema y su nombre; un duplicado es todo igual (usuaria, 21 nov.).

Caso real: DUN.PA_PersRelaciones_Sel_ValidaInterviniente y COLOCACIONES.PA_PersRelaciones_Sel_ValidaInterviniente
en el mismo pase. Se tomaban como un solo procedimiento: «el esquema no coincide» y «documentación duplicada» (alto).
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

_PAS = ("CREATE PROCEDURE DUN.PA_Pers_Sel_Valida (\n @nOrigenId INT,\n @cJsonDatos VARCHAR(MAX)\n)\nAS\nSELECT 1\n"
        "CREATE PROCEDURE COLOCACIONES.PA_Pers_Sel_Valida (\n @cJsonDatos VARCHAR(MAX),\n @nCodError INT OUTPUT\n)\n"
        "AS\nSELECT 1\n")


def _add(esquema, objeto, descripcion, parametro=None, tipo="PROCEDURE", tipo2="PARAMETER"):
    texto = (f"EXEC sp_addextendedproperty @name = N'MS_Description', @value = N'{descripcion}', "
             f"@level0type = N'SCHEMA', @level0name = N'{esquema}', @level1type = N'{tipo}', @level1name = N'{objeto}'")
    if parametro:
        texto += f", @level2type = N'{tipo2}', @level2name = N'{parametro}'"
    return texto + "\n"


_DICCIONARIO = (
    _add("DUN", "PA_Pers_Sel_Valida", "Procedimiento almacenado encargado de validar los intervinientes")
    + _add("DUN", "PA_Pers_Sel_Valida", "Identificador del origen", "@nOrigenId")
    + _add("DUN", "PA_Pers_Sel_Valida", "Datos del crédito en formato JSON", "@cJsonDatos")
    + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Procedimiento almacenado encargado de validar las condiciones")
    + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Datos del crédito en formato JSON", "@cJsonDatos")
    + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Código de error de la validación", "@nCodError")
)


def _reglas(hallazgos):
    return {h.regla for h in hallazgos}


class MismoNombreOtroEsquemaTest(unittest.TestCase):
    def test_procedimientos_con_el_mismo_nombre_en_dos_esquemas(self):
        reglas = _reglas(verificar_diccionario(_PAS, _DICCIONARIO))
        self.assertNotIn("ESQUEMA_NO_COINCIDE", reglas)
        self.assertNotIn("DOCUMENTACION_DUPLICADA", reglas)

    def test_un_duplicado_de_verdad_se_sigue_marcando_sin_lineas_en_el_texto(self):
        repetido = _DICCIONARIO + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Otra vez", "@cJsonDatos")
        duplicados = [h for h in verificar_diccionario(_PAS, repetido) if h.regla == "DOCUMENTACION_DUPLICADA"]
        self.assertEqual(len(duplicados), 1)
        self.assertIn("@cJsonDatos", duplicados[0].mensaje)
        self.assertNotIn("línea", duplicados[0].mensaje)
        self.assertEqual(duplicados[0].lineas, [5, 7])

    def test_dos_duplicados_en_dos_procedimientos_sin_lineas_en_el_texto(self):
        repetido = (_DICCIONARIO + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Otra vez", "@cJsonDatos")
                    + _add("DUN", "PA_Pers_Sel_Valida", "Otra vez", "@nOrigenId"))
        duplicados = [h for h in verificar_diccionario(_PAS, repetido) if h.regla == "DOCUMENTACION_DUPLICADA"]
        self.assertEqual(len(duplicados), 1)
        self.assertTrue(duplicados[0].mensaje.startswith("Se identificaron 2 declaraciones duplicadas: "))
        self.assertNotIn("línea", duplicados[0].mensaje)

    def test_un_esquema_mal_escrito_se_sigue_marcando(self):
        pa = "CREATE PROCEDURE DUN.PA_Pers_Sel_Valida (\n @nOrigenId INT\n)\nAS\nSELECT 1\n"
        diccionario = (_add("COLOCACIONES", "PA_Pers_Sel_Valida", "Procedimiento almacenado encargado de validar")
                       + _add("COLOCACIONES", "PA_Pers_Sel_Valida", "Identificador del origen", "@nOrigenId"))
        self.assertIn("ESQUEMA_NO_COINCIDE", _reglas(verificar_diccionario(pa, diccionario)))

    def test_tablas_con_el_mismo_nombre_en_dos_esquemas(self):
        tablas = ("CREATE TABLE dbo.Cliente (\n nClienteId INT NOT NULL\n)\n"
                  "CREATE TABLE CRM.Cliente (\n nClienteId INT NOT NULL\n)\n")
        diccionario = "".join(
            _add(esquema, "Cliente", "Tabla que almacena los clientes", tipo="TABLE")
            + _add(esquema, "Cliente", "Identificador del cliente", "nClienteId", tipo="TABLE", tipo2="COLUMN")
            for esquema in ("dbo", "CRM"))
        reglas = _reglas(verificar_diccionario_tablas(tablas, diccionario))
        self.assertNotIn("ESQUEMA_NO_COINCIDE", reglas)
        self.assertNotIn("DOCUMENTACION_DUPLICADA", reglas)
        repetido = diccionario + _add("CRM", "Cliente", "Otra vez", "nClienteId", tipo="TABLE", tipo2="COLUMN")
        self.assertIn("DOCUMENTACION_DUPLICADA", _reglas(verificar_diccionario_tablas(tablas, repetido)))


if __name__ == "__main__":
    unittest.main()
