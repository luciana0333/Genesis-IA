"""C1: «Generar diccionario faltante»."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.diccionario_generador import diccionario_faltante_procedimiento, diccionario_faltante_tabla

TABLA = (
    "CREATE TABLE CLICKTOPAY.Cliente (\n"
    " nClienteId INT NOT NULL,\n"
    " cNombre VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL,\n"
    " cApellido VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL\n"
    ")"
)
PROCEDIMIENTO = (
    "CREATE PROCEDURE CLICKTOPAY.PA_Cliente_Sel_PorId\n"
    "  @nClienteId INT,\n"
    "  @cCodigo VARCHAR(10)\n"
    "AS\nBEGIN\n  SELECT 1;\nEND;"
)
COLUMNA_NOMBRE = (
    "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Nombre del cliente', "
    "@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', @level1type=N'TABLE', @level1name=N'Cliente', "
    "@level2type=N'COLUMN', @level2name=N'cNombre';"
)


def _completar(script: str) -> str:
    """Simula al desarrollador: escribe una descripción distinta en cada sentencia."""
    partes = script.split("@value = N''")
    return "".join(
        parte + (f"@value = N'Descripción de prueba numero {i}'" if i < len(partes) - 1 else "")
        for i, parte in enumerate(partes)
    )


class TestGeneradorTablas(unittest.TestCase):
    def test_create_sin_diccionario_genera_tabla_y_columnas_en_orden(self):
        faltante = diccionario_faltante_tabla(TABLA, "")
        self.assertEqual(faltante["elementos"], ["tabla Cliente", "nClienteId", "cNombre", "cApellido"])
        script = faltante["script"]
        self.assertTrue(script.startswith("-- Diccionario faltante de la tabla CLICKTOPAY.Cliente"))
        self.assertEqual(script.count("EXEC sys.sp_addextendedproperty"), 4)
        self.assertIn("@level1type = N'TABLE', @level1name = N'Cliente';", script)
        self.assertIn("@level2type = N'COLUMN', @level2name = N'cApellido';", script)
        self.assertIn("@value = N'Registra la información de los clientes',  -- Sugerida: revisar y mejorar", script)
        self.assertIn("@value = N'Apellido del cliente',  -- Sugerida: revisar y mejorar", script)

    def test_solo_genera_lo_que_falta(self):
        tabla = (
            "EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Registra los clientes', "
            "@level0type=N'SCHEMA', @level0name=N'CLICKTOPAY', @level1type=N'TABLE', @level1name=N'Cliente';"
        )
        faltante = diccionario_faltante_tabla(TABLA, tabla + "\n" + COLUMNA_NOMBRE)
        self.assertEqual(faltante["elementos"], ["nClienteId", "cApellido"])

    def test_alter_solo_genera_las_columnas_agregadas(self):
        alter = (
            "ALTER TABLE CLICKTOPAY.Cliente ADD cTelefono VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NULL\nGO\n"
            "ALTER TABLE CLICKTOPAY.Cliente ALTER COLUMN cNombre VARCHAR(80) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL"
        )
        self.assertEqual(diccionario_faltante_tabla(alter, "")["elementos"], ["cTelefono"])

    def test_completo_no_genera_nada(self):
        completo = _completar(diccionario_faltante_tabla(TABLA, "")["script"])
        self.assertIsNone(diccionario_faltante_tabla(TABLA, completo))

    def test_el_script_completado_pasa_la_revision(self):
        completo = _completar(diccionario_faltante_tabla(TABLA, "")["script"])
        self.assertEqual(verificar_diccionario_tablas(TABLA, completo), [])

    def test_el_script_con_las_sugerencias_pasa_la_revision(self):
        self.assertEqual(verificar_diccionario_tablas(TABLA, diccionario_faltante_tabla(TABLA, "")["script"]), [])

    def test_columna_que_no_se_puede_deducir_queda_por_completar(self):
        tabla = "CREATE TABLE CLICKTOPAY.Cliente (\n nClienteId INT NOT NULL,\n cXyzQwe VARCHAR(5) NULL\n)"
        script = diccionario_faltante_tabla(tabla, "")["script"]
        self.assertIn("@value = N'',  -- Completar: dato que almacena la columna", script)
        reglas = {h.regla for h in verificar_diccionario_tablas(tabla, script)}
        self.assertEqual(reglas, {"DESCRIPCION_COLUMNA_VACIA"})


class TestGeneradorProcedimientos(unittest.TestCase):
    def test_create_sin_diccionario(self):
        faltante = diccionario_faltante_procedimiento(PROCEDIMIENTO, "")
        self.assertEqual(faltante["elementos"], ["procedimiento PA_Cliente_Sel_PorId", "@nClienteId", "@cCodigo"])
        self.assertIn("@level2type = N'PARAMETER', @level2name = N'@cCodigo';", faltante["script"])

    def test_el_script_completado_pasa_la_revision(self):
        completo = _completar(diccionario_faltante_procedimiento(PROCEDIMIENTO, "")["script"])
        self.assertEqual(verificar_diccionario(PROCEDIMIENTO, completo), [])

    def test_alter_procedure_no_genera(self):
        alter = PROCEDIMIENTO.replace("CREATE PROCEDURE", "ALTER PROCEDURE")
        self.assertIsNone(diccionario_faltante_procedimiento(alter, ""))


if __name__ == "__main__":
    unittest.main()
