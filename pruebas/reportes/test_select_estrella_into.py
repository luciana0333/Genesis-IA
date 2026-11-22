"""SELECT * que crea una tabla con INTO (usuaria, 22 nov.: «eso es grave»).

Caso real (Tablon.PA_BI_Ins_ColocacSaldoDia): «SELECT DISTINCT A.* INTO #TMP_VIRTUAL FROM …ColocCoordAgeVirtual a»
no se marcaba, ni en Reportes ni en Procedimientos: la regla esperaba una coma o el FROM después del A.*.
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_reporte, verificar_procedimiento_normal)


def _estrella(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "SELECT_ESTRELLA_PROHIBIDO"]


class SelectEstrellaIntoTest(unittest.TestCase):
    def test_alias_estrella_con_into_y_la_tabla_correcta(self):
        # Sin «;» y con otro alias «a» antes (TipoCambio): la tabla es la del FROM que sigue al A.*.
        sql = ("DECLARE @nTC MONEY\n"
               "SET @nTC = (SELECT TOP 1 a.nValFijo FROM DBCMACICA11.dbo.TipoCambio a WITH(NOLOCK) ORDER BY a.dFecCamb DESC)\n"
               "SELECT A.cCodCoordinador, A.cCodAnalista\nINTO #TMP_Equipo1\n"
               "FROM DBCMACICA11.colocaciones.ColocAnaCoordAsigna a WITH (NOLOCK)\n\n"
               "SELECT DISTINCT A.*\nINTO #TMP_VIRTUAL\n"
               "FROM DBCMACICA11.COLOCACIONES.ColocCoordAgeVirtual a WITH (NOLOCK)\n"
               "\tINNER JOIN DBCMACICA11.COLOCACIONES.ColocAnaCoordAsigna b WITH (NOLOCK) ON A.ccodcoordinador = b.ccodcoordinador\n"
               "WHERE bEstado = 1\n\n"
               "UPDATE B SET b.cCodCoordinador = a.cCodAnalista FROM #TMP_VIRTUAL A INNER JOIN #TMP_Equipo1 B ON 1 = 1")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _estrella(sql, verificar)
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("ColocCoordAgeVirtual", hallazgos[0].mensaje)
                self.assertNotIn("TipoCambio", hallazgos[0].mensaje)

    def test_estrella_tras_coma_con_into(self):
        sql = "SELECT 1 AS n, * INTO #X FROM dbo.Tabla WITH (NOLOCK)\nSELECT n FROM #X"
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(len(_estrella(sql, verificar)), 1)

    def test_lo_que_no_es_select_estrella(self):
        # COUNT(*) con INTO y una multiplicación antes de INTO no son SELECT *.
        for sql in ("SELECT COUNT(*) AS n INTO #X FROM dbo.Tabla WITH (NOLOCK)\nSELECT n FROM #X",
                    "SELECT a.nMonto * 2 AS n INTO #X FROM dbo.Tabla a WITH (NOLOCK)\nSELECT n FROM #X"):
            for verificar in MODULOS:
                with self.subTest(sql=sql[:30], modulo=verificar.__name__):
                    self.assertEqual(_estrella(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
