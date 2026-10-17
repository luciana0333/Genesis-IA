"""A1/A2 de Tablas: prefijos de TIME, FLOAT y tipos sin prefijo; FLOAT se cambia por DECIMAL."""

import unittest

from app.analizadores.analizador_tablas import verificar_tabla

C = "COLLATE SQL_Latin1_General_CP1_CI_AS"


def _tabla(columnas: str) -> str:
    return (
        "CREATE TABLE dbo.Cliente (\n"
        "    nClienteId INT IDENTITY(1,1) NOT NULL,\n"
        f"    {columnas}\n"
        "    CONSTRAINT PK_Cliente PRIMARY KEY CLUSTERED (nClienteId)\n"
        ")"
    )


def _reglas(sql: str):
    return {h.regla: h for h in verificar_tabla(sql)}


class TestPrefijosDeTipos(unittest.TestCase):
    def test_time_y_datetimeoffset_llevan_d(self):
        self.assertEqual(_reglas(_tabla("dHoraInicio TIME NOT NULL, dFechaZona DATETIMEOFFSET NOT NULL,")), {})
        hallazgo = _reglas(_tabla("cHoraInicio TIME NOT NULL,"))["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertIn("debe iniciar con 'd' (fecha u hora)", hallazgo.mensaje)
        self.assertIn("dHoraInicio", hallazgo.mensaje)

    def test_float_lleva_n(self):
        hallazgo = _reglas(_tabla("cMonto FLOAT NOT NULL,"))["COLUMNA_PREFIJO_TIPO_INVALIDO"]
        self.assertIn("debe iniciar con 'n' (número)", hallazgo.mensaje)

    def test_tipo_sin_prefijo_no_inventa_uno(self):
        # Antes sugería cCodigo, hHora y dDatos (d es fecha).
        hallazgos = verificar_tabla(_tabla("Codigo UNIQUEIDENTIFIER NOT NULL, Datos XML NOT NULL,"))
        mensajes = " ".join(h.mensaje for h in hallazgos)
        self.assertNotIn("cCodigo", mensajes)
        self.assertNotIn("dDatos", mensajes)
        self.assertNotIn("→", mensajes)


class TestFloat(unittest.TestCase):
    def test_float_se_cambia_por_decimal(self):
        hallazgo = _reglas(_tabla("nMonto FLOAT NOT NULL,"))["COLUMNA_TIPO_APROXIMADO"]
        self.assertEqual(hallazgo.severidad.value, "alto")
        self.assertIn("Emplear DECIMAL(p, s) en su lugar", hallazgo.mensaje)

    def test_varias_float_se_agrupan(self):
        hallazgo = _reglas(_tabla("nMonto FLOAT NOT NULL, nTasa FLOAT(24) NOT NULL,"))["COLUMNA_TIPO_APROXIMADO"]
        self.assertIn("Se identificaron 2 columnas de tipo FLOAT", hallazgo.mensaje)
        self.assertIn("nMonto (FLOAT → DECIMAL)", hallazgo.mensaje)

    def test_decimal_no_se_marca(self):
        self.assertEqual(_reglas(_tabla("nMonto DECIMAL(18, 2) NOT NULL,")), {})


if __name__ == "__main__":
    unittest.main()
