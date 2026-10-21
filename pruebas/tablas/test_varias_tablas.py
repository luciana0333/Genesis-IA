# -*- coding: utf-8 -*-
"""Script con varias tablas: cada regla se reporta una sola vez, con la tabla y la línea de cada caso."""

import unittest

from app.analizadores import ortografia

from app.analizadores.analizador_tablas import verificar_tabla

UNA_TABLA = """CREATE TABLE Bonificacion.MetaSaldo(
    nMetaSaldoId INT IDENTITY(1,1) PRIMARY KEY,
    nGradoSatisfaccion VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL
)
"""

VARIAS_TABLAS = """CREATE TABLE Bonificacion.EsquemaSupervisores(
    nEsquemaSupervisoresId INT IDENTITY(1,1) PRIMARY KEY,
    nGradoSatisfaccion VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL
)

CREATE TABLE Bonificacion.EsquemaEjecutivos(
    nEsquemaEjecutivosId INT IDENTITY(1,1) PRIMARY KEY,
    nGradoSatisfaccion VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL
)

CREATE TABLE Bonificacion.SolicitudDetalleMeta(
    nSolicitudDetalleMetaId INT IDENTITY(1,1) PRIMARY KEY,
    nMeta2 DECIMAL(18,2) NOT NULL
)
"""


def _por_regla(hallazgos):
    return {h.regla: h for h in hallazgos}


class TestVariasTablas(unittest.TestCase):
    def test_una_tabla_igual_que_siempre(self):
        hallazgo = _por_regla(verificar_tabla(UNA_TABLA))["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertTrue(hallazgo.mensaje.startswith("La columna nGradoSatisfaccion es de tipo VARCHAR"))

    def test_misma_regla_en_varias_tablas_se_une(self):
        hallazgos = verificar_tabla(VARIAS_TABLAS)
        prefijos = [h for h in hallazgos if h.regla == "COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertEqual(len(prefijos), 1)
        mensaje = prefijos[0].mensaje
        # Redacción de la usuaria; las líneas van en el encabezado (hallazgo.lineas), no en el texto.
        self.assertEqual(
            mensaje,
            "Se identificaron dos columnas cuyo prefijo no corresponde al tipo de dato definido: "
            "Bonificacion.EsquemaSupervisores : Cambiar nGradoSatisfaccion por cGradoSatisfaccion; "
            "Bonificacion.EsquemaEjecutivos : Cambiar nGradoSatisfaccion por cGradoSatisfaccion. "
            "Corregir los nombres de ambas columnas, utilizando el prefijo c en lugar de n, "
            "ya que corresponden a datos de tipo texto y no numéricos.",
        )
        self.assertEqual(prefijos[0].lineas, [3, 8])

    def test_un_solo_caso_dice_su_tabla(self):
        hallazgo = _por_regla(verificar_tabla(VARIAS_TABLAS))["COLUMNA_NOMBRE_CON_NUMERO"]
        # El texto ya nombra la tabla: no se antepone «En la tabla…».
        self.assertTrue(hallazgo.mensaje.startswith(
            "Se identificó que la columna nMeta2 de la tabla Bonificacion.SolicitudDetalleMeta contiene un número"))
        self.assertEqual(hallazgo.linea, 13)

    def test_reglas_de_tabla_en_varias_tablas(self):
        script = VARIAS_TABLAS.replace("Bonificacion.EsquemaSupervisores", "Bonificacion.Esquema_Supervisores") \
                              .replace("Bonificacion.EsquemaEjecutivos", "Bonificacion.Esquema_Ejecutivos")
        hallazgo = _por_regla(verificar_tabla(script))["TABLA_NOMBRE_NO_PASCALCASE"]
        self.assertIn("Se identificaron dos tablas con nombre fuera del estándar", hallazgo.mensaje)
        self.assertIn("Bonificacion.Esquema_Supervisores → EsquemaSupervisores; ", hallazgo.mensaje)
        self.assertNotIn("línea", hallazgo.mensaje)
        self.assertIn("Renombrar cada tabla en PascalCase", hallazgo.mensaje)

    def test_prefijo_en_tres_tablas(self):
        gerentes = VARIAS_TABLAS.replace("Bonificacion.EsquemaSupervisores", "Bonificacion.EsquemaGerentes")
        script = VARIAS_TABLAS + gerentes.split("CREATE TABLE Bonificacion.EsquemaEjecutivos")[0]
        hallazgo = _por_regla(verificar_tabla(script))["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertTrue(hallazgo.mensaje.startswith("Se identificaron tres columnas cuyo prefijo"))
        self.assertIn("Corregir los nombres de las tres columnas", hallazgo.mensaje)


    def test_siglas_son_por_validar_con_severidad_media(self):
        script = VARIAS_TABLAS.replace("nGradoSatisfaccion VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS",
                                       "nSaldoTCF DECIMAL(18,2)").replace(
            "Bonificacion.SolicitudDetalleMeta", "Bonificacion.MetaTPPP").replace("nSolicitudDetalleMetaId", "nMetaTPPPId")
        hallazgos = _por_regla(verificar_tabla(script))
        columnas = hallazgos["COLUMNA_NOMBRE_CON_SIGLA"]
        self.assertEqual(columnas.severidad.value, "medio")
        self.assertIn("Se identificaron tres columnas cuyo nombre contiene siglas: "
                      "Bonificacion.EsquemaSupervisores : nSaldoTCF (sigla TCF); "
                      "Bonificacion.EsquemaEjecutivos : nSaldoTCF (sigla TCF); "
                      "Bonificacion.MetaTPPP : nMetaTPPPId (sigla TPPP).", columnas.mensaje)
        tabla = hallazgos["TABLA_NOMBRE_CON_SIGLA"]
        self.assertEqual(tabla.mensaje,
                         "Se identificó que el nombre de la tabla Bonificacion.MetaTPPP contiene la sigla TPPP. "
                         "Se recomienda validar su significado y, de ser posible, reemplazarla por palabras "
                         "descriptivas (ej.: MetaTasaPromPonderada), ya que las siglas dificultan identificar qué "
                         "información almacena la tabla.")
        self.assertNotIn("COLUMNA_NOMBRE_NO_PASCALCASE", hallazgos)
        self.assertNotIn("TABLA_NOMBRE_NO_PASCALCASE", hallazgos)

    def test_sigla_con_otro_error_es_fuera_del_estandar(self):
        script = VARIAS_TABLAS.replace("nGradoSatisfaccion VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS",
                                       "nSaldo_TCF DECIMAL(18,2)")
        hallazgos = _por_regla(verificar_tabla(script))
        self.assertIn("COLUMNA_NOMBRE_NO_PASCALCASE", hallazgos)
        self.assertNotIn("COLUMNA_NOMBRE_CON_SIGLA", hallazgos)


    @unittest.skipUnless(ortografia.disponible(), "Requiere el diccionario de español (pyspellchecker)")
    def test_nombre_todo_en_minusculas_se_separa_en_palabras(self):
        script = VARIAS_TABLAS.replace("Bonificacion.EsquemaEjecutivos", "Bonificacion.esquematotalizadoejecutivos")
        hallazgo = _por_regla(verificar_tabla(script))["TABLA_NOMBRE_NO_PASCALCASE"]
        self.assertTrue(hallazgo.mensaje.endswith("Renómbrela como EsquemaTotalizadoEjecutivos."))

    @unittest.skipUnless(ortografia.disponible(), "Requiere el diccionario de español (pyspellchecker)")
    def test_si_no_se_puede_separar_no_inventa_nombre(self):
        script = VARIAS_TABLAS.replace("Bonificacion.EsquemaEjecutivos", "Bonificacion.xqzwrtplk")
        hallazgo = _por_regla(verificar_tabla(script))["TABLA_NOMBRE_NO_PASCALCASE"]
        self.assertNotIn("Renómbrela como", hallazgo.mensaje)
        self.assertIn("Use PascalCase", hallazgo.mensaje)


    def test_tablas_con_sigla_texto_de_la_usuaria(self):
        script = VARIAS_TABLAS.replace("Bonificacion.EsquemaSupervisores", "Bonificacion.MetaTPPP")             .replace("Bonificacion.EsquemaEjecutivos", "Bonificacion.SaldoRenovacionPF")
        hallazgo = _por_regla(verificar_tabla(script))["TABLA_NOMBRE_CON_SIGLA"]
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificaron dos tablas cuyos nombres contienen siglas: Bonificacion.MetaTPPP (TPPP); "
            "Bonificacion.SaldoRenovacionPF (PF). Validar que las siglas sean comprensibles y estén "
            "estandarizadas. De ser necesario, reemplazarlas por términos descriptivos que faciliten la "
            "comprensión del nombre de la tabla.",
        )


if __name__ == "__main__":
    unittest.main()
