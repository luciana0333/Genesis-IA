"""Diccionarios con varias tablas o varios procedimientos en el mismo script."""

import unittest

from app.analizadores.analizador_diccionario_procedimientos import diccionario_por_procedimiento, verificar_diccionario
from app.analizadores.analizador_diccionario_tablas import diccionario_por_tabla, verificar_diccionario_tablas
from app.analizadores.diccionario_generador import diccionario_faltante_procedimiento, diccionario_faltante_tabla
from app.analizadores.diccionario_varios import unir_faltantes


def propiedad(valor, tipo, objeto, tipo2=None, nombre2=None):
    """Con parámetros por posición, como en los scripts de la usuaria."""
    sentencia = (f"EXEC sys.sp_addextendedproperty N'MS_Description', N'{valor}', "
                 f"N'schema', N'Bonificacion', N'{tipo}', N'{objeto}'")
    if tipo2:
        sentencia += f", N'{tipo2}', N'{nombre2}'"
    return sentencia + ";\nGO"


TABLAS = """CREATE TABLE Bonificacion.EsquemaTotalizadoEjecutivos (
    nIdEjecutivo INT NOT NULL,
    nBonoComercial DECIMAL(18,2) NOT NULL,
    CONSTRAINT PK_EsquemaTotalizadoEjecutivos PRIMARY KEY CLUSTERED (nIdEjecutivo)
);
GO
CREATE TABLE Bonificacion.EsquemaTotalizadoSupervisores (
    nIdSupervisor INT NOT NULL,
    nBonoComercial DECIMAL(18,2) NOT NULL,
    CONSTRAINT PK_EsquemaTotalizadoSupervisores PRIMARY KEY CLUSTERED (nIdSupervisor)
);
GO"""


def diccionario_tablas(*extra):
    return "\n".join([
        propiedad("Totalizado de bonos de los ejecutivos", "table", "EsquemaTotalizadoEjecutivos"),
        propiedad("Identificador del ejecutivo", "table", "EsquemaTotalizadoEjecutivos", "column", "nIdEjecutivo"),
        propiedad("Bono de gestión comercial", "table", "EsquemaTotalizadoEjecutivos", "column", "nBonoComercial"),
        propiedad("Totalizado de bonos de los supervisores", "table", "EsquemaTotalizadoSupervisores"),
        propiedad("Identificador del supervisor", "table", "EsquemaTotalizadoSupervisores", "column", "nIdSupervisor"),
        propiedad("Bono de gestión comercial", "table", "EsquemaTotalizadoSupervisores", "column", "nBonoComercial"),
        *extra,
    ])


# Solo el encabezado de cada procedimiento, uno debajo del otro.
PROCEDIMIENTOS = """CREATE PROCEDURE Bonificacion.PA_EsquemaTotalizado_Sel_Ejecutivos
    @nPeriodo INT,
    @cCodAgencia VARCHAR(4)

CREATE PROCEDURE Bonificacion.PA_EsquemaTotalizado_Sel_Supervisores
    @nPeriodo INT,
    @cCodAgencia VARCHAR(4)
"""


def diccionario_procedimientos(*extra):
    filas = []
    for nombre in ("PA_EsquemaTotalizado_Sel_Ejecutivos", "PA_EsquemaTotalizado_Sel_Supervisores"):
        filas += [
            propiedad("Obtiene el totalizado de bonos", "procedure", nombre),
            propiedad("Periodo a consultar", "procedure", nombre, "parameter", "@nPeriodo"),
            propiedad("Código de la agencia", "procedure", nombre, "parameter", "@cCodAgencia"),
        ]
    return "\n".join(filas + list(extra))


class TestVariasTablas(unittest.TestCase):
    def test_misma_columna_en_dos_tablas_no_es_duplicado(self):
        self.assertEqual(verificar_diccionario_tablas(TABLAS, diccionario_tablas()), [])

    def test_duplicado_real_dice_su_tabla(self):
        extra = propiedad("Bono repetido", "table", "EsquemaTotalizadoSupervisores", "column", "nBonoComercial")
        hallazgos = verificar_diccionario_tablas(TABLAS, diccionario_tablas(extra))
        self.assertEqual([h.regla for h in hallazgos], ["DOCUMENTACION_DUPLICADA"])
        self.assertIn("EsquemaTotalizadoSupervisores", hallazgos[0].mensaje)

    def test_columna_sin_documentar_en_la_segunda_tabla(self):
        tablas = TABLAS.replace(
            "    nBonoComercial DECIMAL(18,2) NOT NULL,\n    CONSTRAINT PK_EsquemaTotalizadoSupervisores",
            "    nBonoComercial DECIMAL(18,2) NOT NULL,\n    nBonoFinal DECIMAL(18,2) NOT NULL,\n"
            "    CONSTRAINT PK_EsquemaTotalizadoSupervisores",
        )
        hallazgos = verificar_diccionario_tablas(tablas, diccionario_tablas())
        self.assertEqual([h.regla for h in hallazgos], ["COLUMNA_FALTANTE"])
        self.assertIn("EsquemaTotalizadoSupervisores", hallazgos[0].mensaje)
        self.assertEqual(hallazgos[0].linea, 10)
        faltante = unir_faltantes([diccionario_faltante_tabla(t, d) for t, d in diccionario_por_tabla(tablas, diccionario_tablas())])
        self.assertEqual(faltante["elementos"], ["nBonoFinal"])

    def test_nombre_de_tabla_mal_escrito_se_compara_con_su_tabla(self):
        dic = diccionario_tablas().replace(
            "N'EsquemaTotalizadoSupervisores', N'column', N'nIdSupervisor'",
            "N'EsquemaTotalizadoSupervisor', N'column', N'nIdSupervisor'",
        )
        hallazgos = verificar_diccionario_tablas(TABLAS, dic)
        self.assertEqual([h.regla for h in hallazgos], ["NOMBRE_TABLA_NO_COINCIDE"])
        self.assertIn("'EsquemaTotalizadoSupervisores'", hallazgos[0].mensaje)

    def test_create_y_alter_de_la_misma_tabla_son_un_solo_objeto(self):
        tablas = TABLAS + ("\nALTER TABLE Bonificacion.EsquemaTotalizadoEjecutivos ADD CONSTRAINT "
                           "DF_EsquemaTotalizadoEjecutivos_nBonoComercial DEFAULT 0 FOR nBonoComercial;\nGO")
        self.assertEqual(verificar_diccionario_tablas(tablas, diccionario_tablas()), [])

    def test_mismo_error_en_dos_tablas_se_lista_por_tabla(self):
        dic = "\n".join(
            sentencia + "\nGO" for sentencia in diccionario_tablas().split("\nGO") if "N'nId" not in sentencia
        )
        hallazgos = [h for h in verificar_diccionario_tablas(TABLAS, dic) if h.regla == "COLUMNA_FALTANTE"]
        self.assertEqual(len(hallazgos), 1)
        self.assertIn("EsquemaTotalizadoEjecutivos : nIdEjecutivo", hallazgos[0].mensaje)
        self.assertIn("EsquemaTotalizadoSupervisores : nIdSupervisor", hallazgos[0].mensaje)


class TestVariosProcedimientos(unittest.TestCase):
    def test_mismos_parametros_en_dos_procedimientos_no_son_duplicados(self):
        self.assertEqual(verificar_diccionario(PROCEDIMIENTOS, diccionario_procedimientos()), [])

    def test_duplicado_real_dice_su_procedimiento(self):
        extra = propiedad("Otra vez", "procedure", "PA_EsquemaTotalizado_Sel_Supervisores", "parameter", "@nPeriodo")
        hallazgos = verificar_diccionario(PROCEDIMIENTOS, diccionario_procedimientos(extra))
        self.assertEqual([h.regla for h in hallazgos], ["DOCUMENTACION_DUPLICADA"])
        self.assertIn("PA_EsquemaTotalizado_Sel_Supervisores", hallazgos[0].mensaje)

    def test_parametro_sin_documentar_del_segundo_encabezado(self):
        procedimientos = PROCEDIMIENTOS + "    , @nIdSupervisor INT\n"
        hallazgos = verificar_diccionario(procedimientos, diccionario_procedimientos())
        self.assertEqual([h.regla for h in hallazgos], ["PARAMETRO_FALTANTE"])
        self.assertIn("PA_EsquemaTotalizado_Sel_Supervisores", hallazgos[0].mensaje)
        faltante = unir_faltantes([
            diccionario_faltante_procedimiento(t, d)
            for t, d in diccionario_por_procedimiento(procedimientos, diccionario_procedimientos())
        ])
        self.assertEqual(faltante["elementos"], ["@nIdSupervisor"])


if __name__ == "__main__":
    unittest.main()
