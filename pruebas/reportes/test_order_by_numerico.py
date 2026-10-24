"""ORDER BY por posición de columna: los números dentro de una función no son posiciones."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.sql_order_by import order_by_por_posicion


def posiciones(sql):
    return [numeros for _, numeros in order_by_por_posicion(sql)]


class TestLecturaOrderBy(unittest.TestCase):
    def test_numeros_dentro_de_una_funcion_no_son_posiciones(self):
        casos = [
            "SELECT ROW_NUMBER() OVER(PARTITION BY A.nId ORDER BY SUBSTRING(A.cMovNro,1,14) DESC), B.cCtaCod FROM A",
            "SELECT * FROM T ORDER BY SUBSTRING(cMovNro, 1, 14)",
            "SELECT * FROM T ORDER BY CONVERT(VARCHAR(8), dFecha, 112), LEFT(cNombre, 3) DESC",
            "SELECT * FROM T ORDER BY ISNULL(nOrden, 0)",
            "SELECT ROW_NUMBER() OVER(ORDER BY (SELECT 1)) FROM T",
        ]
        for sql in casos:
            with self.subTest(sql=sql):
                self.assertEqual(posiciones(sql), [])

    def test_posiciones_reales(self):
        casos = {
            "SELECT a, b FROM T ORDER BY 1, 2": [["1", "2"]],
            "SELECT a, b FROM T ORDER BY a, 2 DESC;": [["2"]],
            "SELECT a, b FROM T ORDER BY SUBSTRING(a, 1, 3), 2": [["2"]],
            "SELECT ROW_NUMBER() OVER(ORDER BY 1) FROM T": [["1"]],
            "SELECT a FROM T ORDER BY 1\nSELECT b FROM U WHERE x = 2": [["1"]],
            "SELECT a FROM T ORDER BY 1 OFFSET 10 ROWS FETCH NEXT 5 ROWS ONLY": [["1"]],
        }
        for sql, esperado in casos.items():
            with self.subTest(sql=sql):
                self.assertEqual(posiciones(sql), esperado)

    def test_columnas_que_terminan_en_palabra_clave_no_cortan_la_lista(self):
        self.assertEqual(posiciones("SELECT * FROM T ORDER BY cSetCod, nFromId, 3"), [["3"]])


class TestReglaEnLosModulos(unittest.TestCase):
    CASO_DE_LA_USUARIA = """
    SELECT
        (ROW_NUMBER() OVER(PARTITION BY A.nColocLineaCredPersona ORDER BY SUBSTRING(A.cMovNro,1,14) DESC)),
        B.cCtaCod
    FROM dbo.Movimiento A WITH (NOLOCK)
    INNER JOIN dbo.Cuenta B WITH (NOLOCK) ON B.cCtaCod = A.cCtaCod
    """

    def test_reportes_no_marca_substring(self):
        reglas = [h.regla for h in verificar_reporte(self.CASO_DE_LA_USUARIA)]
        self.assertNotIn("ORDER_BY_NUMERICO_PROHIBIDO", reglas)

    def test_normales_no_marca_substring(self):
        reglas = [h.regla for h in verificar_procedimiento_normal(self.CASO_DE_LA_USUARIA)]
        self.assertNotIn("ORDER_BY_NUMERICO_PROHIBIDO", reglas)

    def test_normales_detecta_posicion_despues_de_un_nombre(self):
        hallazgos = [h for h in verificar_procedimiento_normal("SELECT a, b FROM #T ORDER BY a, 2;")
                     if h.regla == "ORDER_BY_NUMERICO_PROHIBIDO"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("(ORDER BY 2)", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
