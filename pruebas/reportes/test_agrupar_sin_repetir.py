"""Varias observaciones de una regla en una sola, sin repetir la frase en cada caso (usuaria, 21 nov.).

Criterio: 2 casos en el párrafo; 3 en viñetas; más de 3 en tabla; lo mismo repetido, una sola frase.
Caso de la usuaria: «WITH (NOLOCK) en tabla temporal» mostraba «Se identificó que la tabla temporal #X tiene
WITH(NOLOCK)» en cada viñeta.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _de(verificar, sql, regla):
    return [h for h in verificar(sql) if h.regla == regla]


def _temporales(n):
    return "\n".join(f"SELECT a FROM #T{i} WITH (NOLOCK)" for i in range(1, n + 1))


class NolockEnTemporalTest(unittest.TestCase):
    def test_dos_en_el_parrafo(self):
        h = _de(verificar_reporte, _temporales(2), "NOLOCK_EN_TABLA_TEMPORAL")[0]
        self.assertEqual(
            h.mensaje,
            "Se identificó que las tablas temporales #T1 y #T2 tienen WITH(NOLOCK). Se recomienda retirarlo, ya que "
            "las tablas temporales solo existen en la sesión del reporte y no generan bloqueos con otros procesos.",
        )
        self.assertEqual(h.lineas, [1, 2])
        self.assertIsNone(getattr(h, "grupos", None))

    def test_tres_en_vinetas(self):
        h = _de(verificar_reporte, _temporales(3), "NOLOCK_EN_TABLA_TEMPORAL")[0]
        self.assertTrue(h.mensaje.startswith(
            "Se identificaron las siguientes tablas temporales con WITH(NOLOCK): #T1; #T2; #T3. Se recomienda"))
        self.assertIsNone(getattr(h, "grupos", None))

    def test_mas_de_tres_en_tabla(self):
        h = _de(verificar_reporte, _temporales(4) + "\nSELECT b FROM #T1 WITH (NOLOCK)", "NOLOCK_EN_TABLA_TEMPORAL")[0]
        self.assertEqual([(g["nombre"], g["tipo"], g["tituloDetalle"], g["columnas"]) for g in h.grupos], [
            ("#T1", "Tabla temporal", "Líneas", "1, 5"), ("#T2", "Tabla temporal", "Líneas", "2"),
            ("#T3", "Tabla temporal", "Líneas", "3"), ("#T4", "Tabla temporal", "Líneas", "4"),
        ])
        # «Ver en el código» recorre tabla por tabla.
        self.assertEqual(h.lineas, [1, 5, 2, 3, 4])
        self.assertEqual(h.mensaje[h.inicio_que_hacer:][:13], "Se recomienda")

    def test_la_misma_tabla_en_varias_lineas_es_un_caso(self):
        h = _de(verificar_reporte, "SELECT a FROM #T WITH (NOLOCK)\nSELECT b FROM #T WITH (NOLOCK)",
                "NOLOCK_EN_TABLA_TEMPORAL")[0]
        self.assertTrue(h.mensaje.startswith("Se identificó que la tabla temporal #T tiene WITH(NOLOCK)."))
        self.assertEqual(h.lineas, [1, 2])


class ModificaTablaFisicaTest(unittest.TestCase):
    def test_misma_tabla_con_dos_operaciones(self):
        h = _de(verificar_reporte, "INSERT INTO dbo.Lote SELECT 1\nUPDATE dbo.Lote SET n = 1 WHERE n = 0",
                "MODIFICACION_TABLA_FISICA")[0]
        self.assertTrue(h.mensaje.startswith(
            "Se identificó que el reporte modifica la tabla dbo.Lote (INSERT INTO, UPDATE). Se recomienda gestionar"))


# Dos casos de cada regla que antes caía en el agrupado genérico («Se encontraron N observaciones de este tipo»).
BATERIA = {
    "NOLOCK_EN_TABLA_TEMPORAL": _temporales(2),
    "MODIFICACION_TABLA_FISICA": "INSERT INTO dbo.A SELECT 1\nUPDATE dbo.B SET x = 1 WHERE y = 1",
    "HINT_BLOQUEO_PROHIBIDO": "SELECT 1 FROM dbo.A a WITH (UPDLOCK)\nSELECT 1 FROM dbo.B b WITH (HOLDLOCK)",
    "HINT_PLAN_PROHIBIDO": "SELECT 1 FROM dbo.A a WITH (FORCESEEK) WHERE a.x = 1 OPTION (RECOMPILE)",
    "CATALOGO_SISTEMA_PROHIBIDO": "SELECT name FROM sys.all_objects\nSELECT name FROM sys.objects",
    "ESQUEMA_OMITIDO_ENTRE_BASES": "SELECT 1 FROM DBCMACICA..Agencias a WITH(NOLOCK)\n"
                                   "SELECT 1 FROM DBCMACICA..Zonas z WITH(NOLOCK)",
    "VARCHAR_MAX_PROHIBIDO": "DECLARE @cA VARCHAR(MAX) = '', @cB VARCHAR(MAX) = ''\nSELECT @cA, @cB",
    "IN_CON_UN_SOLO_VALOR": "SELECT 1 FROM dbo.A a WITH(NOLOCK) WHERE a.x IN (1)\n"
                            "SELECT 1 FROM dbo.A a WITH(NOLOCK) WHERE a.y NOT IN (2)",
    "ORDER_BY_NUMERICO_PROHIBIDO": "SELECT a, b FROM dbo.A WITH(NOLOCK) ORDER BY 1\n"
                                   "SELECT a FROM dbo.A WITH(NOLOCK) ORDER BY 2",
    "WHILE_PROHIBIDO": "CREATE PROCEDURE dbo.PA_X AS\nBEGIN\nWHILE 1 = 0 BEGIN SELECT 1 END\n"
                       "WHILE 1 = 0 BEGIN SELECT 2 END\nEND",
    "COLLATE_DATABASE_DEFAULT": "SELECT a COLLATE DATABASE_DEFAULT FROM dbo.A WITH(NOLOCK)\n"
                                "SELECT b COLLATE DATABASE_DEFAULT FROM dbo.A WITH(NOLOCK)",
    "CAST_EN_JOIN_PROHIBIDO": "SELECT 1 FROM dbo.A a JOIN dbo.B b ON CAST(b.x AS INT) = a.x\n"
                              "SELECT 1 FROM dbo.A a JOIN dbo.C c ON CONVERT(INT, c.x) = a.x",
    "MODIFICACION_SIN_WHERE": "UPDATE dbo.A SET x = 1\nDELETE FROM dbo.B",
    "REPLACE_ANIDADO_TRANSLATE": "SELECT REPLACE(REPLACE(REPLACE(x, '.', ' '), '-', ' '), '/', ' ') FROM dbo.A\n"
                                 "SELECT REPLACE(REPLACE(REPLACE(y, '.', ' '), '-', ' '), '/', ' ') FROM dbo.A",
    "TEMPORAL_TEXTO_SIN_COLLATE": "CREATE TABLE #A (cA VARCHAR(5))\nCREATE TABLE #B (cB VARCHAR(5))",
    # Caso de la usuaria (21 nov.): «#BaseHechos (líneas 33, 68, 79)» dentro de la viñeta.
    "TEMPORAL_SIN_CREAR_VALIDAR": "SELECT a FROM #BaseHechos\nSELECT b FROM #PersonaRelacionCred\nSELECT c FROM #BaseHechos",
    "TABLA_REPETIDA_EN_CONSULTA": "SELECT 1 FROM dbo.A a\nJOIN dbo.C c1 ON c1.n = a.n\nJOIN dbo.C c2 ON c2.n = a.n\n"
                                  "JOIN dbo.C c3 ON c3.n = a.n\nJOIN dbo.C c4 ON c4.n = a.n;",
}


class NingunaRepiteLaFraseTest(unittest.TestCase):
    """Si una regla nueva o antigua vuelve al agrupado genérico, esta prueba falla."""

    def test_bateria_en_los_dos_modulos(self):
        vistas = set()
        for regla, sql in BATERIA.items():
            for verificar in MODULOS:
                for h in verificar(sql):
                    with self.subTest(regla=h.regla, modulo=verificar.__name__):
                        self.assertNotIn("observaciones de este tipo", h.mensaje)
                        # Las líneas van arriba de la tarjeta, no en el texto (usuaria, 21 nov.).
                        self.assertNotRegex(h.mensaje, r"\bl[ií]neas? \d")
                    if h.regla == regla:
                        vistas.add(regla)
                        # La frase de lo encontrado no se repite.
                        problema = h.mensaje[:getattr(h, "inicio_que_hacer", None) or len(h.mensaje)]
                        self.assertLessEqual(problema.lower().count("se identific") + problema.lower().count(
                            "se detect") + problema.lower().count("se verific"), 1, h.mensaje)
        # Cada regla de la batería se probó de verdad en algún módulo.
        self.assertEqual(vistas, set(BATERIA))


if __name__ == "__main__":
    unittest.main()
