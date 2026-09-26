import unittest

from app.analizadores.propiedades_extendidas import leer_propiedades_extendidas


def _una(texto):
    llamadas = leer_propiedades_extendidas(texto)
    assert len(llamadas) == 1, llamadas
    return llamadas[0]


class TestLectorPropiedadesExtendidas(unittest.TestCase):
    def test_sentencias_sin_ningun_separador(self):
        texto = (
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'A'\n"
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'B'"
        )
        llamadas = leer_propiedades_extendidas(texto)
        self.assertEqual([ll.texto("value") for ll in llamadas], ["A", "B"])
        self.assertEqual([ll.linea for ll in llamadas], [1, 2])

    def test_cadenas_con_punto_y_coma_exec_y_comillas_escapadas(self):
        llamada = _una("EXEC sys.sp_addextendedproperty @name=N'MS_Description', "
                       "@value=N'Activo; ver EXEC sys.sp_addextendedproperty y l''otro';")
        self.assertEqual(llamada.texto("value"), "Activo; ver EXEC sys.sp_addextendedproperty y l'otro")
        self.assertEqual(llamada.errores, [])

    def test_ignora_comentarios(self):
        texto = (
            "-- EXEC sys.sp_addextendedproperty @name=N'x'\n"
            "/* EXEC sys.sp_addextendedproperty @name=N'y' */\n"
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'real'"
        )
        self.assertEqual(_una(texto).texto("value"), "real")

    def test_parametros_posicionales_sin_sys_y_execute(self):
        llamada = _una("EXECUTE [sys].[sp_addextendedproperty] N'MS_Description', N'Desc', "
                       "N'SCHEMA', N'dbo', N'TABLE', N'T'")
        self.assertEqual(llamada.texto("level1name"), "T")
        self.assertEqual(llamada.texto("value"), "Desc")

    def test_valores_sin_comillas_y_entre_corchetes(self):
        llamada = _una("EXEC sp_addextendedproperty @name=N'MS_Description', @value=N'x', "
                       "@level0type=N'SCHEMA', @level0name=dbo, @level1type=N'TABLE', @level1name=[Mi Tabla]")
        self.assertEqual(llamada.texto("level0name"), "dbo")
        self.assertFalse(llamada.argumentos["level0name"].entre_comillas)
        self.assertEqual(llamada.texto("level1name"), "Mi Tabla")

    def test_detecta_coma_sobrante_con_su_linea(self):
        llamada = leer_propiedades_extendidas(
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description',\n@value=N'x',\n\n"
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'y'"
        )[0]
        self.assertEqual(len(llamada.errores), 1)
        linea, mensaje = llamada.errores[0]
        self.assertEqual(linea, 2)
        self.assertIn("Coma sobrante", mensaje)

    def test_errores_de_sintaxis(self):
        casos = {
            "EXEC sys.sp_addextendedproperty @name N'MS_Description'": "Falta el signo '='",
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description' @value=N'x'": "Falta una coma",
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @levelX=N'a'": "no es válido",
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'sin cerrar": "no está cerrada",
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'a', @value=N'b'": "repetido",
        }
        for texto, esperado in casos.items():
            with self.subTest(texto=texto):
                mensajes = " | ".join(m for _, m in _una(texto).errores)
                self.assertIn(esperado, mensajes)


if __name__ == "__main__":
    unittest.main()
