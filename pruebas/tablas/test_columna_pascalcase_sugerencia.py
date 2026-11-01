"""Tablas, «Nombre de columna fuera del estándar» (1 nov.): dice qué palabra está mal y cómo queda el nombre.

Las siglas en mayúsculas (ID) están bien; lo que se observa es la palabra en minúscula que viene después.
"""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla


def _mensaje(columna: str, tipo: str = "VARCHAR(20) COLLATE SQL_Latin1_General_CP1_CI_AS"):
    sql = (f"CREATE TABLE GENERAL.Prueba (\n nPruebaId INT NOT NULL,\n {columna} {tipo} NOT NULL,\n"
           f" CONSTRAINT PK_Prueba_nPruebaId PRIMARY KEY CLUSTERED (nPruebaId)\n)")
    mensajes = [h.mensaje for h in verificar_tabla(sql) if h.regla == "COLUMNA_NOMBRE_NO_PASCALCASE"]
    return mensajes[0] if mensajes else None


class SugerenciaExactaTest(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        self.assertEqual(
            _mensaje("cPersIDnro"),
            "El nombre de la columna cPersIDnro no cumple la nomenclatura PascalCase: la palabra «nro» debe iniciar "
            "con mayúscula. Renombrar la columna como cPersIDNro, ya que después del prefijo cada palabra debe "
            "iniciar con mayúscula.",
        )

    def test_la_sigla_id_esta_bien(self):
        for columna, tipo in (("cPersIDNro", None), ("nPersIDTpo", "TINYINT"), ("cPersIdNro", None)):
            with self.subTest(columna=columna):
                self.assertIsNone(_mensaje(columna, tipo) if tipo else _mensaje(columna))

    def test_varias_palabras_tras_siglas(self):
        self.assertEqual(
            _mensaje("cIDnroRUCtpo"),
            "El nombre de la columna cIDnroRUCtpo no cumple la nomenclatura PascalCase: las palabras «nro» y «tpo» "
            "deben iniciar con mayúscula. Renombrar la columna como cIDNroRUCTpo, ya que después del prefijo cada "
            "palabra debe iniciar con mayúscula.",
        )

    def test_guiones_bajos(self):
        self.assertEqual(
            _mensaje("cPers_Nombre"),
            "El nombre de la columna cPers_Nombre no cumple la nomenclatura PascalCase: contiene guiones bajos. "
            "Renombrar la columna como cPersNombre, ya que después del prefijo cada palabra debe iniciar con "
            "mayúscula, sin guiones bajos.",
        )

    def test_todo_en_mayusculas(self):
        self.assertIn("está escrito en mayúsculas. Renombrar la columna como cPersona", _mensaje("cPERSONA"))

    def test_palabras_pegadas(self):
        self.assertIn("tiene palabras pegadas, sin mayúscula inicial. Renombrar la columna como nMontoAprobado",
                      _mensaje("nMontoaprobado", "INT"))

    def test_sin_sugerencia_no_inventa_un_ejemplo(self):
        mensaje = _mensaje("cpersonanombre")
        self.assertTrue(mensaje.endswith(
            "Renombrar la columna escribiendo cada palabra con mayúscula inicial después del prefijo."))
        self.assertNotIn("cPersonaNombre", mensaje)


if __name__ == "__main__":
    unittest.main()
