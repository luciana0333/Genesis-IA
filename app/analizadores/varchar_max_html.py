"""VARCHAR(MAX) para armar un HTML (cuerpo de un correo, una tabla): puede ser largo, igual que un JSON o un XML.

Lo comparten Reportes y Negocio.
"""

from __future__ import annotations

import re

# Un texto con etiquetas HTML: '<table>', '</td>', '<br/>', '<tr style="...">'.
_ETIQUETA_HTML = re.compile(
    r"'[^']*<\s*/?\s*(?:html|head|body|table|thead|tbody|tfoot|tr|td|th|caption|br|hr|p|div|span|b|i|u|strong|"
    r"em|font|style|h[1-6]|ul|ol|li|a|img|center)\b[^']*'",
    re.IGNORECASE,
)
# sp_send_dbmail con el cuerpo en HTML.
_CORREO_HTML = re.compile(r"@body_format\s*=\s*N?'\s*HTML\s*'", re.IGNORECASE)


def nombre_de_html(nombre: str) -> bool:
    """@TablaHTML, @cHtmlCuerpo: el nombre dice que guarda un HTML."""
    return bool(re.search(r"html", nombre, re.IGNORECASE))


def prefijo_json(nombre: str) -> bool:
    """@jData, @jDetalle: la «j» es el prefijo de un JSON (igual que en la regla de prefijos de parámetros)."""
    return bool(re.match(r"@?j[A-Z0-9_]", nombre))


# Inicio de una sentencia que nunca va dentro de una consulta: sirve de límite cuando el código no usa ';'.
# (END solo con TRY/CATCH: el END de un CASE va dentro de la consulta).
_INICIO_SENTENCIA = re.compile(
    r"(?<![\w@#.])(?:(?:DECLARE|BEGIN|IF|ELSE|WHILE|THROW|RETURN|PRINT|EXEC(?:UTE)?|GO|END\s+(?:TRY|CATCH))(?![\w@#])|"
    r"SET\s+(?=@|NOCOUNT\b|XACT_ABORT\b|ANSI_\w+\b|DATEFORMAT\b|LANGUAGE\b|TRANSACTION\b))",
    re.IGNORECASE,
)
_PARENTESIS_O_DML = re.compile(r"[()]|(?<![\w@#.])(?:SELECT|INSERT|UPDATE|DELETE|MERGE)(?![\w@#])", re.IGNORECASE)


def limites_sentencia(limpio: str, posicion: int) -> tuple:
    """(inicio, fin) de la sentencia que contiene la posición.

    Además de ';', corta donde empieza otra sentencia (DECLARE, SET @x, EXEC, IF, THROW…): en un procedimiento
    largo sin ';' la «sentencia» era un bloque de miles de líneas y un .value( lejano justificaba cualquier
    VARCHAR(MAX) (usuaria, 21 nov.: @cCodError, @cError y @psCalif en FluGenSol_InsPropuesta_SP).
    """
    inicio = limpio.rfind(";", 0, posicion) + 1
    for match in _INICIO_SENTENCIA.finditer(limpio, inicio, posicion):
        inicio = match.start()
    fin = limpio.find(";", posicion)
    fin = fin if fin >= 0 else len(limpio)
    siguiente = _INICIO_SENTENCIA.search(limpio, posicion + 1, fin)
    fin = siguiente.start() if siguiente else fin
    # Tras DECLARE, SET @x, EXEC, IF…, un SELECT/INSERT/UPDATE/DELETE fuera de paréntesis ya es otra sentencia
    # («DECLARE @c VARCHAR(MAX) SELECT @d = T.x.value(…)»). En «SET @c = (SELECT …)» va entre paréntesis: es la misma.
    if _INICIO_SENTENCIA.match(limpio, inicio):
        profundidad = 0
        for match in _PARENTESIS_O_DML.finditer(limpio, inicio, fin):
            simbolo = match.group(0)
            if simbolo == "(":
                profundidad += 1
            elif simbolo == ")":
                profundidad = max(profundidad - 1, 0)
            elif profundidad == 0:
                if match.start() <= posicion:
                    inicio = match.start()  # la posición está en esa consulta: desde ahí hasta el final
                else:
                    fin = match.start()
                break
    return inicio, fin


def sentencia_de(limpio: str, posicion: int) -> str:
    inicio, fin = limites_sentencia(limpio, posicion)
    return limpio[inicio:fin]


def arma_html(texto: str, limpio: str, posicion: int) -> bool:
    """La sentencia concatena etiquetas HTML o envía un correo con el cuerpo en HTML.

    Los límites se buscan en el texto sin comentarios ni literales y las etiquetas en el original,
    porque están dentro de las comillas (ambos tienen el mismo largo).
    """
    inicio, fin = limites_sentencia(limpio, posicion)
    sentencia = texto[inicio:fin]
    return bool(_ETIQUETA_HTML.search(sentencia) or _CORREO_HTML.search(sentencia))


def _llamada_que_contiene(limpio: str, posicion: int):
    """(función, contenido) del CAST( o CONVERT( que encierra la posición; None si no está dentro de uno."""
    nivel = 0
    for i in range(posicion - 1, -1, -1):
        if limpio[i] == ")":
            nivel += 1
        elif limpio[i] == "(":
            if nivel:
                nivel -= 1
                continue
            funcion = re.search(r"\b(CAST|CONVERT|TRY_CAST|TRY_CONVERT)\s*$", limpio[:i], re.IGNORECASE)
            if not funcion:
                return None
            nivel_fin = 0
            for j in range(i + 1, len(limpio)):
                if limpio[j] == "(":
                    nivel_fin += 1
                elif limpio[j] == ")":
                    if not nivel_fin:
                        return funcion.group(1).upper(), limpio[i + 1:j]
                    nivel_fin -= 1
            return funcion.group(1).upper(), limpio[i + 1:]
    return None


def convierte_xml_json_html(limpio: str, posicion: int) -> bool:
    """CONVERT(VARCHAR(MAX), @cXml) o CAST(@xDatos AS VARCHAR(MAX)): pasa a texto un XML, JSON o HTML.

    Se reconoce por la variable o el parámetro que se convierte: declarado como XML, o con xml/json/html
    en el nombre (igual que la variable que guarda el resultado).
    """
    llamada = _llamada_que_contiene(limpio, posicion)
    if not llamada:
        return False
    for variable in re.findall(r"@\w+", llamada[1]):
        if re.search(r"xml|json|html", variable, re.IGNORECASE):
            return True
        if re.search(rf"{re.escape(variable)}\s+(?:AS\s+)?XML\b", limpio, re.IGNORECASE):
            return True
    return False
