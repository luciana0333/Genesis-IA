"""«Comparación de columna numérica con texto» en Reportes y Negocio (texto de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _observacion(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "COLUMNA_NUMERICA_CON_TEXTO"]


class NumeroComparadoConTextoTest(unittest.TestCase):
    def test_temporal_con_tipo_confirmado_va_en_medio_con_el_texto_de_la_usuaria(self):
        sql = "CREATE TABLE #C (nConsCod INT)\nSELECT 1 FROM #C CT WHERE CT.nConsCod = '3001'"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgo = _observacion(sql, verificar)[0]
                self.assertEqual(hallazgo.severidad.value, "medio")
                self.assertIsNone(getattr(hallazgo, "consulta", None))
                self.assertEqual(
                    hallazgo.mensaje,
                    "Se identificó que la columna CT.nConsCod, definida como INT, se compara con un valor de texto "
                    "('3001'). Se recomienda verificar el tipo de dato de la columna y realizar la comparación "
                    "utilizando el mismo tipo. En este caso, como CT.nConsCod es de tipo INT, se debe comparar con un "
                    "valor numérico, sin utilizar comillas (ej.: CT.nConsCod = 3001).",
                )

    def test_tabla_fisica_por_prefijo_va_en_bajo_con_consulta(self):
        sql = ("SELECT 1 FROM DBCMACICA.DBO.Producto PD WITH (NOLOCK)\n"
               "INNER JOIN DBCMACICA.DBO.Constante CT WITH (NOLOCK) ON CT.nConsValor = PD.nPrdEstado\n"
               "WHERE CT.nConsCod = '3001'")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgo = _observacion(sql, verificar)[0]
                self.assertEqual(hallazgo.severidad.value, "bajo")
                self.assertEqual(hallazgo.linea, 3)
                self.assertTrue(hallazgo.mensaje.startswith(
                    "Se identificó que la columna CT.nConsCod, de tipo numérico según su prefijo, se compara con un "
                    "valor de texto ('3001'). "))
                self.assertIn("Si CT.nConsCod es de tipo numérico, se debe comparar con un valor numérico, sin "
                              "utilizar comillas (ej.: CT.nConsCod = 3001).", hallazgo.mensaje)
                self.assertEqual(
                    hallazgo.consulta,
                    "SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE\nFROM DBCMACICA.INFORMATION_SCHEMA.COLUMNS\n"
                    "WHERE TABLE_SCHEMA = 'DBO' AND TABLE_NAME = 'Constante' AND COLUMN_NAME = 'nConsCod'",
                )

    def test_in_y_varias_columnas_en_una_sola_observacion(self):
        sql = ("CREATE TABLE #C (nConsCod INT)\nSELECT 1 FROM #C c\n"
               "JOIN dbo.Constante CT WITH (NOLOCK) ON CT.nConsValor = c.nConsCod\n"
               "WHERE c.nConsCod IN ('1', '2') AND CT.nConsCod = '3001'")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _observacion(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")  # una está confirmada
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificaron las siguientes columnas numéricas comparadas con texto: c.nConsCod, definida "
                    "como INT, se compara con valores de texto ('1', '2'); CT.nConsCod, de tipo numérico según su "
                    "prefijo, se compara con un valor de texto ('3001'). "))

    def test_lo_que_no_se_observa(self):
        for sql in (
            "CREATE TABLE #C (nCodigo VARCHAR(10))\nSELECT 1 FROM #C c WHERE c.nCodigo = '10'",  # tipo real: texto
            "UPDATE A SET A.nEstado = '1' FROM #T A",                    # asignación, no filtro
            "SELECT nValor = '1' FROM dbo.T",                             # alias del SELECT
            "SELECT 1 FROM dbo.T t WITH (NOLOCK) WHERE t.nTipo = 'A'",   # texto con letras
            "SELECT 1 FROM dbo.T t WITH (NOLOCK) WHERE t.cCodigo = '10'",  # columna de texto
            "SELECT 1 FROM dbo.T t WITH (NOLOCK) WHERE t.nCodigo = 10",    # ya es número
            "SELECT 1 FROM dbo.T t WITH (NOLOCK) WHERE @nX = '1'",          # variable
        ):
            for verificar in MODULOS:
                with self.subTest(sql=sql, modulo=verificar.__name__):
                    self.assertEqual(_observacion(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
