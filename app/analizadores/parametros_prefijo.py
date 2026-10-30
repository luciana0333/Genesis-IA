# -*- coding: utf-8 -*-
"""Parámetros sin el prefijo de su tipo de dato (compartido por Reportes y Procedimientos de negocio).

Igual que las columnas, el nombre del parámetro empieza con la letra de su tipo:
c texto, n número, d fecha u hora, b bit (y j para un JSON en VARCHAR(MAX), x para XML).

    CREATE PROCEDURE dbo.PA_GDD_ProyectoLote_Sel_Cuotas
        @ProyectoId INT        <- debería ser @nProyectoId

Solo se revisa al crear el procedimiento: en un ALTER los parámetros ya existen y cambiarlos rompería
a quien lo llama.
"""

import re
from typing import List, Optional, Tuple

from app.analizadores.analizador_tablas import _PREFIJOS_TIPO

_CREATE = re.compile(
    r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROC(?:EDURE)?\s+(?:\[[^\]]+\]|[\w$#]+)(?:\s*\.\s*(?:\[[^\]]+\]|[\w$#]+)){0,2}",
    re.IGNORECASE,
)
_PARAMETRO = re.compile(r"\s*(@[A-Za-z_]\w*)\s+(?:AS\s+)?([A-Za-z_][\w.]*\s*(?:\([^)]*\))?)", re.IGNORECASE)
_DESCRIPCION = {"c": "texto", "n": "número", "d": "fecha u hora", "b": "bit", "x": "XML"}


def _parametros(limpio: str) -> List[Tuple[str, str, int]]:
    """[(nombre, tipo, posición)] de los parámetros del CREATE PROCEDURE (hasta el AS)."""
    encabezado = _CREATE.search(limpio)
    if not encabezado:
        return []
    fin = re.compile(r"\bAS\b", re.IGNORECASE).search(limpio, encabezado.end())
    zona = limpio[encabezado.end():fin.start() if fin else len(limpio)]
    resultado, profundidad, inicio = [], 0, 0
    partes = []
    for i, letra in enumerate(zona):
        if letra == "(":
            profundidad += 1
        elif letra == ")":
            profundidad -= 1
        elif letra == "," and profundidad <= 1:
            partes.append((zona[inicio:i], inicio))
            inicio = i + 1
    partes.append((zona[inicio:], inicio))
    for texto, desplazamiento in partes:
        texto_sin_parentesis = texto.lstrip(" \t\r\n(")
        quitado = len(texto) - len(texto_sin_parentesis)
        parametro = _PARAMETRO.match(texto_sin_parentesis)
        if parametro:
            resultado.append((parametro.group(1), parametro.group(2),
                              encabezado.end() + desplazamiento + quitado + parametro.start(1)))
    return resultado


def _prefijo_esperado(nombre: str, tipo: str) -> Optional[str]:
    """Letra que debe llevar el parámetro según su tipo; None si el tipo no tiene prefijo o el actual vale."""
    tipo_mayus = re.sub(r"\s+", "", tipo).upper()
    if re.match(r"XML\b", tipo_mayus):
        return "x"
    # Un JSON llega en (N)VARCHAR(MAX): «j» también es válido (@jData).
    if re.match(r"N?VARCHAR\(MAX\)", tipo_mayus) and nombre[1:2] == "j":
        return None
    for prefijo, patron in _PREFIJOS_TIPO:
        if re.match(patron, tipo_mayus, re.IGNORECASE):
            return prefijo
    return None  # tipos sin prefijo en el manual (UNIQUEIDENTIFIER, tipos de tabla, CURSOR…)


def parametros_sin_prefijo(limpio: str) -> List[Tuple[str, str, str, int]]:
    """[(parámetro, tipo, nombre sugerido, posición)] de los parámetros que no empiezan con su prefijo."""
    resultado = []
    for nombre, tipo, posicion in _parametros(limpio):
        prefijo = _prefijo_esperado(nombre, tipo)
        if prefijo is None or re.match(rf"@{prefijo}[A-Z0-9_]", nombre):
            continue
        # Si ya trae un prefijo en minúscula (@cMonto en un INT, @pnTipo), se reemplaza.
        resto = re.sub(r"^[a-z]{1,2}(?=[A-Z])", "", nombre[1:])
        sugerido = f"@{prefijo}{resto[:1].upper()}{resto[1:]}"
        resultado.append((nombre, re.sub(r"\s+", "", tipo).upper(), sugerido, posicion))
    return resultado


def mensaje_parametros_sin_prefijo(casos: List[Tuple[str, str, str, int]]) -> str:
    """Texto de la observación (uno o varios parámetros). Texto de la usuaria."""
    lista = "; ".join(f"{nombre} ({tipo}) → {sugerido}" for nombre, tipo, sugerido, _ in casos)
    prefijos = "c para texto, n para número, d para fecha u hora y b para bit"
    if len(casos) == 1:
        return (f"Se identificó un parámetro cuyo nombre no incluye el prefijo correspondiente a su tipo de dato: "
                f"{lista}. Renombrar el parámetro según lo indicado, utilizando el prefijo correspondiente a su tipo "
                f"de dato ({prefijos}), a fin de mantener una nomenclatura uniforme y facilitar su identificación.")
    return (f"Se identificaron {len(casos)} parámetros cuyos nombres no incluyen el prefijo correspondiente a su "
            f"tipo de dato: {lista}. Renombrar los parámetros según lo indicado, utilizando el prefijo "
            f"correspondiente a su tipo de dato ({prefijos}), a fin de mantener una nomenclatura uniforme y "
            f"facilitar su identificación.")


# Variables (DECLARE @x ...): misma regla que los parámetros, también solo al crear el procedimiento.
_DECLARE = re.compile(r"\bDECLARE\b", re.IGNORECASE)
# Lo que cierra la lista del DECLARE fuera de paréntesis (aunque el código no use «;»).
_FIN_DECLARE = re.compile(
    r"\(|\)|;|,|\b(?:CASE|END|SELECT|SET|INSERT|UPDATE|DELETE|MERGE|DECLARE|IF|ELSE|WHILE|BEGIN|RETURN|EXEC|"
    r"EXECUTE|PRINT|THROW|RAISERROR|WITH|TRUNCATE|DROP|CREATE|ALTER|OPEN|FETCH|CLOSE|DEALLOCATE|GO)\b",
    re.IGNORECASE,
)


def _variables(limpio: str) -> List[Tuple[str, str, int]]:
    """[(nombre, tipo, posición)] de las variables de cada DECLARE (DECLARE @a INT = 0, @b VARCHAR(10))."""
    resultado = []
    for declare in _DECLARE.finditer(limpio):
        posicion = declare.end()
        while True:
            variable = _PARAMETRO.match(limpio, posicion)
            if not variable:
                break
            resultado.append((variable.group(1), variable.group(2), variable.start(1)))
            # Se avanza hasta la coma que separa la siguiente variable (fuera de paréntesis y de un CASE).
            profundidad, casos, siguiente = 0, 0, None
            for token in _FIN_DECLARE.finditer(limpio, variable.end()):
                palabra = token.group(0).upper()
                if palabra == "(":
                    profundidad += 1
                elif palabra == ")":
                    profundidad -= 1
                elif profundidad > 0:
                    continue
                elif palabra == "CASE":
                    casos += 1
                elif palabra in ("END", "ELSE") and casos:
                    casos -= palabra == "END"
                elif palabra == ",":
                    siguiente = token.end()
                    break
                else:
                    break
            if siguiente is None:
                break
            posicion = siguiente
    return resultado


def _sugerido(nombre: str, prefijo: str) -> str:
    # Si ya trae un prefijo en minúscula (@cMonto en un INT, @pnTipo), se reemplaza.
    resto = re.sub(r"^[a-z]{1,2}(?=[A-Z])", "", nombre[1:])
    return f"@{prefijo}{resto[:1].upper()}{resto[1:]}"


def variables_sin_prefijo(limpio: str) -> List[Tuple[str, str, str, int]]:
    """[(variable, tipo, nombre sugerido, posición)]; solo si el script crea el procedimiento."""
    if not _CREATE.search(limpio):
        return []
    resultado = []
    for nombre, tipo, posicion in _variables(limpio):
        prefijo = _prefijo_esperado(nombre, tipo)
        if prefijo is None or re.match(rf"@{prefijo}[A-Z0-9_]", nombre):
            continue
        resultado.append((nombre, re.sub(r"\s+", "", tipo).upper(), _sugerido(nombre, prefijo), posicion))
    return resultado


def mensaje_variables_sin_prefijo(casos: List[Tuple[str, str, str, int]]) -> str:
    """Texto de la observación (una o varias variables), igual al de los parámetros e incluye la x del XML."""
    lista = "; ".join(f"{nombre} ({tipo}) → {sugerido}" for nombre, tipo, sugerido, _ in casos)
    prefijos = "c para texto, n para número, d para fecha u hora, b para bit y x para XML"
    if len(casos) == 1:
        return (f"Se identificó una variable cuyo nombre no incluye el prefijo correspondiente a su tipo de dato: "
                f"{lista}. Renombrar la variable según lo indicado, utilizando el prefijo correspondiente a su tipo "
                f"de dato ({prefijos}), a fin de mantener una nomenclatura uniforme y facilitar su identificación.")
    return (f"Se identificaron {len(casos)} variables cuyos nombres no incluyen el prefijo correspondiente a su "
            f"tipo de dato: {lista}. Renombrar las variables según lo indicado, utilizando el prefijo "
            f"correspondiente a su tipo de dato ({prefijos}), a fin de mantener una nomenclatura uniforme y "
            f"facilitar su identificación.")
