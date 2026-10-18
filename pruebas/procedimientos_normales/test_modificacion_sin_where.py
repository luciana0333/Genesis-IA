"""UPDATE o DELETE sin WHERE sobre una tabla física (nivel medio)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal


def _procedimiento(cuerpo: str) -> str:
    return (
        "CREATE PROCEDURE dbo.PA_Cliente_Upd_Estado\n  @nClienteId INT\nAS\nBEGIN\n  SET NOCOUNT ON;\n"
        f"{cuerpo}\nEND"
    )


def _sin_where(cuerpo: str):
    return [h for h in verificar_procedimiento_normal(_procedimiento(cuerpo)) if h.regla == "MODIFICACION_SIN_WHERE"]


class TestModificacionSinWhere(unittest.TestCase):
    def test_update_sin_where(self):
        hallazgos = _sin_where("  UPDATE dbo.Cliente SET nEstado = 0")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "medio")
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó un UPDATE sobre la tabla dbo.Cliente sin condición WHERE, por lo que se modificarán "
            "todos sus registros. Se recomienda agregar la condición WHERE que limite los registros a actualizar, "
            "ya que sin ella el cambio afecta a toda la tabla.",
        )

    def test_delete_sin_where(self):
        for cuerpo in ("  DELETE FROM dbo.Cliente", "  DELETE dbo.Cliente", "  DELETE TOP (100) FROM dbo.Cliente"):
            with self.subTest(cuerpo=cuerpo):
                hallazgos = _sin_where(cuerpo)
                self.assertEqual(len(hallazgos), 1)
                self.assertIn("Se identificó un DELETE sobre la tabla dbo.Cliente sin condición WHERE, por lo que "
                              "se eliminarán todos sus registros", hallazgos[0].mensaje)

    def test_alias_se_resuelve_a_la_tabla(self):
        hallazgos = _sin_where("  UPDATE c SET c.nEstado = 0 FROM dbo.Cliente c")
        self.assertIn("UPDATE sobre la tabla dbo.Cliente sin condición WHERE", hallazgos[0].mensaje)

    def test_where_en_una_subconsulta_no_cuenta(self):
        cuerpo = "  UPDATE dbo.Cliente SET nSaldo = (SELECT SUM(m.nMonto) FROM dbo.Movimiento m WHERE m.nId = 1)"
        self.assertEqual(len(_sin_where(cuerpo)), 1)

    def test_select_siguiente_con_where_no_lo_oculta(self):
        cuerpo = "  UPDATE dbo.Cliente SET nEstado = 0\n  SELECT c.cNombre FROM dbo.Cliente c WHERE c.nClienteId = 1"
        self.assertEqual(len(_sin_where(cuerpo)), 1)

    def test_no_se_marcan(self):
        casos = (
            "  UPDATE dbo.Cliente SET nEstado = 0 WHERE nClienteId = @nClienteId",
            "  DELETE FROM dbo.Cliente WHERE nClienteId = @nClienteId",
            "  UPDATE #Pendientes SET nEstado = 0",
            "  DELETE FROM #Pendientes",
            "  DECLARE @T TABLE (nId INT)\n  DELETE FROM @T",
            "  UPDATE c SET c.nEstado = 0 FROM dbo.Cliente c INNER JOIN #Pendientes p ON p.nId = c.nClienteId",
            "  DELETE c FROM dbo.Cliente c INNER JOIN #Pendientes p ON p.nId = c.nClienteId",
            "  UPDATE t SET t.nEstado = 0 FROM #Pendientes t",
            "  ;WITH cte AS (SELECT c.nEstado FROM dbo.Cliente c WHERE c.nClienteId = 1)\n  UPDATE cte SET nEstado = 0",
            "  UPDATE STATISTICS dbo.Cliente",
            "  MERGE dbo.Cliente AS d USING #T AS o ON d.nId = o.nId\n  WHEN MATCHED THEN UPDATE SET d.nEstado = 1\n"
            "  WHEN NOT MATCHED BY SOURCE THEN DELETE;",
        )
        for cuerpo in casos:
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(_sin_where(cuerpo), [])


if __name__ == "__main__":
    unittest.main()
