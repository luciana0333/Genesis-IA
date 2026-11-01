"""Diccionario de procedimientos: en un ALTER se agrega (ADD) la descripción de lo que ya existía.

Igual que en el diccionario de tablas («Validar documentación existente», bajo): no es error, pero
sp_addextendedproperty falla si el procedimiento o el parámetro ya estaba documentado. Una sola
observación para todo el script.
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario

_ACCION = ("Verificar si ya cuentan con descripción en el diccionario, ya que de ser así la ejecución del "
           "script fallará. En ese caso, retirar esas sentencias o reemplazarlas por sentencias de "
           "actualización (sp_updateextendedproperty).")


def _exec(proc, parametro=None, operacion="ADD", valor="Descripción del dato"):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC SP_{operacion}EXTENDEDPROPERTY @name=N'MS_Description', @value=N'{valor}',@level0type=N'SCHEMA', "
            f"@level0name=N'DUN', @level1type=N'PROCEDURE', @level1name=N'{proc}'{nivel2}\n")


def _proc(verbo, nombre, parametros=("@nOrigenId", "@cDoi")):
    lista = ",\n".join(f"\t{p} INT" for p in parametros)
    return f"{verbo} PROCEDURE DUN.{nombre}\n(\n{lista}\n)\n"


def _existente(sql, dic):
    return [h for h in verificar_diccionario(sql, dic) if h.regla == "DOCUMENTACION_EXISTENTE_EN_ALTER"]


class SeObservaTest(unittest.TestCase):
    def test_procedimiento_y_parametros(self):
        dic = (_exec("PA_Solicitud_Sel_Avance", valor="Procedimiento que obtiene la solicitud")
               + _exec("PA_Solicitud_Sel_Avance", "@nOrigenId") + _exec("PA_Solicitud_Sel_Avance", "@cDoi"))
        hallazgos = _existente(_proc("ALTER", "PA_Solicitud_Sel_Avance"), dic)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "bajo")
        self.assertEqual(hallazgos[0].lineas, [1, 2, 3])
        self.assertEqual(
            hallazgos[0].mensaje,
            "El diccionario agrega la descripción del procedimiento DUN.PA_Solicitud_Sel_Avance y de los "
            "parámetros @nOrigenId y @cDoi, que ya existen y podrían estar documentados. " + _ACCION,
        )

    def test_un_solo_parametro_en_singular(self):
        dic = _exec("PA_Solicitud_Sel_Avance", "@cDoi")
        hallazgos = _existente(_proc("ALTER", "PA_Solicitud_Sel_Avance"), dic)
        self.assertEqual(
            hallazgos[0].mensaje,
            "El diccionario agrega la descripción del parámetro @cDoi del procedimiento DUN.PA_Solicitud_Sel_Avance, "
            "que ya existe y podría estar documentado. Verificar si ya cuenta con descripción en el diccionario, ya "
            "que de ser así la ejecución del script fallará. En ese caso, retirar la sentencia o reemplazarla por "
            "una de actualización (sp_updateextendedproperty).",
        )

    def test_solo_la_descripcion_del_procedimiento(self):
        dic = _exec("PA_Solicitud_Sel_Avance", valor="Procedimiento que obtiene la solicitud")
        mensaje = _existente(_proc("ALTER", "PA_Solicitud_Sel_Avance"), dic)[0].mensaje
        self.assertTrue(mensaje.startswith(
            "El diccionario agrega la descripción del procedimiento DUN.PA_Solicitud_Sel_Avance, que ya existe y "
            "podría estar documentada. Verificar si ya cuenta con descripción"))

    def test_varios_procedimientos_en_un_solo_mensaje(self):
        sql = _proc("ALTER", "PA_Solicitud_Sel_Avance") + "\n" + _proc("ALTER", "PA_Solicitud_Sel_Detalle", ("@cPersCod",))
        dic = (_exec("PA_Solicitud_Sel_Avance", valor="Procedimiento que obtiene la solicitud")
               + _exec("PA_Solicitud_Sel_Avance", "@nOrigenId") + _exec("PA_Solicitud_Sel_Avance", "@cDoi")
               + _exec("PA_Solicitud_Sel_Detalle", "@cPersCod"))
        hallazgos = _existente(sql, dic)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(
            hallazgos[0].mensaje,
            "El diccionario agrega descripciones a 2 procedimientos que ya existen y podrían estar documentados: "
            "en DUN.PA_Solicitud_Sel_Avance, la descripción del procedimiento y de los parámetros @nOrigenId y "
            "@cDoi; en DUN.PA_Solicitud_Sel_Detalle, la descripción del parámetro @cPersCod. " + _ACCION,
        )


class NoSeObservaTest(unittest.TestCase):
    def test_create_y_create_or_alter(self):
        dic = _exec("PA_Solicitud_Sel_Avance", valor="Procedimiento que obtiene la solicitud") + _exec(
            "PA_Solicitud_Sel_Avance", "@nOrigenId") + _exec("PA_Solicitud_Sel_Avance", "@cDoi")
        for verbo in ("CREATE", "CREATE OR ALTER"):
            with self.subTest(verbo=verbo):
                self.assertEqual(_existente(_proc(verbo, "PA_Solicitud_Sel_Avance"), dic), [])

    def test_alter_con_sentencias_de_actualizacion(self):
        dic = (_exec("PA_Solicitud_Sel_Avance", operacion="UPDATE", valor="Procedimiento que obtiene la solicitud")
               + _exec("PA_Solicitud_Sel_Avance", "@nOrigenId", operacion="UPDATE"))
        self.assertEqual(_existente(_proc("ALTER", "PA_Solicitud_Sel_Avance"), dic), [])

    def test_solo_las_que_agregan(self):
        dic = (_exec("PA_Solicitud_Sel_Avance", "@nOrigenId", operacion="UPDATE")
               + _exec("PA_Solicitud_Sel_Avance", "@cDoi"))
        hallazgos = _existente(_proc("ALTER", "PA_Solicitud_Sel_Avance"), dic)
        self.assertIn("del parámetro @cDoi", hallazgos[0].mensaje)
        self.assertNotIn("@nOrigenId", hallazgos[0].mensaje)

    def test_varios_procedimientos_solo_el_alter(self):
        sql = _proc("CREATE", "PA_Solicitud_Sel_Nuevo") + "\n" + _proc("ALTER", "PA_Solicitud_Sel_Avance", ("@cDoi",))
        dic = (_exec("PA_Solicitud_Sel_Nuevo", valor="Procedimiento nuevo") + _exec("PA_Solicitud_Sel_Nuevo", "@cDoi")
               + _exec("PA_Solicitud_Sel_Avance", "@cDoi"))
        hallazgos = _existente(sql, dic)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("del parámetro @cDoi del procedimiento DUN.PA_Solicitud_Sel_Avance", hallazgos[0].mensaje)
        self.assertNotIn("PA_Solicitud_Sel_Nuevo", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
