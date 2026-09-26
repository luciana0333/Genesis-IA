# -*- coding: utf-8 -*-
"""
hallazgo.py
------------
Define la estructura única de un "hallazgo" (observación) que usan
TODOS los analizadores del proyecto (diccionario, reglas estáticas,
plan de ejecución).

Al tener una sola definición compartida, cualquier módulo nuevo que
agreguemos ya sabe automáticamente cómo reportar sus resultados, y la
interfaz visual solo necesita entender ESTA forma, sin importar de
qué analizador vino el hallazgo.
"""

from dataclasses import dataclass
from enum import Enum


class Severidad(str, Enum):
    """
    Los niveles de severidad posibles para un hallazgo.

    Hereda de (str, Enum) para que se pueda comparar y mostrar
    directamente como texto en la interfaz y en el informe final,
    sin necesidad de convertir el valor manualmente cada vez.
    """
    CRITICO = "critico"
    ALTO = "alto"
    MEDIO = "medio"
    BAJO = "bajo"


class OrigenAnalisis(str, Enum):
    """
    De qué módulo vino el hallazgo. Esto nos sirve más adelante para
    agrupar el informe final por sección (Diccionario, Código,
    Plan de Ejecución).
    """
    DICCIONARIO = "diccionario"
    REGLAS_ESTATICAS = "reglas_estaticas"
    PLAN_EJECUCION = "plan_ejecucion"


@dataclass
class Hallazgo:
    """
    Representa UNA sola observación detectada durante el análisis.

    Atributos:
        linea: número de línea en el código donde ocurre (1 si no aplica,
               como en validaciones a nivel de todo el procedimiento).
        origen: de qué módulo vino (ver OrigenAnalisis).
        severidad: qué tan grave es (ver Severidad).
        regla: identificador corto de la regla (ej. "USO_CURSOR"),
               útil para filtrar o contar hallazgos por tipo.
        mensaje: el texto ya redactado, en el tono de correo que se usa
                 en las observaciones a los desarrolladores.
    """
    linea: int
    origen: OrigenAnalisis
    severidad: Severidad
    regla: str
    mensaje: str

    def __str__(self) -> str:
        """
        Representación en texto plano, para cuando queramos imprimir
        el hallazgo en consola o en el informe final sin formato.
        """
        return f"[L{self.linea}] ({self.severidad.value.upper()}) {self.regla}: {self.mensaje}"