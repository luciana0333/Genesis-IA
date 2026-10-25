"""Diccionario dentro de BEGIN TRANSACTION / TRY sin «;»: lo que sigue (COMMIT, END...) no es texto sobrante."""

import unittest

from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.propiedades_extendidas import leer_propiedades_extendidas

TABLA = """CREATE TABLE RRHH.CumplimientoMetasPer (
    nCierreTapp DECIMAL(18,2) NOT NULL,
    nCierreTad DECIMAL(18,2) NOT NULL
);"""

# Como llegan los diccionarios de la usuaria: transacción, TRY/CATCH y sin «;» después de cada EXEC.
DICCIONARIO = """BEGIN TRANSACTION
BEGIN TRY
	SET NOCOUNT ON

	EXEC sys.sp_addextendedproperty
	@name=N'MS_Description', @value=N'Indica la tasa promedio ponderada al cierre del mes anterior.',
	@level0type=N'SCHEMA', @level0name=N'RRHH',
	@level1type=N'TABLE', @level1name=N'CumplimientoMetasPer',
	@level2type=N'COLUMN', @level2name=N'nCierreTapp'


	EXEC sys.sp_addextendedproperty
	@name=N'MS_Description', @value=N'Indica la tasa promedio ponderada de desembolso al cierre del mes anterior',
	@level0type=N'SCHEMA', @level0name=N'RRHH',
	@level1type=N'TABLE', @level1name=N'CumplimientoMetasPer',
	@level2type=N'COLUMN', @level2name=N'nCierreTad'


	COMMIT TRANSACTION

	SET NOCOUNT OFF

	PRINT '[OK] Diccionario creado correctamente.';
END TRY
BEGIN CATCH
	IF XACT_STATE() <> 0 ROLLBACK TRANSACTION
	PRINT 'LINE: ' + CAST(ERROR_LINE() AS VARCHAR(5))
	PRINT 'ERROR: ' + ERROR_MESSAGE()
END CATCH
"""


class TestDiccionarioEnTransaccion(unittest.TestCase):
    def test_commit_despues_del_ultimo_exec_no_es_texto_sobrante(self):
        llamadas = leer_propiedades_extendidas(DICCIONARIO)
        self.assertEqual(len(llamadas), 2)
        self.assertEqual([ll.errores for ll in llamadas], [[], []])
        self.assertEqual(llamadas[1].texto("level2name"), "nCierreTad")

    def test_revision_sin_error_de_sintaxis(self):
        reglas = {h.regla for h in verificar_diccionario_tablas(TABLA, DICCIONARIO)}
        self.assertNotIn("SINTAXIS_DICCIONARIO", reglas)

    def test_otras_sentencias_que_siguen_tampoco(self):
        for siguiente in ("END TRY", "SET NOCOUNT OFF", "PRINT 'ok'", "IF @@ERROR <> 0 ROLLBACK", "SELECT 1", "GO"):
            with self.subTest(siguiente=siguiente):
                texto = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'x', "
                         "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'T'\n"
                         + siguiente)
                self.assertEqual(leer_propiedades_extendidas(texto)[0].errores, [])

    def test_texto_que_si_sobra_se_sigue_marcando(self):
        texto = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'x', "
                 "@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'T' hola")
        errores = leer_propiedades_extendidas(texto)[0].errores
        self.assertEqual(len(errores), 1)
        self.assertIn("texto que sobra después de @level1name: 'hola'", errores[0][1])


if __name__ == "__main__":
    unittest.main()
