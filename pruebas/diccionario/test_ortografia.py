import unittest

from app.analizadores import ortografia
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas


DESCRIPCIONES_CORRECTAS = [
    "Identificador unico del archivo de la solicitud",
    "Identificador único del estado",
    "Ruta de almacenamiento del archivo",
    "Fecha de registro del archivo; se asigna al insertar",
    "Indica si el registro se encuentra activo (1=Activo, 0=Inactivo)",
    "Correo electronico de contacto del cliente",
    "Tabla que almacena la informacion del cliente",
    "Archivos adjuntos registrados para cada solicitud",
    "Monto del desembolso del credito en soles",
    "Numero de cuotas pendientes del prestamo",
    "Usuario que registra la operacion",
    "Fecha y hora de la ultima actualizacion",
    "Observaciones ingresadas por el analista",
    "Codigo del producto crediticio",
    "Estados que puede tener una solicitud",
    "Clientes que tienen deuda vencida",
    "Campo que sirve para auditar cambios",
    "Motivo por el cual se rechaza la solicitud",
    "Se usa en @level2name y TB_Estado.nEstadoId",
]


@unittest.skipUnless(ortografia.disponible(), "pyspellchecker no está instalado")
class TestOrtografia(unittest.TestCase):
    def test_descripciones_correctas_no_generan_avisos(self):
        for texto in DESCRIPCIONES_CORRECTAS:
            with self.subTest(texto=texto):
                self.assertEqual(ortografia.palabras_mal_escritas(texto), [])

    def test_detecta_palabras_mal_escritas_con_sugerencia(self):
        errores = dict(ortografia.palabras_mal_escritas("Fehca de regsitro del arhcivo del clienet"))
        self.assertEqual(errores["Fehca"], ["Fecha"])
        self.assertEqual(errores["regsitro"], ["registro"])
        self.assertEqual(errores["arhcivo"], ["archivo"])
        self.assertEqual(errores["clienet"], ["cliente"])
        self.assertEqual(ortografia.palabras_mal_escritas("Permite regsitrar el pago"), [("regsitrar", ["registrar"])])

    def test_no_exige_tildes(self):
        self.assertEqual(ortografia.palabras_mal_escritas("Descripcion del codigo unico"), [])

    def test_ignora_nombres_de_objetos_siglas_y_vocabulario(self):
        texto = "Valor de nEstadoId para el RUC del cliente enviado por email desde TB_Estado"
        self.assertEqual(ortografia.palabras_mal_escritas(texto, ["TB_Estado"]), [])

    def test_ejemplo_del_equipo_en_el_diccionario_de_tablas(self):
        tabla = "CREATE TABLE dbo.TB_Estado (nEstadoId INT NOT NULL);"
        diccionario = (
            "EXEC sys.sp_addextendedproperty @name = N'MS_Description', "
            "@value = N'Estados que puede tener una solicitud', "
            "@level0type = N'SCHEMA', @level0name = dbo, @level1type = N'TABLE', @level1name = TB_Estado;\n"
            "-- nEstadoId\n"
            "EXEC sys.sp_addextendedproperty \n@name = N'MS_Description',\n"
            "@value = N'Identificadodr único del estado',\n"
            "@level0type = N'SCHEMA', @level0name = dbo,\n"
            "@level1type = N'TABLE',  @level1name = TB_Estado,\n"
            "@level2type = N'COLUMN', @level2name = nEstadoId;"
        )
        hallazgos = verificar_diccionario_tablas(tabla, diccionario)
        self.assertEqual([h.regla for h in hallazgos], ["ERROR_ORTOGRAFICO"])
        self.assertEqual(hallazgos[0].linea, 3)
        self.assertIn("columna nEstadoId", hallazgos[0].mensaje)
        self.assertIn("'Identificadodr'", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
