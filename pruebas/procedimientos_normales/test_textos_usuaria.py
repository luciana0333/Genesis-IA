"""Textos que la usuaria dictó para Procedimientos de negocio (NOLOCK en UPDATE y en temporal, WAITFOR, WHILE)."""

import unittest

from app.analizadores.analizador_procedimientos_normales import (
    _duracion_en_palabras,
    verificar_procedimiento_normal,
)

PROCEDIMIENTO = """CREATE PROCEDURE dbo.PA_Cliente_Upd_Estado
  @n INT
AS
BEGIN
  SET NOCOUNT ON;
  CREATE TABLE #Pendientes (nId INT)
  UPDATE c SET c.nEstado = 1 FROM dbo.Cliente c WITH (NOLOCK) INNER JOIN #Pendientes p WITH (NOLOCK) ON p.nId = c.nClienteId
  WAITFOR DELAY '00:00:05'
  WHILE @n > 0 BEGIN SET @n = @n - 1 END
END"""


class TestTextosUsuaria(unittest.TestCase):
    def setUp(self):
        self.mensajes = {h.regla: h.mensaje for h in verificar_procedimiento_normal(PROCEDIMIENTO)}

    def test_nolock_en_update(self):
        self.assertEqual(
            self.mensajes["NOLOCK_EN_TABLA_FISICA"],
            "Se identificó el uso de WITH (NOLOCK) en la tabla dbo.Cliente, sobre la cual se realiza una "
            "actualización. Se recomienda retirar WITH (NOLOCK), ya que SQL Server ignora esta instrucción en la "
            "tabla que se actualiza y su uso no es una buena práctica.",
        )

    def test_nolock_en_tabla_temporal(self):
        self.assertEqual(
            self.mensajes["NOLOCK_EN_TABLA_TEMPORAL"],
            "Se identificó el uso de WITH (NOLOCK) en la tabla temporal #Pendientes. Se recomienda retirar "
            "WITH (NOLOCK), ya que las tablas temporales son de uso exclusivo de la sesión que las crea, por lo "
            "que no requieren esta instrucción para evitar bloqueos entre sesiones.",
        )

    def test_waitfor(self):
        self.assertEqual(
            self.mensajes["WAITFOR_DELAY_PROHIBIDO"],
            "Se identificó el uso de WAITFOR DELAY '00:00:05', que detiene la ejecución del procedimiento durante "
            "cinco segundos. Se recomienda retirar esta instrucción, ya que obligar al motor de base de datos a "
            "esperar innecesariamente retrasa la ejecución y constituye una mala práctica.",
        )

    def test_while(self):
        self.assertEqual(
            self.mensajes["WHILE_PROHIBIDO"],
            "Se identificó el uso de un bucle WHILE en el procedimiento. Se recomienda evaluar otras alternativas "
            "que permitan procesar los registros en conjunto y evitar el uso de WHILE, ya que puede generar "
            "bucles infinitos y afectar el rendimiento del procedimiento.",
        )

    def test_duracion_en_palabras(self):
        casos = {
            "'00:00:05'": "cinco segundos",
            "'00:01:30'": "un minuto y treinta segundos",
            "'01:00:00'": "una hora",
            "'00:00:21'": "veintiún segundos",
            "'02:01:01'": "dos horas, un minuto y un segundo",
            "'texto'": "",
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(_duracion_en_palabras(valor), esperado)

    def test_waitfor_time(self):
        sql = PROCEDIMIENTO.replace("WAITFOR DELAY '00:00:05'", "WAITFOR TIME '22:00'")
        mensaje = next(h.mensaje for h in verificar_procedimiento_normal(sql) if h.regla == "WAITFOR_DELAY_PROHIBIDO")
        self.assertIn("que detiene la ejecución del procedimiento hasta las 22:00.", mensaje)


if __name__ == "__main__":
    unittest.main()
