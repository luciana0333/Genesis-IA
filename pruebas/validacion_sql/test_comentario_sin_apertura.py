"""Encabezado al que le falta el /* (usuaria, 23 nov.).

Caso real PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral: el encabezado empezaba en «PROCEDIMIENTO : …» sin el
/* y terminaba en «*****/». El validador debe decir que falta abrir el comentario (no solo «sintaxis incorrecta cerca de
'PROCEDIMIENTO'») y las buenas prácticas no deben decir que no hay encabezado.
"""
import unittest
from pathlib import Path

from app.analizadores.comentario_sin_apertura import cierre_sin_apertura, encabezado_sin_abrir
from app.analizadores.encabezado import encabezado_observado, nombre_del_encabezado_distinto
from app.analizadores.scriptdom import LECTOR_SCRIPTDOM, validar_estructura

DISPONIBLE = LECTOR_SCRIPTDOM.estado().get("disponible")

CUERPO = ("ALTER PROCEDURE dbo.PA_Prueba_Sel(@n INT)\nAS\nBEGIN\n"
          "    SELECT a.n FROM dbo.T a WITH (NOLOCK) WHERE a.n = @n\nEND\n")
ENCABEZADO = ("PROCEDIMIENTO : dbo.PA_Prueba_Sel\n"
              "PROPOSITO     : Lista las pruebas\n"
              "AUTOR         : LMPE\n"
              "FECHA         : 04/08/2025\n"
              "Control de Cambios\n"
              "Fecha | Autor | Descripción\n"
              "EXEC dbo.PA_Prueba_Sel 1\n")


class DetectarCierreSinApertura(unittest.TestCase):
    def test_casos(self):
        casos = {
            "falta el /*": (ENCABEZADO + "*****/\n" + CUERPO, True),
            "encabezado completo": ("/*" + ENCABEZADO + "*/\n" + CUERPO, False),
            "comentarios anidados": ("/* a /* b */ c */\n" + CUERPO, False),
            "*/ dentro de un texto": (CUERPO + "SELECT '*/'\n", False),
            "*/ dentro de un comentario --": ("-- fin */\n" + CUERPO, False),
            "comilla escapada": ("SELECT 'it''s */'\n" + CUERPO, False),
            "anidado con un cierre de más": ("/* a /* b */ c */ */\n" + CUERPO, True),
        }
        for nombre, (sql, esperado) in casos.items():
            with self.subTest(nombre):
                self.assertEqual(cierre_sin_apertura(sql) is not None, esperado)

    def test_el_tramo_empieza_en_la_primera_etiqueta(self):
        sql = "\n\n" + ENCABEZADO + "*****/\n" + CUERPO
        inicio, fin = encabezado_sin_abrir(sql)
        self.assertTrue(sql[inicio:].startswith("PROCEDIMIENTO"))
        self.assertTrue(sql[:fin].endswith("*****/"))


class BuenasPracticas(unittest.TestCase):
    def test_sin_apertura_no_dice_que_no_hay_encabezado(self):
        sql = ENCABEZADO + "*****/\n" + CUERPO
        self.assertIsNone(encabezado_observado(sql, sql))

    def test_sin_apertura_sigue_revisando_el_nombre(self):
        sql = ENCABEZADO.replace("PROCEDIMIENTO : dbo.PA_Prueba_Sel", "PROCEDIMIENTO : dbo.PA_Otro") + "*/\n" + CUERPO
        self.assertEqual(nombre_del_encabezado_distinto(sql, sql)[1:], ("dbo.PA_Otro", "dbo.PA_Prueba_Sel"))

    def test_sin_encabezado_se_sigue_marcando(self):
        self.assertIn("no cuenta con un encabezado", encabezado_observado(CUERPO, CUERPO)[1])


def _sintaxis(sql):
    return [h for h in validar_estructura(sql) if h.regla == "ERROR_SINTAXIS"]


@unittest.skipUnless(DISPONIBLE, "Esta PC no tiene ScriptDom (viene con SSMS).")
class Validador(unittest.TestCase):
    def test_falta_el_slash_asterisco_del_encabezado(self):
        errores = _sintaxis(ENCABEZADO + "*****/\n" + CUERPO)
        self.assertEqual(len(errores), 1)
        self.assertIn("falta abrir el comentario del encabezado (/*)", errores[0].mensaje)
        self.assertIn("«PROCEDIMIENTO : dbo.PA_Prueba_Sel» de la línea 1", errores[0].mensaje)
        self.assertIn("cierre */ de la línea 8", errores[0].mensaje)
        self.assertIn("crear el procedimiento", errores[0].mensaje)
        self.assertEqual(errores[0].lineas, [1, 8])

    def test_comentario_que_no_es_encabezado(self):
        errores = _sintaxis(CUERPO.replace("    SELECT", "    se busca la prueba */\n    SELECT"))
        self.assertEqual(len(errores), 1)
        self.assertIn("cierre de comentario */ en la línea 4 sin su apertura /*", errores[0].mensaje)

    def test_error_despues_del_cierre_se_conserva(self):
        sql = ENCABEZADO + "*/\n" + CUERPO.replace("WHERE a.n = @n", "WHERE a.n = = @n")
        errores = _sintaxis(sql)
        self.assertGreaterEqual(len(errores), 1)
        self.assertIn("falta abrir el comentario", errores[0].mensaje)

    def test_falta_el_cierre_sigue_como_antes(self):
        errores = _sintaxis("/*" + ENCABEZADO + CUERPO)
        self.assertTrue(errores)
        self.assertNotIn("falta abrir", errores[0].mensaje)

    def test_encabezado_con_guiones_no_se_marca(self):
        sql = "".join("-- " + linea + "\n" for linea in ENCABEZADO.splitlines()) + CUERPO
        self.assertEqual(_sintaxis(sql), [])

    def test_caso_real(self):
        ruta = Path(__file__).parent / "recursos" / "PA_GDD_CredFallidoComiteDetalle_sin_apertura.sql"
        if not ruta.exists():
            self.skipTest("Falta el archivo del caso real.")
        errores = _sintaxis(ruta.read_text(encoding="utf-8"))
        self.assertEqual(len(errores), 1)
        self.assertIn("falta abrir el comentario del encabezado", errores[0].mensaje)


if __name__ == "__main__":
    unittest.main()
