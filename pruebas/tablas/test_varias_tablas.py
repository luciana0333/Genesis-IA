# -*- coding: utf-8 -*-
"""Script con varias tablas: cada regla se reporta una sola vez, con la tabla y la línea de cada caso."""

import unittest

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
            "Se recomienda corregir los nombres de ambas columnas, utilizando el prefijo c en lugar de n, "
            "ya que corresponden a datos de tipo texto y no numéricos.",
        )
        self.assertEqual(prefijos[0].lineas, [3, 8])

    def test_un_solo_caso_dice_su_tabla(self):
        hallazgo = _por_regla(verificar_tabla(VARIAS_TABLAS))["COLUMNA_NOMBRE_CON_NUMERO"]
        self.assertTrue(hallazgo.mensaje.startswith(
            "En la tabla Bonificacion.SolicitudDetalleMeta, el nombre de la columna nMeta2 contiene números"))
        self.assertEqual(hallazgo.linea, 13)

    def test_reglas_de_tabla_en_varias_tablas(self):
        script = VARIAS_TABLAS.replace("Bonificacion.EsquemaSupervisores", "Bonificacion.Esquema_Supervisores") \
                              .replace("Bonificacion.EsquemaEjecutivos", "Bonificacion.Esquema_Ejecutivos")
        hallazgo = _por_regla(verificar_tabla(script))["TABLA_NOMBRE_NO_PASCALCASE"]
        self.assertIn("Se identificaron 2 tablas con nombre fuera del estándar", hallazgo.mensaje)
        self.assertIn("Bonificacion.Esquema_Supervisores → EsquemaSupervisores; ", hallazgo.mensaje)
        self.assertNotIn("línea", hallazgo.mensaje)
        self.assertIn("Renombrar cada tabla en PascalCase", hallazgo.mensaje)

    def test_prefijo_en_tres_tablas(self):
        gerentes = VARIAS_TABLAS.replace("Bonificacion.EsquemaSupervisores", "Bonificacion.EsquemaGerentes")
        script = VARIAS_TABLAS + gerentes.split("CREATE TABLE Bonificacion.EsquemaEjecutivos")[0]
        hallazgo = _por_regla(verificar_tabla(script))["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertTrue(hallazgo.mensaje.startswith("Se identificaron tres columnas cuyo prefijo"))
        self.assertIn("Se recomienda corregir los nombres de las tres columnas", hallazgo.mensaje)


if __name__ == "__main__":
    unittest.main()
