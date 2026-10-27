import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario

PROCEDIMIENTO = """CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId
    @nClienteId INT,
    @cCodigo VARCHAR(10)
AS
BEGIN
    SELECT 1
END"""


def sentencia(descripcion, parametro=None):
    nivel2 = f", @level2type=N'PARAMETER', @level2name=N'{parametro}'" if parametro else ""
    return (
        f"EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'{descripcion}', "
        f"@level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'PROCEDURE', "
        f"@level1name=N'PA_Cliente_Sel_PorId'{nivel2}\nGO"
    )


def duplicados(diccionario):
    return [h for h in verificar_diccionario(PROCEDIMIENTO, diccionario) if h.regla == "DOCUMENTACION_DUPLICADA"]


class TestDocumentacionDuplicadaProcedimiento(unittest.TestCase):
    def test_parametro_documentado_dos_veces(self):
        diccionario = "\n".join([
            sentencia("Consulta el cliente por su identificador"),
            sentencia("Identificador del cliente", "@nClienteId"),
            sentencia("Código del cliente", "@cCodigo"),
            sentencia("Identificador del cliente", "@nClienteId"),
        ])
        hallazgos = duplicados(diccionario)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("Se identificó que el parámetro @nClienteId se encuentra documentado dos veces, siendo la primera declaración en la línea 3",
                      hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].linea, 7)

    def test_procedimiento_y_parametro_repetidos_se_agrupan(self):
        diccionario = "\n".join([
            sentencia("Consulta el cliente por su identificador"),
            sentencia("Identificador del cliente", "@nClienteId"),
            sentencia("Código del cliente", "@cCodigo"),
            sentencia("Consulta el cliente por su identificador"),
            sentencia("Identificador del cliente", "@nClienteId"),
        ])
        hallazgos = duplicados(diccionario)
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("Se identificaron 2 declaraciones duplicadas", hallazgos[0].mensaje)
        self.assertIn("PA_Cliente_Sel_PorId (primera declaración en la línea 1)", hallazgos[0].mensaje)
        self.assertIn("@nClienteId (primera declaración en la línea 3)", hallazgos[0].mensaje)

    def test_sin_repetidos_no_reporta(self):
        diccionario = "\n".join([
            sentencia("Consulta el cliente por su identificador"),
            sentencia("Identificador del cliente", "@nClienteId"),
            sentencia("Código del cliente", "@cCodigo"),
        ])
        self.assertEqual(duplicados(diccionario), [])

    def test_update_no_cuenta_como_repetido(self):
        actualizar = sentencia("Identificador único del cliente", "@nClienteId").replace(
            "sp_addextendedproperty", "sp_updateextendedproperty")
        diccionario = "\n".join([
            sentencia("Consulta el cliente por su identificador"),
            sentencia("Identificador del cliente", "@nClienteId"),
            actualizar,
        ])
        self.assertEqual(duplicados(diccionario), [])


if __name__ == "__main__":
    unittest.main()
