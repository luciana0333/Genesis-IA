"""Misma columna con el mismo error en varias tablas: se dice una vez, con todas sus tablas."""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla

SCRIPT = """CREATE TABLE Garantia.Testimonio (
    nTestimonioId INT IDENTITY(1,1) NOT NULL,
    cNumGarant BIGINT NOT NULL,
    cCtaCod VARCHAR(18) NULL,
    CONSTRAINT PK_Testimonio PRIMARY KEY (nTestimonioId))
CREATE TABLE Garantia.TestimonioMovimiento (
    nTestimonioMovimientoId INT IDENTITY(1,1) NOT NULL,
    cNumGarant BIGINT NOT NULL,
    cCtaCod VARCHAR(18) NOT NULL,
    CONSTRAINT PK_TestimonioMovimiento PRIMARY KEY (nTestimonioMovimientoId))
CREATE TABLE Garantia.AmpliarTestimonio (
    nAmpliarTestimonioId INT IDENTITY(1,1) NOT NULL,
    cNumGarant BIGINT NOT NULL,
    cUsuario VARCHAR(4) NOT NULL,
    CONSTRAINT PK_AmpliarTestimonio PRIMARY KEY (nAmpliarTestimonioId))"""


def _mensajes():
    return {h.regla: h for h in verificar_tabla(SCRIPT, False)}


class MismaColumnaVariasTablasTest(unittest.TestCase):
    def test_prefijo_una_vez_con_sus_tablas(self):
        hallazgo = _mensajes()["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertEqual(hallazgo.lineas, [3, 8, 13])
        self.assertEqual(
            hallazgo.mensaje,
            "Se identificaron tres columnas cuyo prefijo no corresponde al tipo de dato definido: Cambiar cNumGarant "
            "por nNumGarant en las tablas Garantia.Testimonio, Garantia.TestimonioMovimiento y Garantia.AmpliarTestimonio. "
            "Corregir los nombres de las tres columnas, utilizando el prefijo n en lugar de c, ya que corresponden "
            "a datos de tipo numérico y no de texto.",
        )

    def test_otras_reglas_tambien_juntan_la_columna(self):
        mensaje = _mensajes()["COLUMNA_SIN_COLLATE"].mensaje
        self.assertIn("cCtaCod (Garantia.Testimonio y Garantia.TestimonioMovimiento); "
                      "cUsuario (Garantia.AmpliarTestimonio)", mensaje)
        self.assertEqual(mensaje.count("cCtaCod"), 1)

    def test_columnas_distintas_siguen_por_separado(self):
        sql = SCRIPT.replace("cNumGarant BIGINT NOT NULL,\n    cUsuario", "cNumGarantia BIGINT NOT NULL,\n    cUsuario")
        mensaje = {h.regla: h for h in verificar_tabla(sql, False)}["COLUMNA_PREFIJO_TIPO_INVALIDO"].mensaje
        self.assertIn("Cambiar cNumGarant por nNumGarant en las tablas Garantia.Testimonio y Garantia.TestimonioMovimiento; "
                      "Garantia.AmpliarTestimonio : Cambiar cNumGarantia por nNumGarantia", mensaje)


if __name__ == "__main__":
    unittest.main()
