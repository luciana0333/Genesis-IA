"""Variables de prueba comentadas: no son «Código SQL comentado» (Reportes y Procedimientos de negocio)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

PLANTILLA = """CREATE PROCEDURE dbo.PA_Colocaciones_Sel_Reporte
    @FECHA DATE,
    @AGENCIAS VARCHAR(300)
AS
BEGIN
{comentario}
    DECLARE
    @Usuario VARCHAR(4),
    @fechaSbs DATE;

    SELECT cAgeCod FROM dbo.Agencia WITH (NOLOCK) WHERE dFecha = @FECHA;
END
"""

CASO_DE_LA_USUARIA = """    --DECLARE
    --@FECHA DATE='20260930',
    --@AGENCIAS VARCHAR(300)='18',
    --@CODUSU VARCHAR(4)='LRCQ' ,
    --@CPRODUCTO VARCHAR(200)='205,307,312,202,209,310,322,309,208,207,303,206,221,121,102,101,305',
    --@CHONRAMIENTO VARCHAR(5)='SI,NO'"""


def comentados(comentario):
    sql = PLANTILLA.format(comentario=comentario)
    return {
        "reportes": [h.linea for h in verificar_reporte(sql) if h.regla == "CODIGO_SQL_COMENTADO"],
        "negocio": [h.linea for h in verificar_procedimiento_normal(sql) if h.regla == "CODIGO_SQL_COMENTADO"],
    }


class TestBloquesDePrueba(unittest.TestCase):
    def test_no_se_marcan(self):
        casos = {
            "caso de la usuaria": CASO_DE_LA_USUARIA,
            "un DECLARE por línea": "    --DECLARE @FECHA DATE = '20260930';\n    --DECLARE @AGENCIAS VARCHAR(300) = '18';",
            "con SET": "    --DECLARE @FECHA DATE\n    --SET @FECHA = '20260930'",
            "ejemplo de ejecución": "    -- Ejemplo de ejecución:\n"
                                    "    --EXEC dbo.PA_Colocaciones_Sel_Reporte @FECHA = '20260930', @AGENCIAS = '18'",
            "en bloque /* */": "    /*\n    DECLARE @FECHA DATE = '20260930',\n            @AGENCIAS VARCHAR(300) = '18'\n    */",
            "con GETDATE y NULL": "    --DECLARE @FECHA DATE = GETDATE(), @AGENCIAS VARCHAR(300) = NULL",
        }
        for nombre, comentario in casos.items():
            with self.subTest(nombre):
                self.assertEqual(comentados(comentario), {"reportes": [], "negocio": []})

    def test_codigo_real_comentado_si_se_marca(self):
        casos = {
            "consulta comentada": "    --SELECT cAgeCod FROM dbo.Agencia WHERE nId = 1",
            "DECLARE junto con una consulta": "    --DECLARE @FECHA DATE = '20260930'\n    --SELECT * FROM dbo.Agencia",
            "EXEC de otro procedimiento": "    --EXEC dbo.PA_Agencia_Upd_Estado @nId = 1",
            "UPDATE en bloque /* */": "    /*\n    DECLARE @n INT = 1\n    UPDATE dbo.Agencia SET cEstado = 'I'\n    */",
        }
        for nombre, comentario in casos.items():
            with self.subTest(nombre):
                resultado = comentados(comentario)
                self.assertTrue(resultado["reportes"], nombre)
                self.assertTrue(resultado["negocio"], nombre)


if __name__ == "__main__":
    unittest.main()
