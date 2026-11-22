"""VARCHAR(MAX): solo justifica el JSON/XML de la misma sentencia, aunque el código no use ';' (usuaria, 21 nov.).

Caso real (FluGenSol_InsPropuesta_SP): sin ';' la «sentencia» era un bloque de miles de líneas y un .value( lejano
justificaba @cCodError (va en un THROW), @cError y @psCalif (OUTPUT de un EXEC).
"""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

MODULOS = (verificar_procedimiento_normal, verificar_reporte)

SIN_PUNTO_Y_COMA = (
    "ALTER PROCEDURE dbo.PA_Prueba @xDatos XML, @cCodError VARCHAR(MAX) = '' OUTPUT AS\n"
    "BEGIN\n"
    " DECLARE @cError VARCHAR(MAX)\n"
    " ,@cComentario VARCHAR(MAX)\n"
    " SELECT @cComentario = T.Item.value('@cObs', 'VARCHAR(500)') FROM @xDatos.nodes('Dto') T(Item)\n"
    " EXEC dbo.PA_Otro @cError OUTPUT\n"
    " IF @cError <> '' PRINT @cComentario\n"
    " SELECT TOP 1 @cCodError = 'Error: ' + @cError\n"
    " THROW 50000, @cCodError, 1\n"
    "END"
)


def _marcadas(sql, verificar):
    return [h for h in verificar(sql) if h.regla == "VARCHAR_MAX_PROHIBIDO"]


class VarcharMaxSentenciaRealTest(unittest.TestCase):
    def test_un_xml_de_otra_sentencia_no_justifica(self):
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                hallazgos = _marcadas(SIN_PUNTO_Y_COMA, verificar)
                self.assertEqual(len(hallazgos), 1)
                mensaje = hallazgos[0].mensaje
                self.assertIn("@cCodError", mensaje)
                self.assertIn("@cError", mensaje)
                # @cComentario se llena con el .value( de su propia sentencia: se justifica.
                self.assertNotIn("@cComentario", mensaje)

    def test_el_xml_en_la_misma_sentencia_sigue_justificando(self):
        sql = ("DECLARE @x XML = '<a/>'\nDECLARE @c VARCHAR(MAX)\n"
               "SET @c = (SELECT T.N.value('.', 'VARCHAR(100)') FROM @x.nodes('a') T(N))\nSELECT @c")
        for verificar in MODULOS:
            with self.subTest(modulo=verificar.__name__):
                self.assertEqual(_marcadas(sql, verificar), [])


if __name__ == "__main__":
    unittest.main()
