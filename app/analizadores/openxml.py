"""«Uso de OPENXML en lugar de métodos nativos» (regla de Negocio; pedido y texto de la usuaria, 11 nov.).

EXEC sp_xml_preparedocument @nIdXml OUTPUT, @Xml carga el XML en la memoria del servidor (hasta 1/8 de la memoria de
SQL Server para estos documentos) y obliga a liberarlo después con sp_xml_removedocument. La forma moderna son los
métodos nativos del tipo XML: @Xml.nodes('/ruta') AS T(x) y x.value('(campo)[1]', 'INT'), que no reservan esa memoria.

Una sola observación con todas las variables del PA. Vive en su propio módulo para poder sumarlo a Reportes si se pide.
"""

import re
from typing import Callable, List, Optional, Tuple

# EXEC sp_xml_preparedocument @nIdXml OUTPUT, … — también EXECUTE, con el estado de retorno (EXEC @ret = …), con
# esquema (sys.) o corchetes y con el nombre del parámetro (@hdoc = @nIdXml OUTPUT).
_PREPARA = re.compile(
    r"\bEXEC(?:UTE)?\s+(?:@\w+\s*=\s*)?(?:\[?\w+\]?\s*\.\s*)*\[?sp_xml_preparedocument\]?\s+(?:@hdoc\s*=\s*)?(?P<variable>@\w+)",
    re.IGNORECASE,
)


def _enumerar(nombres: List[str]) -> str:
    """«@a», «@a y @b», «@a, @b y @c»."""
    if len(nombres) == 1:
        return nombres[0]
    return f"{', '.join(nombres[:-1])} y {nombres[-1]}"


def openxml_agrupado(limpio: str, linea_de: Callable[[int], int]) -> Optional[Tuple[int, str, List[int]]]:
    """(posición del primero, mensaje, líneas) o None. `limpio`: el SQL sin comentarios ni contenido de textos."""
    variables: List[str] = []
    posiciones: List[int] = []
    for match in _PREPARA.finditer(limpio):
        variable = match.group("variable")
        if variable.lower() not in (v.lower() for v in variables):
            variables.append(variable)
        posiciones.append(match.start())
    if not variables:
        return None
    # Texto de la usuaria (11 nov.); en singular cuando hay una sola variable.
    if len(variables) == 1:
        problema = (f"Se identificó el uso de sp_xml_preparedocument para procesar el XML correspondiente a "
                    f"{variables[0]}.")
    else:
        problema = (f"Se identificó el uso de sp_xml_preparedocument para procesar los XML correspondientes a "
                    f"{_enumerar(variables)}.")
    que_hacer = ("Se recomienda utilizar los métodos nativos .nodes() y .value() para leer y extraer los datos del "
                 "XML, evitando el uso de sp_xml_preparedocument, ya que reserva memoria del servidor y requiere "
                 "liberarla posteriormente.")
    lineas = sorted({linea_de(posicion) for posicion in posiciones})
    return posiciones[0], f"{problema} {que_hacer}", lineas
