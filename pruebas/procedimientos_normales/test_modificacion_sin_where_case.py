"""Negocio, UPDATE/DELETE sin WHERE: el ELSE y el END de un CASE no cortan la sentencia.

Solo se observa cuando de verdad no hay WHERE (ni JOIN) y la tabla es física.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal

# Caso de la usuaria: CASE en varias líneas, con su ELSE y su END al inicio de línea.
_SET_CON_CASE = """    UPDATE R
    SET
        R.SaldoTCF = CASE
                        WHEN SUBSTRING(R.NroCredito, 9, 1) = '1'
                        THEN C.Saldo
                        ELSE ROUND(C.Saldo * 3.5, 2)
                     END,
        R.Moneda   = CASE
                        WHEN SUBSTRING(R.NroCredito, 9, 1) = '1'
                        THEN 'SOLES'
                        ELSE 'DOLARES'
                     END
"""


def _procedimiento(cuerpo: str) -> str:
    return f"CREATE PROCEDURE dbo.PA_Credito_Upd_Saldos\nAS\nBEGIN\n{cuerpo}END\n"


def _sin_where(cuerpo: str):
    return [h for h in verificar_procedimiento_normal(_procedimiento(cuerpo)) if h.regla == "MODIFICACION_SIN_WHERE"]


class TestNoSeObserva(unittest.TestCase):
    """Tiene WHERE, JOIN o es temporal: no debe salir."""

    def test_caso_de_la_usuaria_con_where(self):
        self.assertEqual(_sin_where(_SET_CON_CASE + "    FROM dbo.Reporte R\n    WHERE R.nId = 1\n"), [])

    def test_con_join_despues_del_case(self):
        cuerpo = _SET_CON_CASE + "    FROM dbo.Reporte R\n    INNER JOIN dbo.Credito C ON C.cCtaCod = R.NroCredito\n"
        self.assertEqual(_sin_where(cuerpo), [])

    def test_alias_de_una_temporal(self):
        self.assertEqual(_sin_where(_SET_CON_CASE + "    FROM #ReporteA R\n"), [])

    def test_case_anidado_con_where(self):
        cuerpo = """    UPDATE dbo.Reporte
    SET cTipo = CASE
                    WHEN nMonto > 0 THEN
                        CASE
                            WHEN nMonto > 1000 THEN 'ALTO'
                            ELSE 'BAJO'
                        END
                    ELSE 'CERO'
                END
    WHERE dFecha = @dFecha
"""
        self.assertEqual(_sin_where(cuerpo), [])

    def test_minusculas(self):
        cuerpo = ("    update dbo.Reporte\n    set cTipo = case\n        when nMonto > 0 then 'A'\n"
                  "        else 'B'\n    end\n    where nId = 1\n")
        self.assertEqual(_sin_where(cuerpo), [])

    def test_delete_con_case_en_el_where(self):
        cuerpo = ("    DELETE FROM dbo.Reporte\n    WHERE cTipo = CASE\n        WHEN @nModo = 1 THEN 'A'\n"
                  "        ELSE 'B'\n    END\n")
        self.assertEqual(_sin_where(cuerpo), [])

    def test_where_con_punto_y_coma(self):
        self.assertEqual(_sin_where(_SET_CON_CASE + "    FROM dbo.Reporte R\n    WHERE R.nId = 1;\n"), [])

    def test_columna_llamada_end_no_cierra_el_case(self):
        cuerpo = """    UPDATE dbo.Reporte
    SET cTipo = CASE
                    WHEN [End] = 1 THEN 'A'
                    WHEN R.End = 2 THEN 'B'
                    ELSE 'C'
                END
    WHERE nId = 1
"""
        self.assertEqual(_sin_where(cuerpo), [])


class TestSiSeObserva(unittest.TestCase):
    """Sin WHERE sobre una tabla física: debe salir, aunque haya CASE."""

    def test_alias_de_tabla_fisica_sin_where(self):
        hallazgos = _sin_where(_SET_CON_CASE + "    FROM dbo.Reporte R\n")
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("UPDATE sobre la tabla dbo.Reporte sin condición WHERE", hallazgos[0].mensaje)

    def test_case_sin_where_no_toma_el_where_de_la_sentencia_siguiente(self):
        cuerpo = """    UPDATE dbo.Reporte
    SET cTipo = CASE
                    WHEN nMonto > 0 THEN 'A'
                    ELSE 'B'
                END

    SELECT nId FROM dbo.Reporte WHERE nId = 1
"""
        self.assertEqual(len(_sin_where(cuerpo)), 1)

    def test_case_sin_where_antes_del_end_del_bloque(self):
        cuerpo = """    IF @nModo = 1
    BEGIN
        UPDATE dbo.Reporte
        SET cTipo = CASE WHEN nMonto > 0 THEN 'A' ELSE 'B' END
    END
    UPDATE dbo.Reporte SET cTipo = 'X' WHERE nId = 1
"""
        hallazgos = _sin_where(cuerpo)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].linea, 6)

    def test_case_en_varias_lineas_antes_del_end_del_bloque(self):
        cuerpo = """    IF @nModo = 1
    BEGIN
        UPDATE dbo.Reporte
        SET cTipo = CASE
                        WHEN nMonto > 0 THEN 'A'
                        ELSE 'B'
                    END
    END
    ELSE
        UPDATE dbo.Reporte SET cTipo = 'X' WHERE nId = 1
"""
        hallazgos = _sin_where(cuerpo)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].linea, 6)

    def test_if_else_sin_case_sigue_igual(self):
        cuerpo = """    IF @nModo = 1
        UPDATE dbo.Reporte SET cTipo = 'A'
    ELSE
        UPDATE dbo.Reporte SET cTipo = 'B' WHERE nId = 1
"""
        hallazgos = _sin_where(cuerpo)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].linea, 5)

    def test_delete_sin_where(self):
        self.assertEqual(len(_sin_where("    DELETE FROM dbo.Reporte\n")), 1)

    def test_case_en_una_sola_linea_sin_where(self):
        self.assertEqual(len(_sin_where("    UPDATE dbo.Reporte SET cTipo = CASE WHEN nMonto > 0 THEN 'A' ELSE 'B' END\n")), 1)


if __name__ == "__main__":
    unittest.main()
