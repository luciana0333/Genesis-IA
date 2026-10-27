"""Índices: tablas existentes en una sola observación y columna de la clave fija en el filtro WHERE."""

import unittest

from app.analizadores.analizador_indices import verificar_indices

INDICES_DE_LA_USUARIA = """CREATE UNIQUE NONCLUSTERED INDEX IXUN_CuentasOrdenEstadisticoCapitalLote_cPeriodo_nTipoEstadistico_nMoneda_bVigente
ON CONTABILIDAD.CuentasOrdenEstadisticoCapitalLote (cPeriodo, nTipoEstadistico, nMoneda, bVigente)
WHERE bVigente = 1
GO

CREATE NONCLUSTERED INDEX IXN_CuentasOrdenEstadisticoCapitalDet_nCuentasOrdenEstadisticoCapitalLoteId_cTipoProceso_nMoneda_cCtaCod_INC07
ON CONTABILIDAD.CuentasOrdenEstadisticoCapitalDet (nCuentasOrdenEstadisticoCapitalLoteId, cTipoProceso, nMoneda, cCtaCod)
INCLUDE (cPrograma, cComponente, cCtaContCod, cCodAge, nTipoCreditos, nPrdEstado, nImporteEstadistico)
GO
"""


def _reglas(texto: str, regla: str):
    return [h for h in verificar_indices(texto, "") if h.regla == regla]


class TestTablasExistentesJuntas(unittest.TestCase):
    def test_caso_de_la_usuaria_una_sola_observacion(self):
        hallazgos = _reglas(INDICES_DE_LA_USUARIA, "INDICE_TABLA_EXISTENTE")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].lineas, [2, 7])
        self.assertEqual(hallazgos[0].seccion, "indices")
        self.assertTrue(hallazgos[0].mensaje.startswith(
            "Se identificaron 2 índices para tablas que ya existen (su CREATE TABLE no está en el script de la "
            "tabla): Índice IXUN_CuentasOrdenEstadisticoCapitalLote_cPeriodo_nTipoEstadistico_nMoneda_bVigente "
            "(tabla CONTABILIDAD.CuentasOrdenEstadisticoCapitalLote); Índice "
            "IXN_CuentasOrdenEstadisticoCapitalDet_nCuentasOrdenEstadisticoCapitalLoteId_cTipoProceso_nMoneda_cCtaCod_INC07 "
            "(tabla CONTABILIDAD.CuentasOrdenEstadisticoCapitalDet). Se recomienda validar que cada tabla"))

    def test_un_solo_indice_sigue_igual(self):
        texto = "CREATE NONCLUSTERED INDEX IXN_Cliente_cCodigo ON dbo.Cliente (cCodigo);"
        hallazgos = _reglas(texto, "INDICE_TABLA_EXISTENTE")
        self.assertEqual(len(hallazgos), 1)
        self.assertTrue(hallazgos[0].mensaje.startswith("Se identificó que el índice IXN_Cliente_cCodigo es para la tabla"))


class TestColumnaFijaEnFiltro(unittest.TestCase):
    def test_caso_de_la_usuaria(self):
        hallazgos = _reglas(INDICES_DE_LA_USUARIA, "INDICE_COLUMNA_FIJA_EN_FILTRO")
        self.assertEqual(len(hallazgos), 1)
        self.assertEqual(hallazgos[0].severidad.value, "bajo")
        self.assertEqual(
            hallazgos[0].mensaje,
            "Se identificó que la columna bVigente del índice "
            "IXUN_CuentasOrdenEstadisticoCapitalLote_cPeriodo_nTipoEstadistico_nMoneda_bVigente forma parte de su "
            "clave, pero el filtro WHERE bVigente = 1 ya la fija en un solo valor. Se recomienda retirarla de la clave "
            "del índice, ya que no aporta para ordenar ni para distinguir las filas y solo ocupa espacio "
            "(ej.: (cPeriodo, nTipoEstadistico, nMoneda) WHERE bVigente = 1).",
        )

    def test_no_se_marca(self):
        casos = (
            # La columna del filtro no está en la clave.
            "CREATE NONCLUSTERED INDEX IXN_T_cCodigo ON dbo.T (cCodigo) WHERE bVigente = 1;",
            # Rango, no un solo valor.
            "CREATE NONCLUSTERED INDEX IXN_T_nMonto ON dbo.T (nMonto) WHERE nMonto > 0;",
            # Con OR la columna puede tener más de un valor.
            "CREATE NONCLUSTERED INDEX IXN_T_cCodigo_nEstado ON dbo.T (cCodigo, nEstado) WHERE nEstado = 1 OR nEstado = 2;",
            # Es la única columna de la clave: no se puede quitar.
            "CREATE NONCLUSTERED INDEX IXN_T_bVigente ON dbo.T (bVigente) WHERE bVigente = 1;",
            # Sin filtro.
            "CREATE NONCLUSTERED INDEX IXN_T_cCodigo_bVigente ON dbo.T (cCodigo, bVigente);",
        )
        for texto in casos:
            with self.subTest(texto=texto):
                self.assertEqual(_reglas(texto, "INDICE_COLUMNA_FIJA_EN_FILTRO"), [])

    def test_is_null_y_varias_columnas(self):
        texto = ("CREATE NONCLUSTERED INDEX IXN_T_cCodigo_nEstado_dBaja ON dbo.T (cCodigo, nEstado, dBaja) "
                 "WHERE nEstado = 1 AND dBaja IS NULL WITH (ONLINE = ON);")
        hallazgos = _reglas(texto, "INDICE_COLUMNA_FIJA_EN_FILTRO")
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("las columnas nEstado y dBaja", hallazgos[0].mensaje)
        self.assertIn("(ej.: (cCodigo) WHERE nEstado = 1 AND dBaja IS NULL)", hallazgos[0].mensaje)


if __name__ == "__main__":
    unittest.main()
