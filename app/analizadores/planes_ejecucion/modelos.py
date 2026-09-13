"""Modelos internos para normalizar operadores de un plan SQL Server."""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class OperadorPlan:
    nodo_id: str
    operacion_fisica: str
    operacion_logica: str
    estimacion_filas: Optional[float]
    filas_reales: Optional[float]
    filas_leidas: Optional[float]
    lecturas_logicas: Optional[float]
    costo_subarbol: Optional[float]
    objeto: str
    profundidad: int
    tiene_spill: bool
    tiene_conversion_implicita: bool


@dataclass(frozen=True)
class MemoriaPlan:
    memoria_solicitada_kb: Optional[float]
    memoria_concedida_kb: Optional[float]
    memoria_maxima_utilizada_kb: Optional[float]
