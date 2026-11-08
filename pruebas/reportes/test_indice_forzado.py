"""Índice forzado (WITH INDEX) con su propia observación en Reportes y Negocio (pedido de la usuaria, 7 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte
from app.analizadores.indice_forzado import QUE_HACER_INDICE_FORZADO

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


class IndiceForzadoTest(unittest.TestCase):
    def test_su_propia_observacion_con_el_que_hacer_de_la_usuaria(self):
        sql = "SELECT c.n FROM COLOCACIONES c WITH (NOLOCK, INDEX(PK_COLOCACIONES)) WHERE c.n = 1"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = {h.regla: h for h in verificar(sql)}
                self.assertNotIn("HINT_PLAN_PROHIBIDO", hallazgos)
                self.assertEqual(hallazgos["INDICE_FORZADO"].severidad.value, "alto")
                self.assertEqual(
                    hallazgos["INDICE_FORZADO"].mensaje,
                    "Se identificó que se obliga al motor a usar el índice 'PK_COLOCACIONES' en la tabla "
                    "COLOCACIONES. " + QUE_HACER_INDICE_FORZADO,
                )

    def test_varios_indices_en_una_observacion_y_los_otros_hints_aparte(self):
        sql = ("SELECT 1 FROM COLOCACIONES c WITH (INDEX(PK_COLOCACIONES))\n"
               "JOIN COLOCCALENDARIO k WITH (INDEX = PLAN_PAGOS) ON k.n = c.n\n"
               "OPTION (RECOMPILE)")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = [h for h in verificar(sql) if h.regla in ("INDICE_FORZADO", "HINT_PLAN_PROHIBIDO")]
                reglas = sorted(h.regla for h in hallazgos)
                self.assertEqual(reglas, ["HINT_PLAN_PROHIBIDO", "INDICE_FORZADO"])
                indice = next(h for h in hallazgos if h.regla == "INDICE_FORZADO")
                # La frase una vez y, por viñeta, el índice y su tabla (opción A de la usuaria).
                self.assertTrue(indice.mensaje.startswith(
                    "Se identificó que se obliga al motor a usar los siguientes índices: 'PK_COLOCACIONES' en la "
                    "tabla COLOCACIONES; 'PLAN_PAGOS' en la tabla COLOCCALENDARIO. "))
                self.assertEqual(indice.lineas, [1, 2])
                self.assertTrue(indice.mensaje.endswith(QUE_HACER_INDICE_FORZADO))

    def test_crear_un_indice_no_es_forzarlo(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                reglas = {h.regla for h in verificar("CREATE TABLE #T (nId INT)\nCREATE INDEX IX_T ON #T (nId)")}
                self.assertNotIn("INDICE_FORZADO", reglas)


if __name__ == "__main__":
    unittest.main()
