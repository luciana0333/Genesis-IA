# -*- coding: utf-8 -*-
"""Glosario de siglas: aprobar una sigla desde la pantalla la acepta al instante en tablas y procedimientos."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.analizadores import siglas
from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_tablas import verificar_tabla

TABLA = """CREATE TABLE Bonificacion.MetaTPPP (
    nMetaTPPPId INT IDENTITY(1,1) PRIMARY KEY,
    nSaldoTCF DECIMAL(18,2) NOT NULL
)
"""


class TestGlosarioSiglas(unittest.TestCase):
    def setUp(self):
        carpeta = tempfile.mkdtemp()
        self.locales = Path(carpeta) / "siglas_locales.txt"
        self.parche = mock.patch.object(siglas, "_LOCALES", self.locales)
        self.parche.start()
        siglas.siglas_aprobadas.cache_clear()

    def tearDown(self):
        self.parche.stop()
        siglas.siglas_aprobadas.cache_clear()

    def test_observaciones_indican_sus_siglas_por_validar(self):
        hallazgos = {h.regla: h for h in verificar_tabla(TABLA)}
        self.assertEqual(hallazgos["TABLA_NOMBRE_CON_SIGLA"].siglas, ["TPPP"])
        self.assertEqual(sorted(hallazgos["COLUMNA_NOMBRE_CON_SIGLA"].siglas), ["TCF", "TPPP"])

    def test_aprobar_sigla_la_acepta_al_instante(self):
        self.assertEqual(siglas.aprobar_sigla(" tppp ", "Tasa  Promedio Ponderada Pasiva"), "TPPP")
        self.assertIn("TPPP = Tasa Promedio Ponderada Pasiva", self.locales.read_text(encoding="utf-8"))
        hallazgos = {h.regla: h for h in verificar_tabla(TABLA)}
        self.assertNotIn("TABLA_NOMBRE_CON_SIGLA", hallazgos)
        self.assertEqual(hallazgos["COLUMNA_NOMBRE_CON_SIGLA"].siglas, ["TCF"])
        reglas = {h.regla for h in verificar_procedimiento_normal(
            "CREATE PROCEDURE dbo.PA_MetaTPPP_Sel_PorAgencia AS SELECT 1")}
        self.assertNotIn("PROCEDIMIENTO_NOMBRE_CON_SIGLA", reglas)

    def test_datos_invalidos(self):
        for sigla, texto in (("T", "x"), ("TPPP1", "x"), ("TPPP", ""), ("TPPP", "a = b"), ("TPPP", "x" * 151)):
            with self.subTest(sigla=sigla, texto=texto[:10]):
                with self.assertRaises(ValueError):
                    siglas.aprobar_sigla(sigla, texto)
        self.assertFalse(self.locales.exists())


if __name__ == "__main__":
    unittest.main()
