"""Código comentado: también los restos de depuración, en Reportes y Negocio (pedido de la usuaria, 8 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _lineas(sql, verificar):
    hallazgos = [h for h in verificar(sql) if h.regla == "CODIGO_SQL_COMENTADO"]
    return sorted({n for h in hallazgos for n in (getattr(h, "lineas", None) or [h.linea])})


class ComentariosCodigoTest(unittest.TestCase):
    def test_restos_de_depuracion(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS\nBEGIN\n"
               "    SELECT -- TOP (10000)\n"                                   # 3
               "        c.cCtaCod FROM dbo.Cartera c WITH (NOLOCK)\n"
               "  --  Where cctacod = '108133041000273368'\n"                   # 5
               "    SELECT CASE WHEN c.n = 1 THEN 'A'\n"
               "                --THEN 'Apertura'\n"                            # 7
               "           END FROM dbo.Cartera c WITH (NOLOCK)\n"
               "    -- INNER JOIN dbo.Persona p WITH (NOLOCK) ON p.c = c.c\n"    # 9
               "    -- AND c.nEstado = 1\n"                                     # 10
               "END")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_lineas(sql, verificar), [3, 5, 7, 9, 10])

    def test_comentarios_que_explican_no_se_marcan(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos AS\nBEGIN\n"
               "    -- 1. Hacia cuentas nuevas\n"
               "    -- Where se filtra por la fecha de corte\n"
               "    -- Set de datos para el reporte\n"
               "    -- Top de clientes por saldo\n"
               "    -- Then se agrupa por agencia\n"
               "    -- Obtiene los datos desde bi.tablon.desembolsos\n"
               "    SELECT 'texto -- WHERE c = 1' AS c\n"
               "END")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_lineas(sql, verificar), [])

    def test_variables_de_prueba_siguen_permitidas(self):
        sql = ("CREATE PROCEDURE dbo.PA_GDD_Cartera_Sel_Saldos @dFechaCorte DATE AS\nBEGIN\n"
               "   --  DECLARE @dFechaCorte DATE = '2026-09-29'\n"
               "    SELECT 1\nEND")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_lineas(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
