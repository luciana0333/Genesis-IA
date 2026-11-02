# -*- coding: utf-8 -*-
"""LEFT que puede ser LIKE (compartido por Reportes y Procedimientos de negocio).

    WHERE LEFT(cCtaCod, 5) = '10901'   →   WHERE cCtaCod LIKE '10901%'

Aplicar LEFT (o SUBSTRING desde 1) a la columna impide usar sus índices; LIKE con el comodín solo al final
sí los aprovecha (Index Seek). Solo se recomienda cuando LIKE devuelve exactamente las mismas filas.
"""

import re
from typing import List, Optional, Tuple

# LEFT(col, n) o SUBSTRING(col, 1, n): los primeros n caracteres de una columna.
_COLUMNA_LIKE = r"(?:[\w#]+\.)?(?:\[[^\]]+\]|[\w#]+)"
_INICIO_COLUMNA = (
    rf"(?P<funcion>LEFT\s*\(\s*(?P<col>{_COLUMNA_LIKE})\s*,\s*(?P<n>\d+)\s*\)"
    rf"|SUBSTRING\s*\(\s*(?P<col2>{_COLUMNA_LIKE})\s*,\s*1\s*,\s*(?P<n2>\d+)\s*\))"
)
_VALOR_LIKE = r"N?'(?:[^']|'')*'|@\w+|\d+"
# El valor termina ahí: no sigue un decimal, una letra ni una operación ('ab' + 'c', 10.5, @p + 1).
_FIN_VALOR = r"(?![\w.])(?!\s*[+\-*/%|&^])"
# Palabras que dicen dónde está la comparación: en un filtro (sí) o en el SELECT, SET, CASE, IF... (no).
_CLAUSULA_LIKE = re.compile(
    r"\(|\)|\b(WHERE|ON|HAVING|SELECT|SET|CASE|WHEN|THEN|ELSE|IF|WHILE|RETURN|VALUES|PRINT)\b", re.IGNORECASE
)
_TIPOS_TEXTO = r"N?(?:VAR)?CHAR|N?TEXT"
_TIPOS_SQL = (
    r"N?(?:VAR)?CHAR|N?TEXT|BIGINT|INT|SMALLINT|TINYINT|BIT|DECIMAL|NUMERIC|SMALLMONEY|MONEY|FLOAT|REAL|"
    r"DATETIME2|DATETIMEOFFSET|SMALLDATETIME|DATETIME|DATE|TIME|UNIQUEIDENTIFIER|XML|VARBINARY|BINARY|SYSNAME"
)


def _en_filtro(limpio: str, posicion: int) -> bool:
    """
    La comparación está en un WHERE, ON o HAVING (donde un índice puede servir), y no en el SELECT, en un
    SET, en un CASE, en un IF, ni negada con NOT (NOT LIKE tampoco usa el índice).
    """
    profundidad = 0
    for marca in reversed(list(_CLAUSULA_LIKE.finditer(limpio, 0, posicion))):
        simbolo = marca.group(0).upper()
        if simbolo == ")":
            profundidad += 1
        elif simbolo == "(":
            profundidad = max(profundidad - 1, 0)
        elif profundidad == 0:
            return simbolo in ("WHERE", "ON", "HAVING")
    return False


def _negado(limpio: str, posicion: int) -> bool:
    return bool(re.search(r"\bNOT\s*\(?\s*$", limpio[:posicion], re.IGNORECASE))


def _tipo_declarado(limpio: str, nombre: str) -> Optional[re.Match]:
    """
    Tipo con que se declara en el script una variable o parámetro (@p VARCHAR(5)) o una columna de una
    temporal o variable tabla (CREATE TABLE #T (cCodigo CHAR(5), ...)); None si no está declarada.
    """
    if nombre.startswith("@"):
        antes = rf"(?<![\w@#]){re.escape(nombre)}"
    else:
        antes = rf"[(,]\s*\[?{re.escape(nombre.split('.')[-1].strip('[]'))}\]?"
    return re.search(rf"{antes}\s+(?:AS\s+)?({_TIPOS_SQL})\b\s*(?:\(\s*(\d+|MAX)\b)?", limpio, re.IGNORECASE)


def _texto_para_like(valor: str) -> str:
    """Los comodines del texto (%, _, [) se escriben entre corchetes para que LIKE los tome tal cual."""
    return re.sub(r"([%_\[])", r"[\1]", valor)


def _like_equivalente(limpio: str, col: str, n: int, valor: str) -> Optional[str]:
    """
    `col LIKE ...` que devuelve exactamente lo mismo que LEFT(col, n) = valor, o None si no lo hay:
    - un texto debe tener n caracteres y no terminar en espacio (con = se ignoran los espacios del final;
      con LIKE no). Con otra longitud la condición no es equivalente (o nunca se cumple);
    - un número debe tener n dígitos;
    - una variable debe estar declarada como texto de n caracteres (si no, su valor puede ser más corto o
      más largo).
    """
    if valor.startswith("@"):
        tipo = _tipo_declarado(limpio, valor)
        if not tipo or not re.fullmatch(_TIPOS_TEXTO, tipo.group(1), re.IGNORECASE) or tipo.group(2) != str(n):
            return None
        return f"{col} LIKE {valor} + '%'"
    if valor[0].isdigit():
        return f"{col} LIKE '{valor}%'" if len(valor) == n else None
    prefijo = "N" if valor[0] in "Nn" else ""
    contenido = valor[len(prefijo) + 1:-1].replace("''", "'")
    if len(contenido) != n or contenido.endswith(" "):
        return None
    return f"{col} LIKE {prefijo}'{_texto_para_like(contenido).replace(chr(39), chr(39) * 2)}%'"


def _columna_de_texto(limpio: str, col: str) -> bool:
    """La columna no está declarada en el script con un tipo que no es texto (int, date...): LIKE no aplica."""
    if col.startswith("@"):
        return False  # LEFT sobre una variable: no hay índice que perder
    tipo = _tipo_declarado(limpio, col)
    if not tipo:
        return True  # tabla real: su tipo no está en el script
    return bool(re.fullmatch(_TIPOS_TEXTO, tipo.group(1), re.IGNORECASE))


def left_reemplazable_por_like(limpio: str) -> List[Tuple[int, str]]:
    """
    LEFT(col, n) = 'abc' (o SUBSTRING(col, 1, n)) en un filtro: con LIKE 'abc%' se aprovechan los índices.
    Solo se marca cuando LIKE devuelve exactamente lo mismo. Devuelve (posición, mensaje) de cada caso.
    `limpio`: el script sin comentarios, pero con el contenido de los textos.
    """
    encontrados = []
    patrones = (
        rf"\b{_INICIO_COLUMNA}\s*=\s*(?P<val>{_VALOR_LIKE}){_FIN_VALOR}",
        rf"(?<![\w@#.\]'+\-*/%])(?P<val>{_VALOR_LIKE})\s*=\s*{_INICIO_COLUMNA}",
        rf"\b{_INICIO_COLUMNA}\s+IN\s*\((?P<lista>\s*(?:{_VALOR_LIKE})(?:\s*,\s*(?:{_VALOR_LIKE}))*\s*)\)",
    )
    for patron in patrones:
        for match in re.finditer(patron, limpio, re.IGNORECASE):
            col = match.group("col") or match.group("col2")
            n = int(match.group("n") or match.group("n2"))
            if not _en_filtro(limpio, match.start()) or _negado(limpio, match.start()):
                continue
            if not _columna_de_texto(limpio, col):
                continue
            valores = (re.findall(_VALOR_LIKE, match.group("lista")) if match.groupdict().get("lista")
                       else [match.group("val")])
            likes = [_like_equivalente(limpio, col, n, valor) for valor in valores]
            if not all(likes):
                continue
            funcion = re.sub(r"\s+", " ", match.group("funcion"))
            condicion = re.sub(r"\s+", " ", match.group(0).strip())
            ejemplo = likes[0] if len(likes) == 1 else "(" + " OR ".join(likes) + ")"
            nombre = "SUBSTRING" if funcion.upper().startswith("SUBSTRING") else "LEFT"
            encontrados.append((
                match.start(),
                f"Se encontró {condicion} en una condición. Emplear LIKE, ya que "
                f"aplicar {nombre} a la columna impide usar sus índices y LIKE con el comodín al final sí los "
                f"aprovecha (ej.: {ejemplo}).",
            ))
    return encontrados
