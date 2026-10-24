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


class TestInConUnSoloValor(unittest.TestCase):
    """IN (SELECT ...) es una subconsulta (puede devolver varias filas): no es un solo valor."""

    def mensajes(self, verificar, sql):
        return [h.mensaje for h in verificar(sql) if h.regla == "IN_CON_UN_SOLO_VALOR"]

    def test_subconsulta_no_se_marca(self):
        casos = [
            "DELETE A FROM #colocacsaldo A WHERE cAgeCod NOT IN (SELECT cAgeCod FROM #CurAge)",
            "SELECT a FROM T WITH (NOLOCK) WHERE cAgeCod IN ( select cAgeCod FROM #CurAge)",
            "SELECT a FROM T WITH (NOLOCK) WHERE cAgeCod IN (\n    SELECT cAgeCod FROM #CurAge\n)",
        ]
        for sql in casos:
            for verificar in (verificar_reporte, verificar_procedimiento_normal):
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(self.mensajes(verificar, sql), [])

    def test_un_valor_si_se_marca(self):
        mensajes = self.mensajes(verificar_reporte, "SELECT a FROM T WITH (NOLOCK) WHERE cEstado IN ('A')")
        self.assertEqual(mensajes, [
            "Se identificó el uso de IN para comparar un único valor. Se recomienda utilizar el operador = "
            "cuando se compara un solo valor (ej.: WHERE cEstado = 'A')."
        ])

    def test_not_in_con_un_valor_sugiere_distinto(self):
        mensajes = self.mensajes(verificar_reporte, "SELECT a FROM T WITH (NOLOCK) WHERE cEstado NOT IN ('A')")
        self.assertEqual(mensajes, [
            "Se identificó el uso de NOT IN para comparar un único valor. Se recomienda utilizar el operador <> "
            "cuando se compara un solo valor (ej.: WHERE cEstado <> 'A')."
        ])

    def test_severidad_baja_en_reportes(self):
        # Mismo plan de ejecución que «=»: es una corrección de claridad, no de rendimiento.
        hallazgo = next(h for h in verificar_reporte("SELECT a FROM T WITH (NOLOCK) WHERE nId IN (@nId)")
                        if h.regla == "IN_CON_UN_SOLO_VALOR")
        self.assertEqual(hallazgo.severidad.value, "bajo")

    def test_texto_de_la_usuaria_en_negocio(self):
        mensajes = self.mensajes(verificar_procedimiento_normal,
                                 "UPDATE c SET c.cEstado = 'I' FROM dbo.Cliente c WHERE c.nClienteId IN (@nClienteId);")
        self.assertEqual(mensajes, [
            "Se identificó el uso del operador IN para comparar un único valor en c.nClienteId IN (@nClienteId). "
            "Se recomienda reemplazar IN por =, ya que se está comparando un solo valor. El operador IN es más "
            "apropiado para comparar múltiples valores (ej.: c.nClienteId = @nClienteId)."
        ])

    def test_varios_valores_no_se_marca(self):
        for verificar in (verificar_reporte, verificar_procedimiento_normal):
            self.assertEqual(self.mensajes(verificar, "SELECT a FROM T WITH (NOLOCK) WHERE cEstado IN ('A', 'B')"), [])


if __name__ == "__main__":
    unittest.main()
