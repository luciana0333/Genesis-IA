"""Reportes, modificación de tabla física: el CASE ... ELSE ... END del SET no corta la sentencia.

Solo se observa cuando la tabla que se modifica es física (no temporal, ni variable de tabla).
"""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte

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


def _modificaciones(cuerpo: str):
    sql = f"CREATE PROCEDURE dbo.PA_GDD_Credito_Sel_Saldos\nAS\nBEGIN\n{cuerpo}END\n"
    return [h for h in verificar_reporte(sql) if h.regla == "MODIFICACION_TABLA_FISICA"]


class TestTemporalNoSeObserva(unittest.TestCase):
    def test_caso_de_la_usuaria_con_join(self):
        cuerpo = _SET_CON_CASE + "    FROM #ReporteA R\n    INNER JOIN #Creditos C ON C.cCtaCod = R.NroCredito\n"
        self.assertEqual(_modificaciones(cuerpo), [])

    def test_variable_de_tabla(self):
        self.assertEqual(_modificaciones(_SET_CON_CASE + "    FROM @Reporte R\n"), [])

    def test_case_anidado(self):
        cuerpo = """    UPDATE R
    SET cTipo = CASE
                    WHEN R.nMonto > 0 THEN
                        CASE
                            WHEN R.nMonto > 1000 THEN 'ALTO'
                            ELSE 'BAJO'
                        END
                    ELSE 'CERO'
                END
    FROM #Reporte R
"""
        self.assertEqual(_modificaciones(cuerpo), [])

    def test_minusculas(self):
        cuerpo = "    update r\n    set cTipo = case\n        when r.n > 0 then 'A'\n        else 'B'\n    end\n    from #Reporte r\n"
        self.assertEqual(_modificaciones(cuerpo), [])

    def test_delete_con_case_en_el_where(self):
        cuerpo = ("    DELETE R\n    FROM #Reporte R\n    WHERE R.cTipo = CASE\n        WHEN @nModo = 1 THEN 'A'\n"
                  "        ELSE 'B'\n    END\n")
        self.assertEqual(_modificaciones(cuerpo), [])

    def test_caso_de_la_usuaria_case_en_una_linea_con_join(self):
        cuerpo = """    UPDATE A
        SET
            A.dtFechaVencimiento = B.dtFechaVencimiento,
            A.nEstado  =  CASE WHEN CAST(GETDATE() AS DATE) > CAST(B.dtFechaVencimiento AS DATE)  THEN 2050 ELSE 2020  END,
            A.nUsoVehiculo = B.nUsoVehiculo
        FROM #MOVCONVCOBRANZA  A
        INNER JOIN DBCMACICA.dbo.InformacionVentaSoat B
            ON A.NMOVNRO = B.nMovNro
"""
        self.assertEqual(_modificaciones(cuerpo), [])
        fisica = _modificaciones(cuerpo.replace("#MOVCONVCOBRANZA", "dbo.MovConvCobranza"))
        self.assertEqual(len(fisica), 1)
        self.assertIn("modifica la tabla dbo.MovConvCobranza con UPDATE", fisica[0].mensaje)

    def test_columna_llamada_end(self):
        cuerpo = """    UPDATE R
    SET cTipo = CASE WHEN R.[End] = 1 THEN 'A' ELSE 'C' END
    FROM #Reporte R
"""
        self.assertEqual(_modificaciones(cuerpo), [])


class TestFisicaSiSeObserva(unittest.TestCase):
    def test_alias_de_tabla_fisica_dice_su_nombre(self):
        hallazgos = _modificaciones(_SET_CON_CASE + "    FROM dbo.Reporte R\n")
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("modifica la tabla dbo.Reporte con UPDATE", hallazgos[0].mensaje)

    def test_case_anidado_sobre_fisica(self):
        cuerpo = """    UPDATE R
    SET cTipo = CASE
                    WHEN R.nMonto > 0 THEN CASE WHEN R.nMonto > 1000 THEN 'ALTO' ELSE 'BAJO' END
                    ELSE 'CERO'
                END
    FROM DBCMACICA.dbo.Reporte R
"""
        hallazgos = _modificaciones(cuerpo)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("DBCMACICA.dbo.Reporte", hallazgos[0].mensaje)

    def test_dentro_de_if_else_cada_una_con_su_tabla(self):
        cuerpo = """    IF @nModo = 1
    BEGIN
        UPDATE R
        SET cTipo = CASE
                        WHEN R.nMonto > 0 THEN 'A'
                        ELSE 'B'
                    END
        FROM #Reporte R
    END
    ELSE
        UPDATE R SET cTipo = CASE WHEN R.n = 1 THEN 'X' ELSE 'Y' END FROM dbo.Reporte R
"""
        hallazgos = _modificaciones(cuerpo)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("dbo.Reporte", hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].linea, 14)

    def test_tabla_fisica_con_esquema_sin_alias(self):
        cuerpo = "    UPDATE dbo.Reporte\n    SET cTipo = CASE\n        WHEN nMonto > 0 THEN 'A'\n        ELSE 'B'\n    END\n"
        self.assertEqual(len(_modificaciones(cuerpo)), 1)


if __name__ == "__main__":
    unittest.main()
