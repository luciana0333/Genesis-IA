"""B1: nombre de la propiedad mal escrito (tablas y procedimientos). B3: descripción repetida en columnas."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.propiedades_extendidas import descripcion_mal_escrita

TABLA = (
    "CREATE TABLE CLICKTOPAY.Cliente (\n"
    " nClienteId INT NOT NULL,\n"
    " cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n"
    " cApellido VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL\n"
    ")"
)
PROCEDIMIENTO = "CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId\n  @nClienteId INT\nAS\nBEGIN\n  SELECT 1;\nEND;"


def _tabla(descripcion: str, columna: str = None, nombre: str = "MS_Description") -> str:
    sentencia = (
        f"EXEC sys.sp_addextendedproperty @name=N'{nombre}', @value=N'{descripcion}', @level0type=N'SCHEMA', "
        f"@level0name=N'CLICKTOPAY', @level1type=N'TABLE', @level1name=N'Cliente'"
    )
    return sentencia + (f", @level2type=N'COLUMN', @level2name=N'{columna}';" if columna else ";")


def _proc(descripcion: str, parametro: str = None, nombre: str = "MS_Description") -> str:
    sentencia = (
        f"EXEC sys.sp_addextendedproperty @name=N'{nombre}', @value=N'{descripcion}', @level0type=N'SCHEMA', "
        f"@level0name=N'CLICKTOPAY', @level1type=N'PROCEDURE', @level1name=N'PA_Cliente_Sel_PorId'"
    )
    return sentencia + (f", @level2type=N'PARAMETER', @level2name=N'{parametro}';" if parametro else ";")


class TestDescripcionMalEscrita(unittest.TestCase):
    def test_reconoce_variantes_mal_escritas(self):
        for nombre in ("MS_Descripcion", "Descripcion", "MSDescription", "MS Description", "MS_Desc", "ms_descripción"):
            with self.subTest(nombre=nombre):
                self.assertTrue(descripcion_mal_escrita(nombre))

    def test_no_marca_el_correcto_ni_otras_propiedades(self):
        for nombre in ("MS_Description", "ms_description", "", "Autor", "MS_DiagramPane1"):
            with self.subTest(nombre=nombre):
                self.assertFalse(descripcion_mal_escrita(nombre))


class TestNombrePropiedadTablas(unittest.TestCase):
    def test_columna_con_nombre_mal_escrito_no_se_marca_como_no_documentada(self):
        diccionario = "\n".join([
            _tabla("Registra los clientes de la caja"),
            _tabla("Identificador del cliente", "nClienteId"),
            _tabla("Nombre del cliente", "cNombre", nombre="MS_Descripcion"),
            _tabla("Apellido del cliente", "cApellido"),
        ])
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["NOMBRE_PROPIEDAD_INCORRECTO"])
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertEqual(hallazgos[0].linea, 3)
        self.assertEqual(
            hallazgos[0].mensaje,
            "La propiedad de la columna cNombre se registra como 'MS_Descripcion', por lo que no se reconocerá "
            "como su descripción. Usar «N'MS_Description'» como nombre de la propiedad, ya que es el nombre "
            "estándar de las descripciones del diccionario.",
        )

    def test_tabla_con_nombre_mal_escrito_no_se_marca_como_no_documentada(self):
        diccionario = "\n".join([
            _tabla("Registra los clientes de la caja", nombre="Descripcion"),
            _tabla("Identificador del cliente", "nClienteId"),
            _tabla("Nombre del cliente", "cNombre"),
            _tabla("Apellido del cliente", "cApellido"),
        ])
        reglas = [h.regla for h in verificar_diccionario_tablas(TABLA, diccionario)]
        self.assertEqual(reglas, ["NOMBRE_PROPIEDAD_INCORRECTO"])


class TestNombrePropiedadProcedimientos(unittest.TestCase):
    def test_procedimiento_y_parametro_con_nombre_mal_escrito(self):
        diccionario = "\n".join([
            _proc("Consulta los datos del cliente", nombre="MS_Descripcion"),
            _proc("Identificador del cliente", "@nClienteId", nombre="Descripcion"),
        ])
        hallazgos = verificar_diccionario(PROCEDIMIENTO, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["NOMBRE_PROPIEDAD_INCORRECTO"])
        self.assertIn("Se identificaron 2 propiedades con el nombre mal escrito", hallazgos[0].mensaje)
        self.assertIn("parámetro @nClienteId ('Descripcion')", hallazgos[0].mensaje)

    def test_con_el_nombre_correcto_no_marca_nada(self):
        diccionario = "\n".join([_proc("Consulta los datos del cliente"), _proc("Identificador del cliente", "@nClienteId")])
        self.assertEqual(verificar_diccionario(PROCEDIMIENTO, diccionario), [])


class TestDescripcionRepetida(unittest.TestCase):
    def test_dos_columnas_con_la_misma_descripcion(self):
        diccionario = "\n".join([
            _tabla("Registra los clientes de la caja"),
            _tabla("Identificador del cliente", "nClienteId"),
            _tabla("Nombre del cliente", "cNombre"),
            _tabla("Nombre  del  CLIENTE", "cApellido"),
        ])
        hallazgos = verificar_diccionario_tablas(TABLA, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["DESCRIPCION_REPETIDA"])
        self.assertEqual(hallazgos[0].severidad.value, "medio")
        self.assertEqual(hallazgos[0].linea, 4)
        self.assertTrue(hallazgos[0].mensaje.startswith(
            "Las columnas cNombre y cApellido tienen la misma descripción: 'Nombre del cliente'."))

    def test_tres_columnas_con_la_misma_descripcion(self):
        diccionario = "\n".join([_tabla("Registra los clientes de la caja")] + [
            _tabla("Dato del cliente", columna) for columna in ("nClienteId", "cNombre", "cApellido")
        ])
        hallazgos = [h for h in verificar_diccionario_tablas(TABLA, diccionario) if h.regla == "DESCRIPCION_REPETIDA"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("Las columnas nClienteId, cNombre y cApellido", hallazgos[0].mensaje)

    def test_la_misma_columna_dos_veces_es_documentacion_duplicada(self):
        diccionario = "\n".join([
            _tabla("Registra los clientes de la caja"),
            _tabla("Identificador del cliente", "nClienteId"),
            _tabla("Nombre del cliente", "cNombre"),
            _tabla("Nombre del cliente", "cNombre"),
            _tabla("Apellido del cliente", "cApellido"),
        ])
        reglas = [h.regla for h in verificar_diccionario_tablas(TABLA, diccionario)]
        self.assertEqual(reglas, ["DOCUMENTACION_DUPLICADA"])


if __name__ == "__main__":
    unittest.main()
