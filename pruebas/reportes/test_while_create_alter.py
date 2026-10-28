"""WHILE en Reportes: se observa en un procedimiento nuevo (CREATE), no en un ALTER."""

import unittest

from app.analizadores.analizador_reportes import verificar_reporte

CUERPO = """
AS
BEGIN
    DECLARE @n INT = 0
    WHILE @n < 3
    BEGIN
        SET @n = @n + 1
    END
    SELECT @n AS nTotal
END"""


def _while(sql):
    return [h for h in verificar_reporte(sql) if h.regla == "WHILE_PROHIBIDO"]


class WhileCreateAlterTest(unittest.TestCase):
    def test_create_lo_observa(self):
        for encabezado in ("CREATE PROCEDURE dbo.PA_Prueba_Sel_Reporte",
                           "CREATE PROC dbo.PA_Prueba_Sel_Reporte",
                           "create procedure dbo.PA_Prueba_Sel_Reporte",
                           "CREATE PROCEDURE [dbo].[PA_Prueba_Sel_Reporte]"):
            with self.subTest(encabezado=encabezado):
                hallazgos = _while(encabezado + CUERPO)
                self.assertEqual(len(hallazgos), 1)
                self.assertEqual(hallazgos[0].linea, 5)
                self.assertEqual(hallazgos[0].severidad.value, "alto")

    def test_alter_no_lo_observa(self):
        for encabezado in ("ALTER PROCEDURE dbo.PA_Prueba_Sel_Reporte",
                           "ALTER PROC dbo.PA_Prueba_Sel_Reporte",
                           "alter procedure dbo.PA_Prueba_Sel_Reporte"):
            with self.subTest(encabezado=encabezado):
                self.assertEqual(_while(encabezado + CUERPO), [])

    def test_alter_con_create_de_otras_cosas_tampoco(self):
        # Un ALTER que crea tablas temporales o índices sigue siendo un ALTER.
        sql = ("ALTER PROCEDURE dbo.PA_Prueba_Sel_Reporte\nAS\nBEGIN\n"
               "CREATE TABLE #T (nId INT)\nCREATE CLUSTERED INDEX IX_#T ON #T (nId)\n"
               "WHILE 1 = 0 BREAK\nEND")
        self.assertEqual(_while(sql), [])

    def test_alter_con_create_procedure_en_un_comentario_tampoco(self):
        sql = "-- Antes: CREATE PROCEDURE dbo.PA_Prueba_Sel_Reporte\nALTER PROCEDURE dbo.PA_Prueba_Sel_Reporte" + CUERPO
        self.assertEqual(_while(sql), [])

    def test_while_en_comentario_o_texto_no_cuenta(self):
        sql = ("CREATE PROCEDURE dbo.PA_Prueba_Sel_Reporte\nAS\nBEGIN\n"
               "-- WHILE @n < 3 (ya no se usa)\nSELECT 'WHILE' AS cTexto\nEND")
        self.assertEqual(_while(sql), [])

    def test_varios_while_en_un_create(self):
        sql = ("CREATE PROCEDURE dbo.PA_Prueba_Sel_Reporte\nAS\nBEGIN\n"
               "WHILE 1 = 0 BREAK\nSELECT 1\nWHILE 1 = 0 BREAK\nEND")
        hallazgo = _while(sql)[0]
        self.assertEqual(hallazgo.lineas, [4, 6])


if __name__ == "__main__":
    unittest.main()
