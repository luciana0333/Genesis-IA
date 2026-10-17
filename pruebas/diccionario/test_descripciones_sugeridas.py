"""Descripciones sugeridas para «Generar diccionario faltante»."""

import unittest
from unittest import mock

from app.analizadores import descripciones_sugeridas as sugeridas
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas
from app.analizadores.diccionario_generador import (
    definiciones_columnas,
    diccionario_faltante_procedimiento,
    diccionario_faltante_tabla,
)

COLUMNAS_CLIENTE = {
    "nClienteId": "Identificador único del cliente",
    "cNombre": "Nombre del cliente",
    "cApellidoPaterno": "Apellido paterno",
    "dFechaNacimiento": "Fecha de nacimiento",
    "dVencimiento": "Fecha de vencimiento",
    "nAgenciaId": "Identificador de la agencia asociada al cliente",
    "nTipoDocumentoId": "Identificador del tipo de documento asociado al cliente",
    "cNumeroDocumento": "Número de documento",
    "cNroRUC": "Número de RUC",
    "cCorreoElectronico": "Correo electrónico",
    "cTelefono": "Teléfono del cliente",
    "cDireccion": "Dirección del cliente",
    "bActivo": "Indica si el cliente está activo (1: sí, 0: no)",
    "bTieneGarantia": "Indica si tiene garantía (1: sí, 0: no)",
    "nMontoDesembolso": "Monto del desembolso",
    "nTasaInteres": "Tasa de interés",
    "cCodSucursal": "Código de la sucursal",
    "cUsuReg": "Usuario que registró el cliente",
    "dFecReg": "Fecha y hora en que se registró el cliente",
    "cUsuMod": "Usuario que realizó la última modificación del cliente",
    "dFecMod": "Fecha y hora de la última modificación del cliente",
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


TABLA_COMPLETA = """CREATE TABLE CLICKTOPAY.Cliente (
    nClienteId INT IDENTITY(1,1) NOT NULL,
    nAgenciaId INT NOT NULL,
    nTipoDocumentoId INT NOT NULL REFERENCES CLICKTOPAY.TipoDocumento(nTipoDocumentoId),
    nEstado TINYINT NOT NULL DEFAULT ((1)),
    bActivo BIT NOT NULL CONSTRAINT DF_Cliente_bActivo DEFAULT (1),
    dFecReg DATETIME NOT NULL DEFAULT (GETDATE()),
    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId),
    CONSTRAINT FK_Cliente_Agencia FOREIGN KEY (nAgenciaId) REFERENCES [CLICKTOPAY].[Agencia] (nAgenciaId)
)"""


class TestContextoDelCreate(unittest.TestCase):
    """Lo que el CREATE dice de la columna se agrega a la descripción."""

    def test_lee_pk_identity_referencias_y_default(self):
        info = definiciones_columnas(TABLA_COMPLETA)
        self.assertEqual(info["NCLIENTEID"], {"identity": True, "pk": True})
        self.assertEqual(info["NAGENCIAID"], {"referencia": "Agencia"})
        self.assertEqual(info["NTIPODOCUMENTOID"], {"referencia": "TipoDocumento"})
        self.assertEqual(info["NESTADO"], {"default": "1"})
        self.assertEqual(info["BACTIVO"], {"default": "1"})
        self.assertEqual(info["DFECREG"], {"default": "GETDATE()"})

    def test_default_en_un_alter_aparte(self):
        alter = "ALTER TABLE dbo.Cliente ADD CONSTRAINT DF_Cliente_nEstado DEFAULT ((2)) FOR nEstado"
        self.assertEqual(definiciones_columnas(alter)["NESTADO"], {"default": "2"})

    def test_descripciones_con_contexto(self):
        valores = [
            linea.split("@value = N'")[1].split("',")[0]
            for linea in diccionario_faltante_tabla(TABLA_COMPLETA, "")["script"].splitlines() if "@value" in linea
        ]
        self.assertEqual(valores, [
            "Registra la información de los clientes",
            "Identificador único del cliente. Clave primaria, se genera automáticamente",
            "Identificador de la agencia asociada al cliente. Referencia a la tabla Agencia",
            "Identificador del tipo de documento asociado al cliente. Referencia a la tabla TipoDocumento",
            "Estado del cliente. Por defecto: 1",
            "Indica si el cliente está activo (1: sí, 0: no). Por defecto: 1",
            "Fecha y hora en que se registró el cliente. Se asigna automáticamente",
        ])

    def test_el_script_con_contexto_pasa_la_revision(self):
        script = diccionario_faltante_tabla(TABLA_COMPLETA, "")["script"]
        self.assertEqual(verificar_diccionario_tablas(TABLA_COMPLETA, script), [])

    def test_parametro_segun_la_accion(self):
        for accion, uso in (("Sel_PorId", "que se desea consultar"), ("Upd", "que se desea actualizar"),
                            ("Del", "que se desea eliminar"), ("Lis", "por el que se filtra la lista")):
            procedimiento = f"CREATE PROCEDURE dbo.PA_Cliente_{accion}\n  @nClienteId INT\nAS\nSELECT 1"
            with self.subTest(accion=accion):
                self.assertIn(f"N'Identificador del cliente {uso}'", diccionario_faltante_procedimiento(procedimiento, "")["script"])


class TestSinSpacy(unittest.TestCase):
    """En una PC sin spaCy se usan las reglas del español: las sugerencias siguen saliendo."""

    def test_funciona_sin_spacy(self):
        with mock.patch.object(sugeridas, "_spacy", return_value=None):
            self.assertEqual(sugeridas.sugerir_columna("nAgenciaId", "Cliente"), "Identificador de la agencia asociada al cliente")
            self.assertEqual(sugeridas.sugerir_tabla("Clientes"), "Registra la información de los clientes")
            self.assertEqual(sugeridas.sugerir_columna("cCodSucursal", "Cliente"), "Código de la sucursal")


if __name__ == "__main__":
    unittest.main()
