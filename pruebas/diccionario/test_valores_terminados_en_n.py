"""Diccionario de procedimientos: un valor que termina en N mayúscula (esquema DUN) se lee completo.

Caso de la usuaria (1 nov.): @level0name=N'DUN' se leía como 'DU' y salía «Esquema no coincide» en todas
las sentencias. La limpieza quitaba todo «N'» del valor, también el final de 'DUN' + la comilla.
"""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import _limpiar_valor, verificar_diccionario


def _exec(proc, esquema="N'DUN'", parametro=None, valor="N'Descripción del dato'"):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (f"EXEC SP_ADDEXTENDEDPROPERTY @name=N'MS_Description', @value={valor},@level0type=N'SCHEMA', "
            f"@level0name={esquema}, @level1type=N'PROCEDURE', @level1name=N'{proc}'{nivel2}\n")


class LimpiarValorTest(unittest.TestCase):
    def test_solo_quita_el_prefijo_y_las_comillas_de_los_extremos(self):
        casos = {
            "N'DUN'": "DUN", "'DUN'": "DUN", "DUN": "DUN", "n'RRHH'": "RRHH", " N'dbo' ": "dbo",
            "N'IDENTIFICACION'": "IDENTIFICACION", "N'@cDNIN'": "@cDNIN", "N''": "", "''": "",
            "N'O''Brien'": "O'Brien",
        }
        for crudo, esperado in casos.items():
            with self.subTest(crudo=crudo):
                self.assertEqual(_limpiar_valor(crudo), esperado)


class EsquemaTerminadoEnNTest(unittest.TestCase):
    def test_caso_de_la_usuaria_esquema_dun(self):
        proc = "PA_Solicitud_Sel_Avance"
        sql = f"ALTER PROCEDURE DUN.{proc}\n(\n\t@nOrigenId INT,\n\t@cDoi VARCHAR(30)\n)\n"
        dic = (_exec(proc, valor="N'Procedimiento encargado de obtener datos de la solicitud'")
               + _exec(proc, parametro="@nOrigenId") + _exec(proc, parametro="@cDoi"))
        for esquema in ("N'DUN'", "'DUN'", "DUN"):
            with self.subTest(esquema=esquema):
                reglas = {h.regla for h in verificar_diccionario(sql, dic.replace("N'DUN'", esquema))}
                self.assertNotIn("ESQUEMA_NO_COINCIDE", reglas)

    def test_esquema_distinto_se_sigue_observando_con_su_nombre_completo(self):
        proc = "PA_Solicitud_Sel_Avance"
        sql = f"ALTER PROCEDURE DUN.{proc}\n(\n\t@nOrigenId INT\n)\n"
        dic = _exec(proc, esquema="N'DUNA'", valor="N'Procedimiento que obtiene la solicitud'")
        hallazgos = [h for h in verificar_diccionario(sql, dic) if h.regla == "ESQUEMA_NO_COINCIDE"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("el esquema 'DUNA', pero el procedimiento está en 'DUN'", hallazgos[0].mensaje)

    def test_parametro_que_termina_en_n_se_reconoce_documentado(self):
        proc = "PA_Persona_Sel_Datos"
        sql = f"CREATE PROCEDURE DUN.{proc}\n(\n\t@cDNIN VARCHAR(8)\n)\n"
        dic = (_exec(proc, valor="N'Procedimiento que consulta los datos de la persona'")
               + _exec(proc, parametro="@cDNIN", valor="N'Número del documento de identidad'"))
        self.assertNotIn("PARAMETRO_FALTANTE", {h.regla for h in verificar_diccionario(sql, dic)})


if __name__ == "__main__":
    unittest.main()
