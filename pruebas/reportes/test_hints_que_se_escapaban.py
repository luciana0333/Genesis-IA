"""Hints que se escapaban o se marcaban de más (2 nov., Reportes y Negocio, aprobado por la usuaria)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

AREAS = {"Reportes": verificar_reporte, "Negocio": verificar_procedimiento_normal}
HINTS = {"HINT_PLAN_PROHIBIDO", "HINT_BLOQUEO_PROHIBIDO", "INDICE_FORZADO"}


def _hints(verificar, sql):
    return [h for h in verificar(sql) if h.regla in HINTS]


class HintsQueSeEscapabanTest(unittest.TestCase):
    def test_ahora_se_detectan(self):
        casos = {
            "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE\nSELECT a FROM dbo.T WITH (NOLOCK)": "HINT_BLOQUEO_PROHIBIDO",
            "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ\nSELECT a FROM dbo.T WITH (NOLOCK)":
                "HINT_BLOQUEO_PROHIBIDO",
            "SET FORCEPLAN ON\nSELECT a FROM dbo.T WITH (NOLOCK)": "HINT_PLAN_PROHIBIDO",
            "SELECT a FROM dbo.T t WITH (NOLOCK) INNER REMOTE JOIN dbo.U u WITH (NOLOCK) ON u.a = t.a":
                "HINT_PLAN_PROHIBIDO",
            "SELECT a FROM dbo.T WITH (NOWAIT)": "HINT_BLOQUEO_PROHIBIDO",
            "SELECT a FROM dbo.T WITH (READCOMMITTEDLOCK)": "HINT_BLOQUEO_PROHIBIDO",
            "SELECT a FROM dbo.T WITH (SNAPSHOT)": "HINT_BLOQUEO_PROHIBIDO",
            "SELECT a FROM dbo.T WITH (NOLOCK, INDEX = IX_T_a)": "INDICE_FORZADO",
        }
        for area, verificar in AREAS.items():
            for sql, regla in casos.items():
                with self.subTest(area=area, sql=sql):
                    self.assertEqual([h.regla for h in _hints(verificar, sql)], [regla])

    def test_nivel_de_aislamiento_dice_que_aplica_a_todo(self):
        sql = "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE\nSELECT a FROM dbo.T WITH (NOLOCK)"
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                mensaje = _hints(verificar, sql)[0].mensaje
                self.assertIn("'SET TRANSACTION ISOLATION LEVEL SERIALIZABLE'", mensaje)
                self.assertIn("en todas las consultas que siguen en el procedimiento", mensaje)

    def test_no_se_marca(self):
        for sql in (
            # Palabras dentro del nombre de una columna.
            "SELECT nFastId, cRecompileFlag FROM dbo.T WITH (NOLOCK)",
            # Bloqueos en temporales y variables de tabla: no detienen a otros procesos.
            "INSERT INTO #T WITH (TABLOCK) (a) SELECT a FROM dbo.T WITH (NOLOCK)",
            "SELECT a FROM #T t WITH (UPDLOCK)",
            "SELECT a FROM @T WITH (TABLOCK)",
            # READUNCOMMITTED es lo mismo que NOLOCK.
            "SELECT a FROM dbo.T WITH (READUNCOMMITTED)",
        ):
            for area, verificar in AREAS.items():
                with self.subTest(area=area, sql=sql):
                    self.assertEqual(_hints(verificar, sql), [])

    def test_readuncommitted_en_temporal_es_nolock_en_temporal(self):
        for area, verificar in AREAS.items():
            with self.subTest(area=area):
                reglas = [h.regla for h in verificar("SELECT a FROM #T WITH (READUNCOMMITTED)")]
                self.assertIn("NOLOCK_EN_TABLA_TEMPORAL", reglas)


if __name__ == "__main__":
    unittest.main()
