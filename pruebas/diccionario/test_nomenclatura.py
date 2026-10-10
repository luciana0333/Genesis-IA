import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

CUERPO = "\n    @nClienteId INT\nAS\nBEGIN\n    SELECT 1\nEND;"
REGLAS_NOMBRE_PROC = {
    "PROCEDIMIENTO_SIN_PREFIJO_PA",
    "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
    "PROCEDIMIENTO_ACCION_SIN_SEPARAR",
    "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
    "PROCEDIMIENTO_SIN_ACCION",
}


def reglas_nombre_proc(verbo, nombre):
    return [h.regla for h in verificar_diccionario(f"{verbo} PROCEDURE {nombre}{CUERPO}", "")
            if h.regla in REGLAS_NOMBRE_PROC]


def reglas_nombre_tabla(verbo, nombre):
    sql = f"{verbo} TABLE {nombre} (nId INT NOT NULL);" if verbo == "CREATE" else f"ALTER TABLE {nombre} ADD cX VARCHAR(5) NULL;"
    return [h.regla for h in verificar_diccionario_tablas(sql, "") if h.regla == "TABLA_NOMBRE_NO_ESTANDAR"]


class TestNomenclaturaProcedimiento(unittest.TestCase):
    def test_create_revisa_la_sintaxis_del_manual(self):
        casos = {
            "dbo.PA_Cliente": "PROCEDIMIENTO_NOMBRE_INCOMPLETO",
            "dbo.Cliente_Consultar": "PROCEDIMIENTO_SIN_PREFIJO_PA",
            "dbo.PA_Cliente_Consultar": "PROCEDIMIENTO_ACCION_NO_ABREVIADA",
            "dbo.PA_Cliente_SelDatos": "PROCEDIMIENTO_ACCION_SIN_SEPARAR",
            "dbo.PA_Cliente_Datos": "PROCEDIMIENTO_SIN_ACCION",
        }
        for nombre, regla in casos.items():
            with self.subTest(nombre=nombre):
                self.assertEqual(reglas_nombre_proc("CREATE", nombre), [regla])

    def test_nombres_correctos_y_sin_exigir_pascalcase(self):
        for nombre in ("dbo.PA_Cliente_Sel_PorDocumento", "dbo.pa_cliente_sel_pordocumento",
                       "dbo.PA_Cliente_Procesar_Pagos"):
            with self.subTest(nombre=nombre):
                self.assertEqual(reglas_nombre_proc("CREATE", nombre), [])

    def test_alter_solo_revisa_el_esquema(self):
        self.assertEqual(reglas_nombre_proc("ALTER", "dbo.PA_Cliente"), [])
        reglas = [h.regla for h in verificar_diccionario(f"ALTER PROCEDURE PA_Cliente{CUERPO}", "")]
        self.assertIn("OBJETO_SIN_ESQUEMA", reglas)


class TestNomenclaturaTabla(unittest.TestCase):
    def test_create_revisa_el_nombre(self):
        for nombre in ("dbo.TB_Cliente", "dbo.Cliente_Datos", "dbo.cliente"):
            with self.subTest(nombre=nombre):
                self.assertEqual(reglas_nombre_tabla("CREATE", nombre), ["TABLA_NOMBRE_NO_ESTANDAR"])
        for nombre in ("dbo.Cliente", "dbo.ClienteDatos"):
            with self.subTest(nombre=nombre):
                self.assertEqual(reglas_nombre_tabla("CREATE", nombre), [])

    def test_sugiere_el_nombre_corregido(self):
        hallazgo = next(h for h in verificar_diccionario_tablas("CREATE TABLE dbo.TB_Cliente (nId INT NOT NULL);", "")
                        if h.regla == "TABLA_NOMBRE_NO_ESTANDAR")
        self.assertIn("(ej.: Cliente)", hallazgo.mensaje)

    def test_alter_no_revisa_el_nombre(self):
        self.assertEqual(reglas_nombre_tabla("ALTER", "dbo.TB_Cliente"), [])


if __name__ == "__main__":
    unittest.main()
