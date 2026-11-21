"""Tabla temporal usada sin crear (Reportes y Negocio): falla al ejecutarse (caso de la usuaria, 7 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _sin_crear(verificar, sql, regla="TEMPORAL_SIN_CREAR"):
    return [h for h in verificar(sql) if h.regla == regla]


VALIDAR = "TEMPORAL_SIN_CREAR_VALIDAR"


class TemporalesSinCrearTest(unittest.TestCase):
    def test_caso_de_la_usuaria_tempre2(self):
        # Se crea #TempPre, pero en la rama de dólares se usa #TempPre2, que nunca se crea.
        sql = ("CREATE TABLE #TempPre (nMovNro INT, cCtaCnt VARCHAR(22) COLLATE SQL_Latin1_General_CP1_CI_AS)\n"
               "INSERT INTO #TempPre (nMovNro) SELECT 1\n"
               "UPDATE X\nSET X.cCtaCnt = 'a'\nFROM #TempPre2 X\n"
               "SELECT nMovNro FROM #TempPre2\n")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _sin_crear(verificar, sql)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "critico")
                self.assertEqual(
                    hallazgos[0].mensaje,
                    "Se identificó que la tabla temporal #TempPre2 se utiliza, pero no se crea dentro "
                    "del procedimiento. Crear la tabla temporal antes de usarla o corregir el nombre (ej.: #TempPre), "
                    "salvo que la cree el procedimiento que lo llama, ya que, al ejecutarse, SQL Server detiene el "
                    "procedimiento con el error «El nombre de objeto '#TempPre2' no es válido».",
                )
                self.assertEqual(hallazgos[0].grupos, [{"nombre": "#TempPre2", "tipo": "Tabla", "lineas": [5, 6]}])

    def test_varias_temporales_en_una_observacion(self):
        sql = "SELECT 1 FROM #A\nINSERT INTO #B (n) SELECT 1\nDELETE FROM #A\nTRUNCATE TABLE #C\n"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                # Ninguna se parece a una creada: «validar» (medio; usuaria, 21 nov.); 3 casos en viñetas.
                hallazgos = _sin_crear(verificar, sql, VALIDAR)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].severidad.value, "medio")
                self.assertTrue(hallazgos[0].mensaje.startswith(
                    "Se identificó que las siguientes tablas temporales se utilizan, pero no se crean en este "
                    "procedimiento: #A; #B; #C. Se recomienda verificar que las tablas temporales se creen previamente "
                    "en el mismo flujo de ejecución y que estén disponibles al momento de ejecutar este procedimiento."))
                self.assertEqual(hallazgos[0].lineas, [1, 3, 2, 4])  # arriba de la tarjeta, tabla por tabla

    def test_creada_con_create_table_o_select_into_no_se_observa(self):
        casos = (
            "CREATE TABLE #A (n INT)\nINSERT INTO #A (n) SELECT 1\nSELECT n FROM #A\nDROP TABLE #A",
            "SELECT 1 AS n INTO #A\nUPDATE #A SET n = 2\nSELECT a.n FROM #A a JOIN #A b ON a.n = b.n",
            "SELECT TOP 1 c.n\nINTO #A\nFROM dbo.Cliente c WITH (NOLOCK)\nCREATE INDEX IX_A ON #A (n)",
            "CREATE TABLE [#A] (n INT)\nSELECT n FROM #a",  # SQL Server no distingue mayúsculas
            "DROP TABLE IF EXISTS #A, #B",  # borrar no es usar
            "SELECT 1 FROM ##Global",  # las temporales globales no se revisan
            "-- SELECT 1 FROM #Comentada\nSELECT 'FROM #EnUnTexto' AS c",
        )
        for verificar in MODULOS:
            for sql in casos:
                with self.subTest(modulo=verificar.__name__, sql=sql):
                    self.assertEqual(_sin_crear(verificar, sql), [])
                    self.assertEqual(_sin_crear(verificar, sql, VALIDAR), [])

    def test_insert_into_no_crea_la_tabla(self):
        # INSERT INTO #A ... no la crea: si no hay CREATE TABLE ni SELECT INTO, se observa (para validar).
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _sin_crear(verificar, "INSERT INTO #A (n)\nSELECT 1", VALIDAR)
                self.assertEqual([h.grupos[0]["nombre"] for h in hallazgos], ["#A"])

    def test_mas_de_tres_solo_los_nombres(self):
        # Caso del PA del motor (21 nov.): con más de 3, la pantalla las muestra en cajitas (opción A): el texto las
        # lista y no se manda tabla.
        sql = ("UPDATE A SET A.n = 1 FROM #BaseHechos A\nSELECT 1 FROM #BaseHechos B JOIN #Garantias G ON 1 = 1\n"
               "SELECT 1 FROM #CreditosTitular\nINSERT INTO #Aux (n) SELECT 1\nDELETE FROM #Aux\n")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                h = _sin_crear(verificar, sql, VALIDAR)[0]
                self.assertIn("procedimiento: #BaseHechos; #Garantias; #CreditosTitular; #Aux.", h.mensaje)
                self.assertEqual([g["nombre"] for g in h.grupos],
                                 ["#BaseHechos", "#Garantias", "#CreditosTitular", "#Aux"])
                self.assertFalse(any("tituloDetalle" in g for g in h.grupos))

    def test_dos_en_el_parrafo_y_una_sola(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                dos = _sin_crear(verificar, "SELECT 1 FROM #A\nSELECT 1 FROM #B", VALIDAR)[0]
                self.assertTrue(dos.mensaje.startswith(
                    "Se identificó que las tablas temporales #A y #B se utilizan, pero no se crean en este "
                    "procedimiento."))
                una = _sin_crear(verificar, "SELECT 1 FROM #A", VALIDAR)[0]
                # Texto de la usuaria (21 nov.), en singular.
                self.assertEqual(
                    una.mensaje,
                    "Se identificó que la tabla temporal #A se utiliza, pero no se crea en este procedimiento. Se "
                    "recomienda verificar que la tabla temporal se cree previamente en el mismo flujo de ejecución y "
                    "que esté disponible al momento de ejecutar este procedimiento.")


if __name__ == "__main__":
    unittest.main()
