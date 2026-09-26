import unittest

from app.analizadores.deteccion_objeto import detectar_objeto


class TestDeteccionObjeto(unittest.TestCase):
    def test_detecta_tablas_y_procedimientos(self):
        casos = {
            "CREATE TABLE dbo.TB_Estado (nEstadoId INT)": "tabla",
            "alter table dbo.TB_Estado add cNombre VARCHAR(10)": "tabla",
            "CREATE PROCEDURE dbo.PA_X AS SELECT 1": "procedimiento",
            "ALTER PROC dbo.PA_X AS SELECT 1": "procedimiento",
            "CREATE OR ALTER PROCEDURE dbo.PA_X AS SELECT 1": "procedimiento",
        }
        for sql, esperado in casos.items():
            with self.subTest(sql=sql):
                self.assertEqual(detectar_objeto(sql), esperado)

    def test_ignora_comentarios_y_texto_sin_objeto(self):
        self.assertEqual(detectar_objeto("-- CREATE PROCEDURE viejo\nCREATE TABLE dbo.T (a INT)"), "tabla")
        self.assertIsNone(detectar_objeto("SELECT * FROM dbo.Cliente"))
        self.assertIsNone(detectar_objeto(""))


if __name__ == "__main__":
    unittest.main()
