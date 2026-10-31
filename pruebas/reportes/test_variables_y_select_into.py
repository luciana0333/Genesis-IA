"""Variables sin uso (se observa la que se declara y nunca más aparece) y SELECT INTO con subconsultas
(Reportes y Negocio)."""

import re
import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _pa(cuerpo):
    return f"CREATE PROCEDURE dbo.PA_Prueba_Sel_Datos\n@p INT\nAS\nBEGIN\n{cuerpo}\nEND"


def _sin_uso(verificar, cuerpo):
    return sorted({v for h in verificar(_pa(cuerpo)) if h.regla == "VARIABLE_DECLARADA_SIN_USO"
                   for v in re.findall(r"@\w+", h.mensaje)})


class VariablesSinUsoTest(unittest.TestCase):
    def _en_los_dos(self, cuerpo, esperado):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__, cuerpo=cuerpo):
                self.assertEqual(_sin_uso(verificar, cuerpo), esperado)

    def test_varias_en_un_mismo_declare(self):
        self._en_los_dos("DECLARE @a INT = 1, @b INT = 2\nSELECT @a", ["@b"])
        self._en_los_dos("DECLARE @m DECIMAL(18,2), @k INT\nSELECT @m", ["@k"])
        self._en_los_dos("DECLARE @x INT = CASE WHEN @p = 1 THEN 1 END, @y INT = 2\nSELECT @x", ["@y"])

    def test_si_vuelve_a_aparecer_ya_tiene_uso(self):
        # Regla de la usuaria (30 oct.): aunque solo reciba un valor o filas, ya se usa (los dos módulos).
        for cuerpo in (
            "DECLARE @n INT\nSET @n = 5",
            "DECLARE @n INT = 0\nSET @n += 1",
            "DECLARE @dMax DATE\nSELECT @dMax = MAX(dFecha) FROM dbo.Mov WITH(NOLOCK)",
            "DECLARE @a INT, @b INT\nSELECT @a = 1, @b = 2\nSELECT @b",
            "DECLARE @a INT, @b INT\nDECLARE c CURSOR FOR SELECT 1, 2\nOPEN c\nFETCH NEXT FROM c INTO @a, @b\nPRINT @a",
            "DECLARE @T TABLE (n INT)\nINSERT INTO @T (n) VALUES (1)",
            "DECLARE @T TABLE (n INT)\nINSERT @T EXEC dbo.PA_Otro",
            "DECLARE @T TABLE (n INT)\nUPDATE #A SET n = 1 OUTPUT inserted.n INTO @T",
        ):
            self._en_los_dos(cuerpo, [])

    def test_solo_en_un_comentario_o_texto_se_observa(self):
        self._en_los_dos("DECLARE @nTotal INT\n-- SET @nTotal = 1\nSELECT 'Total: @nTotal'", ["@nTotal"])

    def test_se_usan_al_menos_una_vez(self):
        for cuerpo in (
            "DECLARE @i INT = 0\nWHILE @i < 10 SET @i = @i + 1",
            "DECLARE @x INT\nIF @x IS NULL SELECT 1",
            "DECLARE @T TABLE (n INT)\nINSERT INTO @T (n) VALUES (1)\nSELECT n FROM @T",
            "DECLARE @ret INT\nEXEC @ret = dbo.PA_Otro\nRETURN @ret",
            "DECLARE @x INT\nEXEC dbo.PA_Otro @cMensaje = @x OUTPUT",
            "DECLARE @u DATE\nSELECT TOP 1 @u = dFecha FROM dbo.A WITH(NOLOCK)\nSET @u = IIF(@p > 1, @u, GETDATE())",
            "DECLARE @nTotal INT = 1\nSELECT @NTOTAL",
            "DECLARE @x INT = 1\nSELECT CASE WHEN @x = 1 THEN 'a' END",
            "DECLARE c CURSOR FOR SELECT 1\nOPEN c",
        ):
            self._en_los_dos(cuerpo, [])


class SelectIntoConSubconsultaTest(unittest.TestCase):
    def test_subconsulta_en_el_select(self):
        sql = _pa("SELECT (SELECT MAX(nId) FROM dbo.B WITH(NOLOCK)) AS nMax INTO #C FROM dbo.A WITH(NOLOCK)")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertIn("SELECT_INTO_PROHIBIDO", {h.regla for h in verificar(sql)})

    def test_fetch_into_no_es_select_into(self):
        sql = _pa("DECLARE @a INT\nSELECT @a = 1\nDECLARE c CURSOR FOR SELECT 1\nOPEN c\nFETCH c INTO @a\nPRINT @a")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertNotIn("SELECT_INTO_PROHIBIDO", {h.regla for h in verificar(sql)})


if __name__ == "__main__":
    unittest.main()
