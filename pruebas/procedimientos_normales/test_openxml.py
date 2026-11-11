"""«Uso de OPENXML en lugar de métodos nativos» (solo Negocio; título y texto de la usuaria, 11 nov.)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import verificar_procedimiento_normal
from app.analizadores.analizador_reportes import verificar_reporte

REGLA = "OPENXML_EN_LUGAR_DE_METODOS_NATIVOS"

# Caso de la usuaria (líneas 129-131 de su PA), con su @XLMDetalleGastos tal cual.
_SU_CASO = (
    "CREATE PROCEDURE dbo.PA_Movimiento_Ins_Detalle @XMLDetalleMovimiento XML, @XMLDetalleComisiones XML, "
    "@XLMDetalleGastos XML AS\nBEGIN\n"
    "    DECLARE @nIdXmlDetalleMov INT, @nIdXmlDetalleComisiones INT, @nIdXmlDetalleGastos INT;\n"
    "    EXEC sp_xml_preparedocument @nIdXmlDetalleMov OUTPUT, @XMLDetalleMovimiento\n"            # 4
    "    EXEC sp_xml_preparedocument @nIdXmlDetalleComisiones OUTPUT, @XMLDetalleComisiones\n"     # 5
    "    EXEC sp_xml_preparedocument @nIdXmlDetalleGastos OUTPUT, @XLMDetalleGastos\n"             # 6
    "    SELECT nMovNro FROM OPENXML(@nIdXmlDetalleMov, '/Movs/Mov', 2) WITH (nMovNro INT);\n"
    "    EXEC sp_xml_removedocument @nIdXmlDetalleMov;\n"
    "END"
)


def _hallazgos(sql, verificar=verificar_procedimiento_normal):
    return [h for h in verificar(sql) if h.regla == REGLA]


class OpenXmlTest(unittest.TestCase):
    def test_caso_de_la_usuaria_una_observacion_con_las_tres_variables(self):
        hallazgos = _hallazgos(_SU_CASO)
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "alto")
        self.assertEqual(hallazgos[0].linea, 4)
        self.assertEqual(hallazgos[0].lineas, [4, 5, 6])
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó el uso de sp_xml_preparedocument para procesar los XML correspondientes a "
            "@nIdXmlDetalleMov, @nIdXmlDetalleComisiones y @nIdXmlDetalleGastos. Se recomienda utilizar los métodos "
            "nativos .nodes() y .value() para leer y extraer los datos del XML, evitando el uso de "
            "sp_xml_preparedocument, ya que reserva memoria del servidor y requiere liberarla posteriormente.",
        )

    def test_una_sola_variable_en_singular(self):
        sql = ("CREATE PROCEDURE dbo.PA_X @Xml XML AS\nBEGIN\n DECLARE @hDoc INT;\n"
               " EXEC sp_xml_preparedocument @hDoc OUTPUT, @Xml;\nEND")
        self.assertTrue(_hallazgos(sql)[0].mensaje.startswith(
            "Se identificó el uso de sp_xml_preparedocument para procesar el XML correspondiente a @hDoc. "))

    def test_formas_de_escribirlo(self):
        for llamada in ("EXECUTE sp_xml_preparedocument @h OUTPUT, @Xml",
                        "EXEC sys.sp_xml_preparedocument @h OUTPUT, @Xml",
                        "EXEC [sys].[sp_xml_preparedocument] @h OUTPUT, @Xml",
                        "exec SP_XML_PREPAREDOCUMENT @hdoc = @h OUTPUT, @xmltext = @Xml"):
            with self.subTest(llamada=llamada):
                sql = f"CREATE PROCEDURE dbo.PA_X @Xml XML AS\nBEGIN\n DECLARE @h INT;\n {llamada};\nEND"
                self.assertIn("correspondiente a @h.", _hallazgos(sql)[0].mensaje)

    def test_misma_variable_dos_veces_se_nombra_una_vez(self):
        sql = ("CREATE PROCEDURE dbo.PA_X @Xml XML AS\nBEGIN\n DECLARE @h INT;\n"
               " EXEC sp_xml_preparedocument @h OUTPUT, @Xml;\n EXEC sp_xml_removedocument @h;\n"
               " EXEC sp_xml_preparedocument @h OUTPUT, @Xml;\nEND")
        hallazgo = _hallazgos(sql)[0]
        self.assertEqual(hallazgo.mensaje.count("@h"), 1)
        self.assertEqual(hallazgo.lineas, [4, 6])

    def test_lo_que_no_se_marca(self):
        for sql in (
            # Forma moderna.
            "CREATE PROCEDURE dbo.PA_X @Xml XML AS\nBEGIN\n SELECT M.x.value('(n)[1]', 'INT') "
            "FROM @Xml.nodes('/Movs/Mov') AS M(x);\nEND",
            # Comentado o dentro de un texto.
            "CREATE PROCEDURE dbo.PA_X @Xml XML AS\nBEGIN\n -- EXEC sp_xml_preparedocument @h OUTPUT, @Xml\n"
            " /* EXEC sp_xml_preparedocument @h OUTPUT, @Xml */\n"
            " PRINT 'EXEC sp_xml_preparedocument @h OUTPUT, @Xml';\nEND",
            # Solo liberar no es preparar.
            "CREATE PROCEDURE dbo.PA_X AS\nBEGIN\n DECLARE @h INT = 1;\n EXEC sp_xml_removedocument @h;\nEND",
        ):
            with self.subTest(sql=sql):
                self.assertEqual(_hallazgos(sql), [])

    def test_solo_en_negocio(self):
        self.assertEqual(_hallazgos(_SU_CASO, verificar_reporte), [])


if __name__ == "__main__":
    unittest.main()
