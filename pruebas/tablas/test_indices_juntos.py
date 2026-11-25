"""Índices de Conciliación (usuaria, 25 nov.): las observaciones repetidas van juntas y lo que envuelve el script
(TRY/CATCH, la transacción, SELECT 'OK') no es «una instrucción que no es un índice»."""
import unittest

from app.analizadores.analizador_indices import verificar_indices

TABLA = ("CREATE TABLE Conciliacion.Devoluciones (nDevolucionesId INT IDENTITY(1,1) NOT NULL, nPeriodo INT NOT NULL, "
         "nMoneda INT NOT NULL, nMonto MONEY NOT NULL, nPolizaId INT NOT NULL, nSegurosId INT NOT NULL, "
         "cNroCertificado VARCHAR(25) COLLATE SQL_Latin1_General_CP1_CI_AS NOT NULL, nOrigen INT NOT NULL, "
         "dFecha DATE NOT NULL, CONSTRAINT PK_Devoluciones PRIMARY KEY CLUSTERED (nDevolucionesId));")

ENVUELTO = """BEGIN TRY
    BEGIN TRANSACTION OPERACION
        CREATE UNIQUE NONCLUSTERED INDEX IXN_Devoluciones_nPeriodo ON Conciliacion.Devoluciones (nPeriodo)
        CREATE UNIQUE NONCLUSTERED INDEX IXN_Devoluciones_nMoneda ON Conciliacion.Devoluciones (nMoneda)
        CREATE NONCLUSTERED INDEX IXN_Devoluciones_nPeriodo_dFecha_INC06 ON Conciliacion.Devoluciones (nPeriodo, dFecha)
        INCLUDE (nMonto, nPolizaId, nSegurosId, cNroCertificado, nOrigen, nMoneda);
        CREATE NONCLUSTERED INDEX IXN_Devoluciones_dFecha_INC06 ON Conciliacion.Devoluciones (dFecha)
        INCLUDE (nMonto, nPolizaId, nSegurosId, cNroCertificado, nOrigen, nMoneda);
    COMMIT TRANSACTION OPERACION
    SELECT 'OK'
END TRY
BEGIN CATCH
    DECLARE @pnError INT
    SELECT @pnError = ERROR_NUMBER()
    IF XACT_STATE() <> 0
    BEGIN
        ROLLBACK TRANSACTION OPERACION
    END
END CATCH"""


class IndicesJuntos(unittest.TestCase):
    def setUp(self):
        self.hallazgos = verificar_indices(ENVUELTO, TABLA)

    def _de(self, regla):
        return [h for h in self.hallazgos if h.regla == regla]

    def test_la_envoltura_no_es_una_instruccion_ajena(self):
        self.assertEqual(self._de("INDICE_SENTENCIA_NO_RECONOCIDA"), [])

    def test_lo_que_no_es_envoltura_se_sigue_marcando(self):
        hallazgos = verificar_indices(
            "CREATE NONCLUSTERED INDEX IXN_Devoluciones_nPeriodo ON Conciliacion.Devoluciones (nPeriodo);\n"
            "UPDATE Conciliacion.Devoluciones SET nMoneda = 1", TABLA)
        self.assertEqual(len([h for h in hallazgos if h.regla == "INDICE_SENTENCIA_NO_RECONOCIDA"]), 1)

    def test_prefijos_en_una_sola_observacion(self):
        prefijos = self._de("INDICE_PREFIJO_INVALIDO")
        self.assertEqual(len(prefijos), 1)
        self.assertTrue(prefijos[0].mensaje.startswith(
            "Se identificaron dos índices que no utilizan el prefijo correspondiente a su tipo "
            "(IXUN_ para índices unique nonclustered): IXN_Devoluciones_nPeriodo → IXUN_Devoluciones_nPeriodo; "))

    def test_include_extenso_en_una_sola_observacion(self):
        incluidas = self._de("INDICE_INCLUDE_EXTENSO")
        self.assertEqual(len(incluidas), 1)
        # Uno por viñeta: «Se identificaron dos índices…: A → 6 columnas: …; B → 6 columnas: ….»
        self.assertIn("Se identificaron dos índices con muchas columnas en su INCLUDE: "
                      "IXN_Devoluciones_nPeriodo_dFecha_INC06 → 6 columnas: ", incluidas[0].mensaje)


if __name__ == "__main__":
    unittest.main()
