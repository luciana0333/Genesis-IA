"""Clave primaria heredada de la tabla padre (caso poco común; usuaria, 21 nov.).

Caso real: CAPTACIONES.DisponibilidadRetiroCuentaCTS (cCtaCod VARCHAR(18) PRIMARY KEY REFERENCES dbo.CaptacCTS).
La PK es también la relación uno a uno con su tabla padre y conserva su tipo: pedir «INT IDENTITY» o renombrarla
rompería la relación. En vez de «PK sin IDENTITY», «PK no numérica» y «nombre de la PK», sale una sola observación
aparte («Casos poco comunes»), para validar con el DBA.
"""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla

CASO_REAL = """CREATE TABLE CAPTACIONES.DisponibilidadRetiroCuentaCTS
(
\tcCtaCod VARCHAR(18)\t\tPRIMARY KEY REFERENCES dbo.CaptacCTS (cCtaCod),
\tbEnfermedadTerminal\t\tBIT NOT NULL DEFAULT 0,
\tnDocumentoGestionCTSId\tINT
)
GO"""

CON_CONSTRAINT = """CREATE TABLE CAPTACIONES.DisponibilidadRetiroCuentaCTS (
 cCtaCod VARCHAR(18) NOT NULL,
 bEnfermedadTerminal BIT NOT NULL CONSTRAINT DF_X DEFAULT 0,
 CONSTRAINT PK_X PRIMARY KEY CLUSTERED (cCtaCod),
 CONSTRAINT FK_X FOREIGN KEY (cCtaCod) REFERENCES [dbo].[CaptacCTS] (cCtaCod))"""

_PK = {"PK_SIN_IDENTITY", "PK_NO_NUMERICA", "PK_NOMBRE_INVALIDO"}


class PkHeredadaTest(unittest.TestCase):
    def test_caso_real_una_sola_observacion_aparte(self):
        for es_dbcmaica in (True, False):
            with self.subTest(dbcmaica=es_dbcmaica):
                hallazgos = verificar_tabla(CASO_REAL, es_dbcmaica)
                reglas = {h.regla for h in hallazgos}
                self.assertFalse(reglas & _PK)
                heredada = next(h for h in hallazgos if h.regla == "PK_HEREDADA")
                self.assertTrue(heredada.poco_comun)
                self.assertEqual(heredada.severidad.value, "bajo")
                self.assertEqual(heredada.linea, 3)
                self.assertEqual(
                    heredada.mensaje,
                    "Se identificó que la clave primaria cCtaCod también es la relación con dbo.CaptacCTS (uno a "
                    "uno), por eso es VARCHAR(18) y no autoincremental. Validar con el DBA, ya que es una excepción "
                    "al estándar de clave primaria.",
                )

    def test_con_constraint_y_foreign_key_aparte(self):
        reglas = {h.regla for h in verificar_tabla(CON_CONSTRAINT, True)}
        self.assertIn("PK_HEREDADA", reglas)
        self.assertFalse(reglas & _PK)

    def test_tabla_normal_sigue_igual(self):
        reglas = {h.regla for h in verificar_tabla(
            "CREATE TABLE dbo.Prueba (cCodigo VARCHAR(10) PRIMARY KEY, cNombre VARCHAR(20) NOT NULL)", True)}
        self.assertTrue(_PK <= reglas)
        self.assertNotIn("PK_HEREDADA", reglas)
        # Una FK en otra columna no convierte la PK en heredada.
        reglas = {h.regla for h in verificar_tabla(
            "CREATE TABLE dbo.Prueba (cCodigo VARCHAR(10) PRIMARY KEY, nClienteId INT NOT NULL "
            "REFERENCES dbo.Cliente (nClienteId))", True)}
        self.assertIn("PK_SIN_IDENTITY", reglas)
        self.assertNotIn("PK_HEREDADA", reglas)


if __name__ == "__main__":
    unittest.main()
