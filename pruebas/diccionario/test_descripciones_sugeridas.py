"""Descripciones sugeridas para «Generar diccionario faltante»."""

import unittest
from unittest import mock

from app.analizadores import descripciones_sugeridas as sugeridas

COLUMNAS_CLIENTE = {
    "nClienteId": "Identificador único del cliente",
    "cNombre": "Nombre del cliente",
    "cApellidoPaterno": "Apellido paterno",
    "dFechaNacimiento": "Fecha de nacimiento",
    "dVencimiento": "Fecha de vencimiento",
    "nAgenciaId": "Identificador de la agencia asociada",
    "nTipoDocumentoId": "Identificador del tipo de documento asociado",
    "cNumeroDocumento": "Número de documento",
    "cNroRUC": "Número de RUC",
    "cCorreoElectronico": "Correo electrónico",
    "cTelefono": "Teléfono del cliente",
    "cDireccion": "Dirección del cliente",
    "bActivo": "Indica si el registro está activo",
    "bTieneGarantia": "Indica si tiene garantía",
    "nMontoDesembolso": "Monto del desembolso",
    "nTasaInteres": "Tasa de interés",
    "cCodSucursal": "Código de la sucursal",
    "cUsuReg": "Usuario que realizó el registro",
    "dFecReg": "Fecha y hora en que se realizó el registro",
    "cUsuMod": "Usuario que realizó la última modificación",
    "dFecMod": "Fecha y hora de la última modificación",
}


class TestSugerenciasColumnas(unittest.TestCase):
    def test_columnas_tipicas(self):
        for columna, esperada in COLUMNAS_CLIENTE.items():
            with self.subTest(columna=columna):
                self.assertEqual(sugeridas.sugerir_columna(columna, "Cliente"), esperada)

    def test_tabla_en_plural_y_compuesta(self):
        self.assertEqual(sugeridas.sugerir_columna("nAgenciaId", "Agencias"), "Identificador único de la agencia")
        self.assertEqual(
            sugeridas.sugerir_columna("nSolicitudArchivoId", "SolicitudArchivos"),
            "Identificador único de la solicitud de archivos",
        )

    def test_parametro_no_dice_unico(self):
        self.assertEqual(sugeridas.sugerir_columna("@nClienteId", "Cliente", es_parametro=True), "Identificador del cliente")

    def test_no_inventa_con_palabras_desconocidas(self):
        self.assertIsNone(sugeridas.sugerir_columna("cXyzQwe", "Cliente"))


class TestSugerenciasTablaYProcedimiento(unittest.TestCase):
    def test_tablas(self):
        self.assertEqual(sugeridas.sugerir_tabla("Cliente"), "Registra la información de los clientes")
        self.assertEqual(sugeridas.sugerir_tabla("Agencias"), "Registra la información de las agencias")
        self.assertEqual(
            sugeridas.sugerir_tabla("SolicitudArchivos"), "Registra la información de las solicitudes de archivos"
        )

    def test_procedimientos(self):
        casos = {
            "PA_Cliente_Sel_PorId": "Consulta los datos del cliente por su identificador",
            "PA_Cliente_Sel_PorNumeroDocumento": "Consulta los datos del cliente por número de documento",
            "PA_Agencia_Ins": "Registra una nueva agencia",
            "PA_Cliente_Upd": "Actualiza los datos del cliente",
            "PA_Cuota_Del": "Elimina la cuota",
            "PA_Credito_Lis": "Lista los créditos",
            "PA_SolicitudArchivos_Sel_Pendientes": "Consulta las solicitudes de archivos pendientes",
        }
        for procedimiento, esperada in casos.items():
            with self.subTest(procedimiento=procedimiento):
                self.assertEqual(sugeridas.sugerir_procedimiento(procedimiento), esperada)

    def test_nombre_fuera_del_estandar_no_sugiere(self):
        self.assertIsNone(sugeridas.sugerir_procedimiento("usp_ObtenerCliente"))


class TestSinSpacy(unittest.TestCase):
    """En una PC sin spaCy se usan las reglas del español: las sugerencias siguen saliendo."""

    def test_funciona_sin_spacy(self):
        with mock.patch.object(sugeridas, "_spacy", return_value=None):
            self.assertEqual(sugeridas.sugerir_columna("nAgenciaId", "Cliente"), "Identificador de la agencia asociada")
            self.assertEqual(sugeridas.sugerir_tabla("Clientes"), "Registra la información de los clientes")
            self.assertEqual(sugeridas.sugerir_columna("cCodSucursal", "Cliente"), "Código de la sucursal")


if __name__ == "__main__":
    unittest.main()
