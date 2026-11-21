"""Reglas registradas para el analisis de planes de ejecucion."""

from app.reglas.reglas_base import ReglaDiccionario


REGLAS_PLANES_EJECUCION = {
    # --- Área Negocio (reglas definidas por la usuaria; usa además conversión y lectura residual) ---
    "TABLE_SCAN_DETECTADO": ReglaDiccionario(
        codigo="TABLE_SCAN_DETECTADO",
        nombre="Table Scan detectado",
        severidad="alto",
        descripcion="Un procedimiento de negocio recorre una tabla física completa (Table Scan). No cuenta tablas temporales ni variables de tabla.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "SPILL_TEMPDB_DETECTADO": ReglaDiccionario(
        codigo="SPILL_TEMPDB_DETECTADO",
        nombre="Spill a TempDB",
        severidad="alto",
        descripcion="Un operador trae la alerta SpillToTempDb: la memoria asignada no alcanzó y escribió en TempDB.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "MEMORIA_SOBREESTIMADA": ReglaDiccionario(
        codigo="MEMORIA_SOBREESTIMADA",
        nombre="Sobreestimación de memoria",
        severidad="medio",
        descripcion="Desde 80 MB reservados y usando menos del 50 % de lo reservado, con o sin la alerta Excessive Grant.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    # --- Área Reportes (reglas definidas por la usuaria) -----------------
    "TIEMPO_EJECUCION_SUPERADO": ReglaDiccionario(
        codigo="TIEMPO_EJECUCION_SUPERADO",
        nombre="Tiempo de ejecución superado",
        severidad="alto",
        descripcion="La suma de la duración de las consultas del plan supera el límite de tiempo del área; se señala el bloque más lento.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "LECTURA_RESIDUAL_ELEVADA": ReglaDiccionario(
        codigo="LECTURA_RESIDUAL_ELEVADA",
        nombre="Lectura residual elevada",
        severidad="alto",
        descripcion="Un Scan lee más de 1 000 000 de filas (ActualRowsRead) y devuelve menos: recorre la tabla casi completa. Un Seek no se marca.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "CONVERSION_IMPLICITA_DETECTADA": ReglaDiccionario(
        codigo="CONVERSION_IMPLICITA_DETECTADA",
        nombre="Conversión implícita",
        severidad="alto",
        descripcion="Un operador tiene la alerta Convert Issue con CONVERT_IMPLICIT: SQL Server convierte el dato fila por fila.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "CONVERSION_TEXTO_A_NUMERO": ReglaDiccionario(
        codigo="CONVERSION_TEXTO_A_NUMERO",
        nombre="Conversión implícita",
        severidad="medio",
        descripcion="Riesgo identificado por Genesis (sin alerta de SQL Server): SUBSTRING, LEFT o RIGHT convertido "
                    "implícitamente a número; si el dato no es numérico, la consulta genera un error de conversión.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "COLUMNA_TEXTO_CONVERTIDA": ReglaDiccionario(
        codigo="COLUMNA_TEXTO_CONVERTIDA",
        nombre="Conversión implícita",
        severidad="medio",
        descripcion="Riesgo identificado por Genesis (sin alerta de SQL Server): una columna de texto (cFecha) que el "
                    "plan convierte implícitamente a fecha o número; si algún valor no tiene el formato esperado, la "
                    "consulta genera un error de conversión.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "CONVERSION_COLUMNA_EN_FILTRO": ReglaDiccionario(
        codigo="CONVERSION_COLUMNA_EN_FILTRO",
        nombre="Conversión implícita",
        severidad="bajo",
        descripcion="Riesgo identificado por Genesis (sin alerta de SQL Server): una columna (BIT, número o fecha) que "
                    "el plan convierte implícitamente dentro de un filtro o un JOIN, lo que obliga a recorrer la tabla. "
                    "Solo se marca si el recorrido lee 10 000 filas o más y devuelve como mucho el 10 %; medio desde "
                    "un millón de filas leídas.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "CONVERSION_COLUMNA_A_DESTINO": ReglaDiccionario(
        codigo="CONVERSION_COLUMNA_A_DESTINO",
        nombre="Conversión implícita",
        severidad="bajo",
        descripcion="Riesgo identificado por Genesis (sin alerta de SQL Server): una columna que el plan convierte "
                    "implícitamente al guardarse (INSERT, UPDATE) o unirse (UNION) con un destino de otro tipo de dato "
                    "(Compute Scalar). No frena la consulta, pero los tipos no son iguales.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "CONVERSION_IMPLICITA": ReglaDiccionario(
        codigo="CONVERSION_IMPLICITA",
        nombre="Conversion implicita",
        severidad="alto",
        descripcion="Una conversion implicita puede impedir el uso eficiente de indices.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "SPILL_TEMPDB": ReglaDiccionario(
        codigo="SPILL_TEMPDB",
        nombre="Spill hacia TempDB",
        severidad="alto",
        descripcion="El operador derrama datos hacia TempDB y requiere revisar memoria, cardinalidad o indices.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "TABLE_SCAN": ReglaDiccionario(
        codigo="TABLE_SCAN",
        nombre="Table Scan",
        severidad="medio",
        descripcion="El plan realiza una lectura completa de una tabla.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "LECTURAS_LOGICAS_ELEVADAS": ReglaDiccionario(
        codigo="LECTURAS_LOGICAS_ELEVADAS",
        nombre="Lecturas logicas elevadas",
        severidad="alto",
        descripcion="Las lecturas logicas del operador superan el umbral configurado.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "SOBREESTIMACION_FILAS": ReglaDiccionario(
        codigo="SOBREESTIMACION_FILAS",
        nombre="Desviacion de cardinalidad",
        severidad="alto",
        descripcion="Las filas reales se desviaron significativamente de las filas estimadas.",
        alcance="plan_ejecucion",
        activo=True,
    ),
    "MEMORIA_CONCEDIDA_SOBREDIMENSIONADA": ReglaDiccionario(
        codigo="MEMORIA_CONCEDIDA_SOBREDIMENSIONADA",
        nombre="Memoria concedida sobredimensionada",
        severidad="medio",
        descripcion="La memoria concedida supera ampliamente la memoria maxima utilizada.",
        alcance="plan_ejecucion",
        activo=True,
    ),
}