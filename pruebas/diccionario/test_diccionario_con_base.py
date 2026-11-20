"""Diccionario que llama a sp_addextendedproperty con la base delante (caso real de la usuaria, 20 nov.).

EXEC DBAGENDACOMERCIAL.sys.sp_addextendedproperty es válido en SQL Server, pero Genesis no lo leía y decía que las
columnas no estaban documentadas aunque sí lo estaban.
"""

import unittest

from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.propiedades_extendidas import leer_propiedades_extendidas

TABLA = """ALTER TABLE DBAGENDACOMERCIAL.dbo.SolicitudOportunidad
    ADD bOnboarding BIT NOT NULL DEFAULT 0;

ALTER TABLE DBAGENDACOMERCIAL.dbo.SolicitudOportunidad
    ADD bOtp BIT NOT NULL DEFAULT 0;"""

DICCIONARIO = """BEGIN TRY

BEGIN TRANSACTION;

EXEC DBAGENDACOMERCIAL.sys.sp_addextendedproperty
        @name = N'MS_Description',
        @value = N'Indica si el cliente completó correctamente el proceso de onboarding: 0 = pendiente, 1 = completado.',
        @level0type = N'SCHEMA', @level0name = N'dbo',
        @level1type = N'TABLE',  @level1name = N'SolicitudOportunidad',
        @level2type = N'COLUMN', @level2name = N'bOnboarding';

EXEC DBAGENDACOMERCIAL.sys.sp_addextendedproperty
        @name = N'MS_Description',
        @value = N'Indica si el cliente completó correctamente el proceso de OTP: 0 = pendiente, 1 = completado.',
        @level0type = N'SCHEMA', @level0name = N'dbo',
        @level1type = N'TABLE',  @level1name = N'SolicitudOportunidad',
        @level2type = N'COLUMN', @level2name = N'bOtp';

COMMIT TRANSACTION;

END TRY
BEGIN CATCH

IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;

END CATCH;"""


class DiccionarioConBaseTest(unittest.TestCase):
    def test_caso_real_sin_observaciones(self):
        self.assertEqual([h.regla for h in verificar_diccionario_tablas(TABLA, DICCIONARIO)], [])

    def test_formas_de_llamar_al_procedimiento(self):
        formas = ("DBAGENDACOMERCIAL.sys.", "[DBAGENDACOMERCIAL].[sys].", "DBAGENDACOMERCIAL..", "sys.", "")
        for forma in formas:
            with self.subTest(forma=forma):
                texto = DICCIONARIO.replace("DBAGENDACOMERCIAL.sys.", forma)
                self.assertEqual(len(leer_propiedades_extendidas(texto)), 2)
        # Otro procedimiento con nombre parecido no cuenta.
        self.assertEqual(len(leer_propiedades_extendidas(
            DICCIONARIO.replace("DBAGENDACOMERCIAL.sys.sp_addextendedproperty", "dbo.sp_addextendedpropertyX"))), 0)


if __name__ == "__main__":
    unittest.main()
