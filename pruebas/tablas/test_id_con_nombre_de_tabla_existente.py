"""ALTER TABLE: el Id que repite el nombre de una tabla que ya existe no se observa por PascalCase (usuaria, 22 nov.).

Caso real: «ALTER TABLE CE_PROYECTOSINMOBILIARIOS_VALOROBRA ADD nCE_ProyectosInmobiliarios_ValorObraId INT IDENTITY».
La tabla ya existe con ese nombre; su PK debe respetarlo, con sus guiones bajos.
"""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla

_ALTER = ("ALTER TABLE dbo.CE_PROYECTOSINMOBILIARIOS_VALOROBRA\n"
          "ADD nCE_ProyectosInmobiliarios_ValorObraId INT IDENTITY(1,1) NOT NULL;\n"
          "ALTER TABLE dbo.CE_PROYECTOSINMOBILIARIOS_VALOROBRA\n"
          "ADD CONSTRAINT PK_CE_PROYECTOSINMOBILIARIOS_VALOROBRA PRIMARY KEY CLUSTERED (nCE_ProyectosInmobiliarios_ValorObraId);")


def _reglas(sql):
    return [h.regla for h in verificar_tabla(sql)]


class IdConNombreDeTablaExistenteTest(unittest.TestCase):
    def test_el_id_con_el_nombre_de_la_tabla_no_se_marca(self):
        self.assertNotIn("COLUMNA_NOMBRE_NO_PASCALCASE", _reglas(_ALTER))

    def test_otra_columna_con_guiones_bajos_si(self):
        sql = ("ALTER TABLE dbo.CE_PROYECTOSINMOBILIARIOS_VALOROBRA "
               "ADD cNombre_Obra VARCHAR(50) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL DEFAULT '';")
        self.assertIn("COLUMNA_NOMBRE_NO_PASCALCASE", _reglas(sql))

    def test_en_una_tabla_nueva_si(self):
        # En un CREATE la tabla es nueva: debe nacer con el estándar.
        sql = "CREATE TABLE dbo.CE_PROYECTOS_OBRA (nCE_PROYECTOS_OBRAId INT IDENTITY(1,1) NOT NULL PRIMARY KEY);"
        self.assertIn("COLUMNA_NOMBRE_NO_PASCALCASE", _reglas(sql))


if __name__ == "__main__":
    unittest.main()
