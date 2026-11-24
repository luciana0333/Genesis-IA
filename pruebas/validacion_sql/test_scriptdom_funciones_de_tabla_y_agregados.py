"""Dos falsos positivos del validador en un reporte real (usuaria, 23 nov.).

Caso real PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral:
- «Función sobre la columna: TRIM(S.value)»: S es STRING_SPLIT, una función que devuelve una tabla y no tiene índices;
  la columna de la tabla física (AGE.cAgeCod) queda limpia, así que su índice sí se usa.
- «CASE sin ELSE» en MAX(CASE WHEN rol = @x THEN cPersCod END): pasa filas a columnas y el NULL es justo lo que se
  busca; un ELSE cambiaría el resultado del COALESCE(NULLIF(...)) que viene después.
"""
import unittest
from pathlib import Path

from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")


def _reglas(sql, regla):
    return [h.linea for h in validar_estructura(sql) if h.regla == regla]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class FuncionSobreColumnaDeFuncionDeTabla(unittest.TestCase):
    def test_columnas_de_funciones_de_tabla_no_se_marcan(self):
        casos = {
            "caso real (JOIN y WHERE)": "DECLARE @c VARCHAR(100) = '1,2'\n"
                                        "SELECT AGE.cAgeCod FROM STRING_SPLIT(@c, ',') S\n"
                                        "INNER JOIN dbo.Agencias AGE WITH (NOLOCK) ON AGE.cAgeCod = TRIM(S.value)\n"
                                        "WHERE TRIM(S.value) <> ''",
            "STRING_SPLIT solo": "DECLARE @c VARCHAR(100) = '1,2'\nSELECT S.value FROM STRING_SPLIT(@c, ',') S WHERE LTRIM(S.value) = '1'",
            "OPENJSON": "DECLARE @j NVARCHAR(MAX) = N'[]'\nSELECT J.value FROM OPENJSON(@j) J WHERE UPPER(J.value) = 'X'",
            "función de usuario": "SELECT F.c FROM dbo.fn_Lista(1) F WHERE UPPER(F.c) = 'X'",
            "nodos de un XML": "DECLARE @x XML = '<a/>'\n"
                               "SELECT N.c.value('.', 'VARCHAR(10)') FROM @x.nodes('/a') N(c) "
                               "WHERE UPPER(N.c.value('.', 'VARCHAR(10)')) = 'X'",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_reglas(sql, "FUNCION_SOBRE_COLUMNA"), [])

    def test_tabla_fisica_se_sigue_marcando(self):
        casos = {
            "tabla física": "SELECT a.cAgeCod FROM dbo.Agencias a WITH (NOLOCK) WHERE TRIM(a.cAgeCod) = '01'",
            "tabla física junto a STRING_SPLIT": "DECLARE @c VARCHAR(100) = '1,2'\n"
                                                 "SELECT a.cAgeCod FROM STRING_SPLIT(@c, ',') S\n"
                                                 "INNER JOIN dbo.Agencias a WITH (NOLOCK) ON TRIM(a.cAgeCod) = S.value",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertTrue(_reglas(sql, "FUNCION_SOBRE_COLUMNA"))


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class CaseSinElseEnAgregados(unittest.TestCase):
    def test_dentro_de_agregados_que_ignoran_null_no_se_marca(self):
        base = "SELECT r.cCtaCod, {} FROM dbo.ProductoPersona r WITH (NOLOCK) GROUP BY r.cCtaCod"
        casos = {
            "caso real MAX": "MAX(CASE WHEN r.nPrdPersRelac = 20 THEN r.cPersCod END) AS cCliente",
            "MIN": "MIN(CASE WHEN r.nPrdPersRelac = 20 THEN r.cPersCod END)",
            "COUNT": "COUNT(CASE WHEN r.nPrdPersRelac = 20 THEN 1 END)",
            "AVG": "AVG(CASE WHEN r.nPrdPersRelac = 20 THEN r.nMonto END)",
            "CASE simple": "MAX(CASE r.nPrdPersRelac WHEN 20 THEN r.cPersCod END)",
            "con paréntesis": "MAX((CASE WHEN r.nPrdPersRelac = 20 THEN r.cPersCod END))",
            "minúsculas": "max(case when r.nPrdPersRelac = 20 then r.cPersCod end)",
        }
        for nombre, expresion in casos.items():
            with self.subTest(nombre):
                self.assertEqual(_reglas(base.format(expresion), "CASE_SIN_ELSE"), [])

    def test_fuera_de_esos_agregados_se_sigue_marcando(self):
        casos = {
            "en el SELECT": "SELECT CASE WHEN a.n = 1 THEN 'A' END FROM dbo.T a WITH (NOLOCK)",
            "dentro de SUM": "SELECT SUM(CASE WHEN a.n = 1 THEN a.nMonto END) FROM dbo.T a WITH (NOLOCK)",
            "anidado en otra función": "SELECT MAX(ISNULL(CASE WHEN a.n = 1 THEN a.c END, '')) FROM dbo.T a WITH (NOLOCK)",
            "CASE suelto junto a un MAX": "SELECT MAX(a.c), CASE WHEN a.n = 1 THEN 'A' END FROM dbo.T a WITH (NOLOCK) GROUP BY a.n",
        }
        for nombre, sql in casos.items():
            with self.subTest(nombre):
                self.assertTrue(_reglas(sql, "CASE_SIN_ELSE"))


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class CasoReal(unittest.TestCase):
    def test_reporte_de_comites_de_creditos_fallidos(self):
        ruta = Path(__file__).parent / "recursos" / "PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral.sql"
        reglas = sorted({h.regla for h in validar_estructura(ruta.read_text(encoding="utf-8"))})
        self.assertEqual(reglas, ["ISNULL_VALIDAR_NULOS"])


if __name__ == "__main__":
    unittest.main()
