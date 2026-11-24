"""«Copiar consulta de validación» en Diccionarios (usuaria, 23 nov.).

Las observaciones que piden verificar qué descripciones ya están registradas traen la consulta para comprobarlo. La
consulta se probó en SQL Server (tempdb): esquema + nombre, lo que falta sale «(sin descripción)», la fila de una
función escalar no se cruza con el valor de retorno (class = 2) y un nombre con comilla no rompe la consulta.
"""
import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.consulta_diccionario import consulta_descripciones

FIRMA_ALTER = ("ALTER PROCEDURE DBO.PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral(\n\t@dFechaInicio DATETIME,\n"
               "\t@dFechaFin DATETIME\n\t)")
DICCIONARIO = ("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Procedimiento que obtiene las actas.',\n"
               "@level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'PROCEDURE',"
               "@level1name=N'PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral'")


def _con_consulta(hallazgos):
    return {h.regla: h.consulta for h in hallazgos if getattr(h, "consulta", None)}


class Consulta(unittest.TestCase):
    def test_procedimiento_por_esquema_y_nombre(self):
        consulta = consulta_descripciones("procedimiento", [("DBO", "PA_X")])
        self.assertIn("o.type IN ('P', 'PC')", consulta)
        self.assertEqual(consulta.count("(s.name = N'DBO' AND o.name = N'PA_X')"), 2)
        self.assertIn("ep.class = 2", consulta)  # parámetros: nunca el valor de retorno
        self.assertIn("pr.parameter_id > 0", consulta)
        self.assertIn("N'(sin descripción)'", consulta)
        self.assertIn("N'Descripción del procedimiento'", consulta)

    def test_funcion_y_tabla(self):
        funcion = consulta_descripciones("funcion", [("dbo", "FN_X")])
        self.assertIn("('FN', 'IF', 'TF', 'FS', 'FT')", funcion)
        self.assertIn("N'Descripción de la función'", funcion)
        tabla = consulta_descripciones("tabla", [("dbo", "T_X")])
        self.assertIn("sys.columns", tabla)
        self.assertIn("d.Elemento AS Columna", tabla)

    def test_sin_esquema_varios_y_comillas(self):
        self.assertIn("o.name = N'PA_X'", consulta_descripciones("procedimiento", [(None, "PA_X")]))
        varios = consulta_descripciones("procedimiento", [("dbo", "PA_A"), ("dun", "PA_B"), ("dbo", "PA_A")])
        self.assertEqual(varios.count("o.name = N'PA_A'"), 2)  # sin repetir el mismo objeto
        self.assertIn("OR (s.name = N'dun' AND o.name = N'PA_B')", varios)
        self.assertIn("N'O''Brien'", consulta_descripciones("tabla", [("dbo", "O'Brien")]))
        self.assertIsNone(consulta_descripciones("procedimiento", []))


class EnLasObservaciones(unittest.TestCase):
    def test_alter_de_procedimiento_trae_la_consulta(self):
        consultas = _con_consulta(verificar_diccionario(FIRMA_ALTER, DICCIONARIO))
        self.assertTrue(consultas)
        for consulta in consultas.values():
            self.assertIn("o.name = N'PA_GDD_CredFallidoComiteDetalle_Sel_FallidosGeneral'", consulta)

    def test_alter_sin_diccionario_de_funcion(self):
        consultas = _con_consulta(verificar_diccionario("ALTER FUNCTION dbo.FN_X (@p INT) RETURNS INT", "", "funcion"))
        self.assertIn("ALTER_SIN_DICCIONARIO", consultas)
        self.assertIn("N'Descripción de la función'", consultas["ALTER_SIN_DICCIONARIO"])

    def test_create_no_trae_consulta(self):
        firma = FIRMA_ALTER.replace("ALTER PROCEDURE", "CREATE PROCEDURE")
        self.assertEqual(_con_consulta(verificar_diccionario(firma, DICCIONARIO)), {})

    def test_alter_table_trae_la_consulta_de_esa_tabla(self):
        hallazgos = verificar_diccionario_tablas("ALTER TABLE dbo.Cliente ALTER COLUMN cNombre VARCHAR(200)", "")
        consultas = _con_consulta(hallazgos)
        self.assertTrue(consultas, [h.regla for h in hallazgos])
        for consulta in consultas.values():
            self.assertIn("(s.name = N'dbo' AND o.name = N'Cliente')", consulta)

    def test_tabla_creada_en_el_mismo_script_no_trae_consulta(self):
        script = ("CREATE TABLE dbo.Cliente (nId INT)\nALTER TABLE dbo.Cliente ADD CONSTRAINT PK_Cliente "
                  "PRIMARY KEY (nId)")
        self.assertEqual(_con_consulta(verificar_diccionario_tablas(script, "")), {})


def _varios_pa(nombres, documentar=None):
    procs, dic = [], []
    for nombre in nombres:
        params = [f"@{nombre[-1]}{j}" for j in range(3)]
        procs.append(f"ALTER PROCEDURE dbo.{nombre}\n(\n" + ",\n".join(f"\t{p} INT" for p in params) + "\n)\nAS\nSELECT 1\nGO")
        dic.append("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Procedimiento que registra datos.', "
                   f"@level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'PROCEDURE',@level1name=N'{nombre}'")
        for p in params:
            dic.append("EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Indica el valor del dato.', "
                       f"@level0type=N'SCHEMA',@level0name=N'dbo', @level1type=N'PROCEDURE',@level1name=N'{nombre}', "
                       f"@level2type=N'PARAMETER',@level2name=N'{p}'")
    return "\n".join(procs), "\n".join(dic)


class DocumentacionExistenteEnTabla(unittest.TestCase):
    """Usuaria (23 nov.): con 5 PA que solo agregan descripciones salía en viñetas, sin nombrar los parámetros."""

    def test_desde_dos_procedimientos_va_en_tabla(self):
        hallazgo = next(h for h in verificar_diccionario(*_varios_pa(["PA_NET_A", "PA_NET_B"]))
                        if h.regla == "DOCUMENTACION_EXISTENTE_EN_ALTER")
        self.assertEqual([g["nombre"] for g in hallazgo.grupos], ["dbo.PA_NET_A", "dbo.PA_NET_B"])
        self.assertEqual(hallazgo.grupos[0]["etiquetas"], ["(descripción del procedimiento)", "@A0", "@A1", "@A2"])
        self.assertEqual(hallazgo.grupos[0]["situacion"], "Se agregan en el diccionario")
        self.assertEqual(hallazgo.lineas, [linea for g in hallazgo.grupos for linea in g["lineas"]])
        self.assertTrue(hallazgo.consulta)

    def test_un_solo_procedimiento_sigue_en_texto(self):
        hallazgo = next(h for h in verificar_diccionario(*_varios_pa(["PA_NET_A"]))
                        if h.regla == "DOCUMENTACION_EXISTENTE_EN_ALTER")
        self.assertFalse(getattr(hallazgo, "grupos", None))


if __name__ == "__main__":
    unittest.main()
