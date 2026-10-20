# -*- coding: utf-8 -*-
"""Cada observación de Diccionarios indica en qué cajita está su línea (para mostrar su código y llevar a ella)."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import verificar_diccionario_tablas

TABLA = """CREATE TABLE dbo.Cliente (
    nIdCliente INT NOT NULL,
    cNombre VARCHAR(50) NOT NULL,
    cApellido VARCHAR(50) NOT NULL
)
"""
DICCIONARIO_TABLA = """EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Tabla de clientes', @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cliente'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'', @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'nIdCliente'
GO
EXEC sys.sp_addextendedproperty @name=N'MS_Description', @value=N'Nombre del clinte', @level0type=N'SCHEMA', @level0name=N'dbo', @level1type=N'TABLE', @level1name=N'Cliente', @level2type=N'COLUMN', @level2name=N'cNombre'
"""
PROCEDIMIENTO = "CREATE PROCEDURE dbo.PA_Cliente_Sel_PorId\n  @nIdCliente INT,\n  @cNombre VARCHAR(10)\nAS\nSELECT 1\n"
DICCIONARIO_PROCEDIMIENTO = (
    "EXEC sys.sp_addextendedproperty N'MS_Description', N'Consulta el cliente', N'SCHEMA', N'dbo', N'PROCEDURE', N'PA_Cliente_Sel_PorId'\n"
    "GO\n"
    "EXEC sys.sp_addextendedproperty N'MS_Description', N'', N'SCHEMA', N'dbo', N'PROCEDURE', N'PA_Cliente_Sel_PorId', N'PARAMETER', N'@nIdCliente'\n"
)


def _por_regla(hallazgos):
    return {h.regla: (h.linea, getattr(h, "seccion", None)) for h in hallazgos}


class TestSeccionesDiccionario(unittest.TestCase):
    def test_tabla_cada_linea_en_su_cajita(self):
        hallazgos = _por_regla(verificar_diccionario_tablas(TABLA, DICCIONARIO_TABLA))
        self.assertEqual(hallazgos["COLUMNA_FALTANTE"], (4, "objeto"))  # cApellido, línea 4 del CREATE TABLE
        self.assertEqual(hallazgos["DESCRIPCION_COLUMNA_VACIA"], (3, "diccionario"))
        self.assertEqual(hallazgos["ERROR_ORTOGRAFICO"], (5, "diccionario"))

    def test_tabla_sin_descripcion_es_general(self):
        sin_tabla = "\n".join(DICCIONARIO_TABLA.splitlines()[2:])
        hallazgos = _por_regla(verificar_diccionario_tablas(TABLA, sin_tabla))
        self.assertEqual(hallazgos["TABLA_SIN_DESCRIPCION"][1], "general")

    def test_procedimiento_cada_linea_en_su_cajita(self):
        hallazgos = _por_regla(verificar_diccionario(PROCEDIMIENTO, DICCIONARIO_PROCEDIMIENTO))
        self.assertEqual(hallazgos["PARAMETRO_FALTANTE"], (3, "objeto"))  # @cNombre, línea 3 del CREATE PROCEDURE
        self.assertEqual(hallazgos["DESCRIPCION_VACIA"], (3, "diccionario"))

    def test_nombre_del_procedimiento_es_del_objeto(self):
        proc = PROCEDIMIENTO.replace("PA_Cliente_Sel_PorId", "ConsultarCliente")
        dic = DICCIONARIO_PROCEDIMIENTO.replace("PA_Cliente_Sel_PorId", "ConsultarCliente")
        hallazgos = verificar_diccionario(proc, dic)
        nomenclatura = [h for h in hallazgos if h.regla.startswith("PROCEDIMIENTO_")]
        self.assertTrue(nomenclatura)
        self.assertTrue(all(h.seccion == "objeto" and h.linea == 1 for h in nomenclatura))

    def test_agrupadas_conservan_cajita_y_lineas(self):
        tabla = TABLA.replace("    cApellido VARCHAR(50) NOT NULL\n", "    cApellido VARCHAR(50) NOT NULL,\n    cCorreo VARCHAR(50) NOT NULL\n")
        hallazgo = next(h for h in verificar_diccionario_tablas(tabla, DICCIONARIO_TABLA) if h.regla == "COLUMNA_FALTANTE")
        self.assertEqual(hallazgo.seccion, "objeto")
        self.assertEqual(hallazgo.lineas, [4, 5])


if __name__ == "__main__":
    unittest.main()
