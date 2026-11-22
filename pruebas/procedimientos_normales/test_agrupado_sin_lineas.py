"""Observaciones agrupadas sin repetir: las líneas van solo arriba de la observación y la frase no se repite por
cada caso (usuaria, 21 y 22 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte


def _de(regla, sql, verificar=verificar_procedimiento_normal):
    return [h for h in verificar(sql) if h.regla == regla]


class AgrupadoSinLineasTest(unittest.TestCase):
    def test_correo_repetido_una_sola_vez(self):
        # El mismo hecho en dos líneas: su mensaje una vez, sin «Se encontraron 2 observaciones de este tipo».
        sql = ("CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n"
               "EXEC msdb.dbo.sp_send_dbmail @recipients = 'a@b.pe', @body = 'x'\n"
               "SELECT 1\n"
               "EXEC msdb.dbo.sp_send_dbmail @recipients = 'c@d.pe', @body = 'y'\nEND")
        correo = _de("ENVIO_CORREO_DESDE_BD", sql)
        self.assertEqual(len(correo), 1)
        self.assertTrue(correo[0].mensaje.startswith("Se identificó un envío de correo desde la base de datos"))
        self.assertNotIn("Se encontraron", correo[0].mensaje)
        self.assertNotIn("línea", correo[0].mensaje)
        self.assertEqual(correo[0].lineas, [3, 5])

    def test_select_into_sin_repetir_la_frase(self):
        # Caso real (22 nov., Tablon.PA_BI_Ins_ColocacSaldoDia): tres tablas con SELECT INTO.
        tres = ("SELECT a.n INTO #TMP_Equipo1 FROM dbo.T a WITH (NOLOCK)\n"
                "SELECT DISTINCT a.n INTO #TMP_VIRTUAL FROM dbo.T a WITH (NOLOCK)\n"
                "SELECT a.n INTO #TB_Equipo FROM #TMP_Equipo1 a\n"
                "SELECT n FROM #TMP_VIRTUAL UNION SELECT n FROM #TB_Equipo")
        mensaje = _de("SELECT_INTO_PROHIBIDO", tres)[0].mensaje
        self.assertTrue(mensaje.startswith(
            "Se identificaron las siguientes tablas creadas con SELECT INTO: #TMP_Equipo1; #TMP_VIRTUAL; #TB_Equipo. "
            "Se recomienda crear primero la tabla con CREATE TABLE"), mensaje)
        self.assertEqual(mensaje.count("SELECT INTO"), 1)
        dos = "SELECT 1 AS n INTO #A\nSELECT 2 AS n INTO #B\nSELECT n FROM #A UNION SELECT n FROM #B"
        self.assertTrue(_de("SELECT_INTO_PROHIBIDO", dos)[0].mensaje.startswith(
            "Se identificó que las tablas #A y #B se crean con SELECT INTO. Se recomienda"))

    def test_collate_distinto_sin_repetir_la_frase(self):
        sql = ("CREATE TABLE #A (cA VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AI, "
               "cB VARCHAR(5) COLLATE Modern_Spanish_CI_AS, cC VARCHAR(5) COLLATE SQL_Latin1_General_CP1_CI_AI)\n"
               "SELECT cA, cB, cC FROM #A")
        mensaje = _de("COLLATE_DISTINTO_AL_ESTANDAR", sql)[0].mensaje
        self.assertTrue(mensaje.startswith(
            "Se identificaron los COLLATE SQL_Latin1_General_CP1_CI_AI y Modern_Spanish_CI_AS, distintos al que usa "
            "la empresa (SQL_Latin1_General_CP1_CI_AS). Valide si el COLLATE es el correcto"), mensaje)
        # El mismo COLLATE varias veces: su mensaje una vez.
        uno = "CREATE TABLE #A (cA VARCHAR(5) COLLATE Modern_Spanish_CI_AS, cB VARCHAR(5) COLLATE Modern_Spanish_CI_AS)"
        self.assertTrue(_de("COLLATE_DISTINTO_AL_ESTANDAR", uno + "\nSELECT cA, cB FROM #A")[0].mensaje.startswith(
            "Se identificó el COLLATE Modern_Spanish_CI_AS, distinto al que usa la empresa"))

    def test_merge_join_es_una_sugerencia_no_una_sentencia_merge(self):
        # Falso positivo (22 nov.): «OPTION (MERGE JOIN)» salía como «sentencia MERGE sobre la tabla JOIN».
        sql = "SELECT a.n FROM dbo.A a WITH (NOLOCK) JOIN dbo.B b WITH (NOLOCK) ON a.n = b.n OPTION (MERGE JOIN)"
        self.assertEqual(_de("MERGE_PROHIBIDO", sql), [])
        merge = "MERGE dbo.Cliente AS t USING #C AS s ON t.n = s.n WHEN MATCHED THEN UPDATE SET t.n = s.n;"
        self.assertEqual(len(_de("MERGE_PROHIBIDO", merge)), 1)

    def test_reportes_select_into_cuenta_tablas_distintas(self):
        from app.analizadores.analizador_reportes import verificar_reporte
        # La misma #Tmp dos veces: su mensaje una vez, no «Se identificaron 2 tablas …: #Tmp».
        sql = "SELECT 1 AS n INTO #Tmp\nDROP TABLE #Tmp\nSELECT 2 AS n INTO #Tmp\nSELECT n FROM #Tmp"
        hallazgo = _de("SELECT_INTO_PROHIBIDO", sql, verificar_reporte)[0]
        self.assertTrue(hallazgo.mensaje.startswith("Se identificó el uso de SELECT INTO para crear la tabla temporal #Tmp."))
        self.assertEqual(hallazgo.lineas, [1, 3])

    def test_reportes_el_mismo_hecho_una_sola_vez(self):
        # El texto genérico de Reportes (reglas sin texto agrupado propio): el mismo hecho dos veces, una sola vez.
        from app.analizadores.analizador_reportes import _agrupar_hallazgos_repetidos
        from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
        texto = "Se identificó el uso de X. Se recomienda retirarlo."
        grupo = [Hallazgo(linea=n, origen=OrigenAnalisis.REGLAS_ESTATICAS, severidad=Severidad.MEDIO,
                          regla="REGLA_PRUEBA", mensaje=texto) for n in (4, 9)]
        resultado = _agrupar_hallazgos_repetidos(grupo)
        self.assertEqual(len(resultado), 1)
        self.assertEqual(resultado[0].mensaje, texto)
        self.assertEqual(resultado[0].lineas, [4, 9])


if __name__ == "__main__":
    unittest.main()
