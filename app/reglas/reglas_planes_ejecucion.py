"""Reglas registradas para el analisis de planes de ejecucion."""

from app.reglas.reglas_base import ReglaDiccionario


REGLAS_PLANES_EJECUCION = {
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