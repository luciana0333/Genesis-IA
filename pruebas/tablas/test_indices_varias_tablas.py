"""Índices de un script de tablas que crea varias tablas: cada índice se cruza con su propia tabla."""

import unittest

from app.analizadores.analizador_indices import verificar_indices

TABLAS = """CREATE TABLE Garantia.Testimonio (
    nTestimonioId INT IDENTITY(1,1) NOT NULL,
    cCtaCod VARCHAR(18) NOT NULL,
    CONSTRAINT PK_Testimonio PRIMARY KEY (nTestimonioId))
CREATE TABLE Garantia.TestimonioMovimiento (
    nTestimonioMovimientoId INT IDENTITY(1,1) NOT NULL,
    cCtaCod VARCHAR(18) NOT NULL,
    nEstado INT NOT NULL,
    CONSTRAINT PK_TestimonioMovimiento PRIMARY KEY (nTestimonioMovimientoId))"""


def _reglas(indices, tablas=TABLAS):
    return [h.regla for h in verificar_indices(indices, tablas)]


class IndicesVariasTablasTest(unittest.TestCase):
    def test_tabla_que_no_es_la_primera_no_es_existente(self):
        indice = "CREATE NONCLUSTERED INDEX IXN_TestimonioMovimiento_cCtaCod ON Garantia.TestimonioMovimiento (cCtaCod)"
        self.assertEqual(_reglas(indice), [])

    def test_columna_de_otra_tabla_no_existe(self):
        # nEstado está en TestimonioMovimiento, no en Testimonio.
        indice = "CREATE NONCLUSTERED INDEX IXN_Testimonio_nEstado ON Garantia.Testimonio (nEstado)"
        self.assertIn("INDICE_COLUMNA_NO_EXISTE", _reglas(indice))

    def test_indice_igual_a_la_pk_de_la_segunda_tabla(self):
        indice = ("CREATE NONCLUSTERED INDEX IXN_TestimonioMovimiento_nTestimonioMovimientoId "
                  "ON Garantia.TestimonioMovimiento (nTestimonioMovimientoId)")
        self.assertIn("INDICE_DUPLICADO", _reglas(indice))

    def test_varios_nombres_fuera_del_estandar_en_una_observacion(self):
        indices = ("CREATE NONCLUSTERED INDEX IXN_TESTIMONIO_CCTACOD_IC01 ON Garantia.Testimonio (cCtaCod)\n"
                   "CREATE NONCLUSTERED INDEX IXN_MOVIMIENTO_CCTACOD ON Garantia.TestimonioMovimiento (cCtaCod)")
        nombres = [h for h in verificar_indices(indices, TABLAS) if h.regla == "INDICE_NOMBRE_NO_ESTANDAR"]
        self.assertEqual(len(nombres), 1)
        self.assertEqual(nombres[0].lineas, [1, 2])
        self.assertEqual(nombres[0].seccion, "indices")
        self.assertEqual(
            nombres[0].mensaje,
            "Se identificaron dos índices cuyo nombre no corresponde a la tabla y las columnas que indexan: "
            "IXN_TESTIMONIO_CCTACOD_IC01 → IXN_Testimonio_cCtaCod; "
            "IXN_MOVIMIENTO_CCTACOD → IXN_TestimonioMovimiento_cCtaCod. "
            "Renombrar cada índice como se sugiere (formato IXN_Tabla_Columnas).",
        )

    def test_nombre_en_mayusculas_con_la_sintaxis_correcta_no_se_observa(self):
        indice = "CREATE NONCLUSTERED INDEX IXN_TESTIMONIOMOVIMIENTO_CCTACOD ON Garantia.TestimonioMovimiento (cCtaCod)"
        self.assertNotIn("INDICE_NOMBRE_NO_ESTANDAR", _reglas(indice))

    def test_tabla_que_no_esta_en_el_script_sigue_siendo_existente(self):
        indice = "CREATE NONCLUSTERED INDEX IXN_Cliente_cCtaCod ON dbo.Cliente (cCtaCod)"
        self.assertIn("INDICE_TABLA_EXISTENTE", _reglas(indice))


if __name__ == "__main__":
    unittest.main()
