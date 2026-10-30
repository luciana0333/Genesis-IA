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


def arma_html(texto: str, limpio: str, posicion: int) -> bool:
    """La sentencia concatena etiquetas HTML o envía un correo con el cuerpo en HTML.

    Los límites (';') se buscan en el texto sin comentarios ni literales y las etiquetas en el original,
    porque están dentro de las comillas (ambos tienen el mismo largo).
    """
    inicio = limpio.rfind(";", 0, posicion) + 1
    fin = limpio.find(";", posicion)
    sentencia = texto[inicio:fin if fin >= 0 else len(texto)]
    return bool(_ETIQUETA_HTML.search(sentencia) or _CORREO_HTML.search(sentencia))
