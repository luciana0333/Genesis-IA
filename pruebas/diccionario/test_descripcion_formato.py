"""«Descripción sin formato estándar» (usuaria, 13 nov.): la descripción del objeto inicia con «Tabla»,
«Procedimiento» o «Función». El resto es libre. Solo la descripción del objeto, no la de columnas ni parámetros."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.descripcion_formato import descripcion_sin_formato

REGLA = "DESCRIPCION_SIN_FORMATO_ESTANDAR"
_TABLA = "CREATE TABLE dbo.Cliente (\n nClienteId INT NOT NULL\n)"
_PA = "CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId\n @nClienteId INT\nAS\nBEGIN\n SELECT 1;\nEND"
_FN = "CREATE FUNCTION dbo.FN_Cliente_Nombre (@nClienteId INT)\nRETURNS VARCHAR(100)\nAS\nBEGIN\n RETURN '';\nEND"


def _dicc(tipo, nombre, descripcion, nivel2=None, valor2="Identificador del cliente"):
    texto = (f"EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'{descripcion}', @level0type=N'SCHEMA', "
             f"@level0name=N'dbo', @level1type=N'{tipo}', @level1name=N'{nombre}'\n")
    if nivel2:
        tipo2, nombre2 = nivel2
        texto += (f"EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'{valor2}', @level0type=N'SCHEMA', "
                  f"@level0name=N'dbo', @level1type=N'{tipo}', @level1name=N'{nombre}', @level2type=N'{tipo2}', "
                  f"@level2name=N'{nombre2}'\n")
    return texto


def _tabla(descripcion, **extra):
    return [h for h in verificar_diccionario_tablas(_TABLA, _dicc("TABLE", "Cliente", descripcion,
                                                                    ("COLUMN", "nClienteId"), **extra)) if h.regla == REGLA]


def _pa(descripcion, **extra):
    return [h for h in verificar_diccionario(_PA, _dicc("PROCEDURE", "PA_Cliente_Sel_PorId", descripcion,
                                                          ("PARAMETER", "@nClienteId"), **extra)) if h.regla == REGLA]


def _fn(descripcion):
    return [h for h in verificar_diccionario(_FN, _dicc("FUNCTION", "FN_Cliente_Nombre", descripcion,
                                                          ("PARAMETER", "@nClienteId")), "funcion") if h.regla == REGLA]


class DescripcionFormatoTest(unittest.TestCase):
    def test_tabla_texto_de_la_usuaria(self):
        hallazgo = _tabla("Almacena los clientes")[0]
        self.assertEqual(hallazgo.severidad.value, "bajo")
        self.assertEqual(hallazgo.linea, 1)
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificó que la descripción de la tabla dbo.Cliente no inicia con la palabra «Tabla». Se recomienda "
            "iniciar la descripción con la palabra «Tabla», para que se pueda reconocer rápidamente el tipo de objeto "
            "documentado y comprender con mayor facilidad la información que contiene.",
        )

    def test_procedimiento_y_funcion(self):
        self.assertIn("la descripción del procedimiento dbo.PA_Cliente_Sel_PorId no inicia con la palabra "
                      "«Procedimiento». Se recomienda iniciar la descripción con la palabra «Procedimiento»",
                      _pa("Consulta el cliente")[0].mensaje)
        self.assertIn("la descripción de la función dbo.FN_Cliente_Nombre no inicia con la palabra «Función». Se "
                      "recomienda iniciar la descripción con la palabra «Función»",
                      _fn("Devuelve el nombre del cliente")[0].mensaje)

    def test_el_resto_es_libre(self):
        for descripcion in ("Tabla que almacena los clientes", "Tabla de clientes", "tabla con los clientes",
                            "TABLA QUE REGISTRA CLIENTES", " Tabla que almacena los clientes"):
            with self.subTest(descripcion=descripcion):
                self.assertEqual(_tabla(descripcion), [])
        for descripcion in ("Procedimiento que consulta el cliente", "Procedimiento encargado de obtener el cliente",
                            "procedimiento almacenado que consulta"):
            with self.subTest(descripcion=descripcion):
                self.assertEqual(_pa(descripcion), [])
        for descripcion in ("Función que devuelve el nombre", "Funcion que devuelve el nombre"):
            with self.subTest(descripcion=descripcion):
                self.assertEqual(_fn(descripcion), [])

    def test_la_palabra_debe_ser_completa_y_al_inicio(self):
        self.assertTrue(_tabla("Tablas de clientes"))           # otra palabra
        self.assertTrue(_tabla("Esta tabla almacena clientes"))  # no está al inicio
        self.assertTrue(_pa("Procedimientos del cliente"))
        self.assertTrue(_pa("Tabla que consulta el cliente"))   # palabra de otro objeto
        self.assertTrue(_fn("Procedimiento que devuelve el nombre"))

    def test_solo_la_descripcion_del_objeto(self):
        # La descripción de la columna o del parámetro es libre.
        self.assertEqual(_tabla("Tabla de clientes", valor2="Identificador del cliente"), [])
        self.assertEqual(_pa("Procedimiento que consulta el cliente", valor2="Código del cliente"), [])

    def test_vacia_no_se_marca_aqui(self):
        self.assertIsNone(descripcion_sin_formato("tabla", "dbo.Cliente", ""))
        self.assertIsNone(descripcion_sin_formato("tabla", "dbo.Cliente", "   "))


if __name__ == "__main__":
    unittest.main()
