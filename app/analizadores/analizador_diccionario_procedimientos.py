# -*- coding: utf-8 -*-
"""
diccionario.py
----------------
Analizador especializado en el diccionario de datos
(sp_addextendedproperty) de un procedimiento almacenado.

Recibe DOS textos por separado, tal como se manejan en la revision real:
  - texto_procedimiento: el CREATE/ALTER PROCEDURE con sus parametros
  - texto_diccionario: el script de sp_addextendedproperty que lo documenta

Compara la "realidad" (procedimiento) contra la "documentacion"
(diccionario) y reporta discrepancias.
"""

import re
from typing import List, Set, Tuple, Dict, Optional

from app.analizadores.propiedades_extendidas import como_llamadas_crudas, leer_propiedades_extendidas
from app.modelos.hallazgo import Hallazgo, Severidad, OrigenAnalisis


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "realidad" (el procedimiento)
# ---------------------------------------------------------------------------

def extraer_parametros(texto_procedimiento: str) -> Set[str]:
    """Extrae los parametros declarados en CREATE/ALTER PROCEDURE."""
    patron = re.compile(
        r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\(?(.*?)\)?\s*AS\b",
        re.IGNORECASE | re.DOTALL
    )
    coincidencia = patron.search(texto_procedimiento)
    if not coincidencia:
        coincidencia = re.search(
            r"(?:CREATE|ALTER)\s+PROCEDURE\s+[\w\.]+\s*\((.*?)\)\s*(?:;|\Z)",
            texto_procedimiento,
            re.IGNORECASE | re.DOTALL,
        )
    if not coincidencia:
        return set()
    bloque_parametros = coincidencia.group(1)
    return set(re.findall(r"@\w+", bloque_parametros))


def extraer_tipo_sentencia(texto_procedimiento: str) -> str:
    """Determina si el procedimiento es un CREATE o un ALTER."""
    if re.search(r"\bALTER\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "ALTER"
    if re.search(r"\bCREATE\s+PROCEDURE\b", texto_procedimiento, re.IGNORECASE):
        return "CREATE"
    return "DESCONOCIDO"


def extraer_esquema_y_nombre(texto_procedimiento: str) -> Tuple[Optional[str], Optional[str]]:
    """Devuelve (esquema, nombre) del procedimiento, o (None, None)."""
    m = re.search(
        r"(?:CREATE|ALTER)\s+PROCEDURE\s+([\w]+)\.([\w]+)",
        texto_procedimiento, re.IGNORECASE
    )
    if m:
        return m.group(1), m.group(2)
    return None, None


# ---------------------------------------------------------------------------
# EXTRACCION - leer la "documentacion" (el script del diccionario)
# ---------------------------------------------------------------------------

def extraer_llamadas_extendedproperty(texto_diccionario: str) -> List[Tuple[int, Dict[str, str]]]:
    """
    Devuelve una lista de (posicion_en_texto, argumentos) por cada
    llamada a sp_addextendedproperty / sp_updateextendedproperty,
    leidas del SCRIPT DEL DICCIONARIO (no del procedimiento).
    """
    # El lector compartido reconoce cada sentencia aunque no haya GO ni ";",
    # y respeta cadenas y comentarios.
    return como_llamadas_crudas(leer_propiedades_extendidas(texto_diccionario))


def _limpiar_valor(valor: str) -> str:
    """Quita comillas y el prefijo N de un valor tipo N'texto' -> texto."""
    return valor.replace("N'", "").replace("'", "").strip()


def _es_descripcion_procedimiento_valida(args: Dict[str, str]) -> bool:
    """Indica si la llamada documenta la descripcion del procedimiento,
    excluyendo las entradas de PARAMETER.
    """
    level1type = args.get("level1type", "").upper()
    level2type = args.get("level2type", "").upper()
    if "PROCEDURE" not in level1type:
        return False
    if "PARAMETER" in level2type:
        return False
    return _limpiar_valor(args.get("value", "")) != ""


def _numero_linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


# ---------------------------------------------------------------------------
# VALIDACIONES INDIVIDUALES
# ---------------------------------------------------------------------------

def _validar_esquema(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema_real: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level0name del diccionario debe coincidir con el esquema real
    del procedimiento (ej. Dbo, CCE, RRHH)."""
    hallazgos = []
    for pos, args in llamadas:
        if "level0name" in args:
            valor = _limpiar_valor(args["level0name"])
            if valor and valor.lower() != esquema_real.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="ESQUEMA_NO_COINCIDE",
                    mensaje=f"El esquema documentado (@level0name='{valor}') no "
                            f"coincide con el esquema real del procedimiento "
                            f"('{esquema_real}')."
                ))
    return hallazgos


def _validar_descripciones_vacias(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    """Un parametro puede estar 'documentado' pero con @value vacio ('') -
    eso no cuenta como documentacion real."""
    hallazgos = []
    for pos, args in llamadas:
        es_parametro = "PARAMETER" in args.get("level2type", "").upper()
        if es_parametro and "value" in args:
            valor_desc = _limpiar_valor(args["value"])
            nombre_param = _limpiar_valor(args.get("level2name", "?"))
            if valor_desc == "":
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.MEDIO,
                    regla="DESCRIPCION_VACIA",
                    mensaje=f"El parametro {nombre_param} tiene una llamada a "
                            f"sp_addextendedproperty, pero su descripcion (@value) "
                            f"esta vacia."
                ))
    return hallazgos


def _validar_parametros_faltantes(
    parametros_reales: Set[str],
    llamadas: List[Tuple[int, Dict[str, str]]],
    tipo_sentencia: str,
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Compara parametros reales vs documentados. El mensaje cambia segun
    si es CREATE o ALTER, y segun si el diccionario tiene o no llamadas.
    """
    hallazgos = []

    parametros_documentados = set()
    for _, args in llamadas:
        if "level2name" in args and "PARAMETER" in args.get("level2type", "").upper():
            parametros_documentados.add(_limpiar_valor(args["level2name"]))

    faltantes = parametros_reales - parametros_documentados

    for p in sorted(faltantes):
        if tipo_sentencia == "ALTER" and llamadas:
            # Hay documentacion previa (llamadas existen), pero le falta
            # este parametro en particular.
            mensaje = (
                f"Este procedimiento ya existia (tiene documentacion previa "
                f"en el diccionario), sin embargo el parametro {p} no se "
                f"encuentra declarado en el diccionario. Verifique."
            )
            severidad = Severidad.MEDIO
        else:
            mensaje = (
                f"El parametro {p} (declarado en el procedimiento) no se "
                f"encuentra declarado en el diccionario."
            )
            severidad = Severidad.MEDIO

        hallazgos.append(Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=severidad,
            regla="PARAMETRO_FALTANTE",
            mensaje=mensaje
        ))

    return hallazgos


def _validar_alter_sin_diccionario(
    tipo_sentencia: str,
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """
    Caso especial: es un ALTER y el script de diccionario esta vacio
    (no se proporciono, o no tiene ninguna llamada a sp_addextendedproperty).
    No asumimos error - pedimos validacion manual.
    """
    if tipo_sentencia == "ALTER" and not llamadas:
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.BAJO,
            regla="ALTER_SIN_DICCIONARIO",
            mensaje=(
                f"Este procedimiento ({esquema}.{nombre_proc}) es un ALTER. "
                f"No se encontro script de diccionario o no contiene llamadas "
                f"a sp_addextendedproperty. Verifique si sus parametros ya "
                f"estan declarados previamente."
            )
        )]
    return []


def _validar_nombre_procedimiento(
    llamadas: List[Tuple[int, Dict[str, str]]],
    nombre_proc: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """El @level1name debe coincidir exactamente con el nombre real."""
    hallazgos = []
    for pos, args in llamadas:
        if "level1name" in args and "PROCEDURE" in args.get("level1type", "").upper():
            valor = _limpiar_valor(args["level1name"])
            if valor.lower() != nombre_proc.lower():
                hallazgos.append(Hallazgo(
                    linea=_numero_linea(texto_diccionario, pos),
                    origen=OrigenAnalisis.DICCIONARIO,
                    severidad=Severidad.ALTO,
                    regla="NOMBRE_NO_COINCIDE",
                    mensaje=f"@level1name='{valor}' no coincide con el nombre "
                            f"real del procedimiento ({nombre_proc})."
                ))
    return hallazgos


def _validar_valores_sin_comillas(
    llamadas: List[Tuple[int, Dict[str, str]]],
    texto_diccionario: str
) -> List[Hallazgo]:
    """Los valores de nombre deben ir entre comillas N'...'."""
    hallazgos = []
    for pos, args in llamadas:
        for clave in ("level0name", "level1name", "level2name"):
            if clave in args:
                valor = args[clave]
                if not (valor.startswith("N'") or valor.startswith("'")):
                    hallazgos.append(Hallazgo(
                        linea=_numero_linea(texto_diccionario, pos),
                        origen=OrigenAnalisis.DICCIONARIO,
                        severidad=Severidad.CRITICO,
                        regla="VALOR_SIN_COMILLAS",
                        mensaje=f"@{clave}={valor} no esta entre comillas (N'...'). "
                                f"Puede generar error de conversion/sintaxis."
                    ))
    return hallazgos


def _validar_procedimiento_documentado(
    llamadas: List[Tuple[int, Dict[str, str]]],
    esquema: str,
    nombre_proc: str
) -> List[Hallazgo]:
    """Debe existir al menos una descripcion valida a nivel PROCEDURE,
    no solo descripciones de PARAMETER.
    """
    doc_procedimiento = [
        a for _, a in llamadas
        if _es_descripcion_procedimiento_valida(a)
    ]
    if not doc_procedimiento:
        return [Hallazgo(
            linea=1,
            origen=OrigenAnalisis.DICCIONARIO,
            severidad=Severidad.MEDIO,
            regla="PROCEDIMIENTO_SIN_DESCRIPCION",
            mensaje=f"El procedimiento {esquema}.{nombre_proc} no tiene una "
                    f"descripcion valida a nivel PROCEDURE en el script del "
                    f"diccionario."
        )]
    return []


# ---------------------------------------------------------------------------
# ORQUESTADOR PRINCIPAL
# ---------------------------------------------------------------------------

def verificar_diccionario(
    texto_procedimiento: str,
    texto_diccionario: str
) -> List[Hallazgo]:
    """
    Funcion principal: compara el procedimiento (realidad) contra el
    script del diccionario (documentacion) y devuelve los hallazgos.
    """
    hallazgos: List[Hallazgo] = []

    esquema, nombre_proc = extraer_esquema_y_nombre(texto_procedimiento)
    if nombre_proc is None:
        return hallazgos

    tipo_sentencia = extraer_tipo_sentencia(texto_procedimiento)
    parametros_reales = extraer_parametros(texto_procedimiento)
    llamadas = extraer_llamadas_extendedproperty(texto_diccionario)

    # Caso especial ALTER sin ningun rastro de diccionario: se corta aqui,
    # no tiene sentido seguir comparando parametro por parametro si no
    # hay nada con que comparar.
    hallazgos += _validar_alter_sin_diccionario(
        tipo_sentencia, llamadas, esquema, nombre_proc
    )
    if tipo_sentencia == "ALTER" and not llamadas:
        return hallazgos

    hallazgos += _validar_procedimiento_documentado(llamadas, esquema, nombre_proc)
    hallazgos += _validar_parametros_faltantes(
        parametros_reales, llamadas, tipo_sentencia, esquema, nombre_proc
    )
    hallazgos += _validar_nombre_procedimiento(llamadas, nombre_proc, texto_diccionario)
    hallazgos += _validar_esquema(llamadas, esquema, texto_diccionario)
    hallazgos += _validar_descripciones_vacias(llamadas, texto_diccionario)
    hallazgos += _validar_valores_sin_comillas(llamadas, texto_diccionario)

    return hallazgos