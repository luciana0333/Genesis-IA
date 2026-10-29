"""Negocio: dependencia con la base de datos BI (no productiva)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal

QUE_HACER = (
    "Se recomienda evitar dependencias con la base de datos BI, ya que no se considera una base de datos "
    "productiva. Ante una eventual indisponibilidad de dicha base, los procedimientos que dependan de ella "
    "podrían verse afectados en su ejecución."
)


def _bi(cuerpo):
    sql = f"CREATE PROCEDURE Bonificacion.PA_RenovacionSaldo_Ins\n@dFecha DATE\nAS\nBEGIN\n{cuerpo}\nEND"
    return [h for h in verificar_procedimiento_normal(sql) if h.regla == "DEPENDENCIA_BASE_BI"]


class DependenciaBiTest(unittest.TestCase):
    def test_funcion_de_bi(self):
        hallazgo = _bi("DECLARE @Tc INT\nSELECT @Tc = tipo FROM bi.dbo.fn_fechas_eliminar(@dFecha, @dFecha, 2, 1)\n"
                       "SELECT @Tc")[0]
        self.assertEqual(hallazgo.severidad.value, "alto")
        self.assertEqual(hallazgo.lineas, [6])
        self.assertEqual(hallazgo.mensaje,
                         f"Se identificó una dependencia con la base de datos BI (bi.dbo.fn_fechas_eliminar). {QUE_HACER}")

    def test_otras_formas_en_una_sola_observacion(self):
        hallazgo = _bi("SELECT 1 FROM dbo.A a INNER JOIN [BI].[dbo].[Ventas] v ON v.n = a.n\n"
                       "EXEC BI.dbo.PA_Cargar_Ins_Datos\nSELECT x FROM Servidor.BI.dbo.Metas")[0]
        self.assertEqual(hallazgo.lineas, [5, 6, 7])
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificaron 3 dependencias con la base de datos BI: [BI].[dbo].[Ventas]; BI.dbo.PA_Cargar_Ins_Datos; "
            "Servidor.BI.dbo.Metas."))

    def test_no_se_confunde(self):
        for cuerpo in ("SELECT bi.cCodigo FROM dbo.Bonificacion bi", "SELECT x FROM DBCMACICA.dbo.Agencias",
                       "SELECT x FROM BIBLIOTECA.dbo.Libros", "-- SELECT x FROM BI.dbo.Ventas\nSELECT 1",
                       "SELECT 'BI.dbo.Ventas' AS c"):
            with self.subTest(cuerpo=cuerpo):
                self.assertEqual(_bi(cuerpo), [])


if __name__ == "__main__":
    unittest.main()
