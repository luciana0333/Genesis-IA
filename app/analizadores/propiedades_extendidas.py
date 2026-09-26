# -*- coding: utf-8 -*-
"""
propiedades_extendidas.py
-------------------------
Lector de scripts de diccionario (sys.sp_addextendedproperty /
sys.sp_updateextendedproperty) compartido por los analizadores de
diccionario de tablas y de procedimientos.

No depende de que las sentencias se separen con GO: recorre el script como
lo haría SQL Server, así que reconoce cada llamada se termine con GO, con
";", con ambos o sin nada. Además:

- respeta las cadenas: un ";" o un "EXEC" dentro de una descripción no
  corta la sentencia, y entiende las comillas escapadas ('');
- ignora los comentarios -- y /* */ (un EXEC comentado no cuenta);
- acepta "sys." opcional, EXEC o EXECUTE, parámetros con nombre o
  posicionales y valores con o sin comillas;
- registra errores de sintaxis (coma sobrante, falta de "=", cadena sin
  cerrar, parámetro desconocido...) con la línea donde ocurren.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# Orden oficial de los parámetros, usado para las llamadas posicionales.
PARAMETROS = (
    "name", "value",
    "level0type", "level0name",
    "level1type", "level1name",
    "level2type", "level2name",
)

_INICIO_LLAMADA = re.compile(
    r"\bEXEC(?:UTE)?\s+(?:\[?sys\]?\s*\.\s*)?\[?sp_(add|update)extendedproperty\]?(?![\w$#@])",
    re.IGNORECASE,
)
_PALABRA = re.compile(r"[A-Za-z_#][\w$#]*")
_NUMERO = re.compile(r"[+-]?\d+(?:\.\d+)?")


@dataclass
class ValorArgumento:
    """Valor de un parámetro tal como aparece en el script."""
    crudo: str            # texto original: N'Cliente', dbo, [dbo], NULL
    texto: str            # valor efectivo: Cliente, dbo
    entre_comillas: bool  # True si es una cadena '...' o N'...'


@dataclass
class LlamadaPropiedad:
    """Una llamada a sp_addextendedproperty / sp_updateextendedproperty."""
    posicion: int
    linea: int
    operacion: str  # "add" | "update"
    argumentos: Dict[str, ValorArgumento] = field(default_factory=dict)
    errores: List[Tuple[int, str]] = field(default_factory=list)  # (línea, mensaje)
    repetidos: List[str] = field(default_factory=list)

    def texto(self, parametro: str) -> str:
        valor = self.argumentos.get(parametro)
        return valor.texto.strip() if valor else ""

    def tiene(self, parametro: str) -> bool:
        return parametro in self.argumentos


# ---------------------------------------------------------------------------
# PREPROCESO: comentarios y cadenas
# ---------------------------------------------------------------------------

def _neutralizar_comentarios(texto: str) -> Tuple[str, List[Tuple[int, int]]]:
    """
    Reemplaza los comentarios por espacios (conservando saltos de línea y
    posiciones) y devuelve también los rangos [inicio, fin) de las cadenas.
    """
    salida = list(texto)
    cadenas: List[Tuple[int, int]] = []
    i, n = 0, len(texto)
    while i < n:
        c = texto[i]
        if c == "'":
            inicio = i
            i += 1
            while i < n:
                if texto[i] == "'":
                    if i + 1 < n and texto[i + 1] == "'":
                        i += 2
                        continue
                    i += 1
                    break
                i += 1
            cadenas.append((inicio, i))
            continue
        if texto.startswith("--", i):
            fin = texto.find("\n", i)
            fin = n if fin == -1 else fin
            for j in range(i, fin):
                salida[j] = " "
            i = fin
            continue
        if texto.startswith("/*", i):
            fin = texto.find("*/", i + 2)
            fin = n if fin == -1 else fin + 2
            for j in range(i, fin):
                if salida[j] not in "\r\n":
                    salida[j] = " "
            i = fin
            continue
        i += 1
    return "".join(salida), cadenas


def _dentro_de_cadena(posicion: int, cadenas: List[Tuple[int, int]]) -> bool:
    return any(inicio <= posicion < fin for inicio, fin in cadenas)


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


# ---------------------------------------------------------------------------
# ANÁLISIS LÉXICO DE LOS ARGUMENTOS
# ---------------------------------------------------------------------------

@dataclass
class _Token:
    tipo: str   # parametro | igual | coma | puntoycoma | cadena | valor | fin | otro
    crudo: str
    inicio: int
    fin: int
    cadena_cerrada: bool = True


def _siguiente_token(texto: str, i: int) -> _Token:
    n = len(texto)
    while i < n and texto[i].isspace():
        i += 1
    if i >= n:
        return _Token("fin", "", n, n)
    c = texto[i]
    if c == "@":
        m = _PALABRA.match(texto, i + 1)
        fin = m.end() if m else i + 1
        return _Token("parametro", texto[i:fin], i, fin)
    if c == "=":
        return _Token("igual", c, i, i + 1)
    if c == ",":
        return _Token("coma", c, i, i + 1)
    if c == ";":
        return _Token("puntoycoma", c, i, i + 1)
    if c == "'" or (c in "Nn" and i + 1 < n and texto[i + 1] == "'"):
        j = i + (2 if c != "'" else 1)
        cerrada = False
        while j < n:
            if texto[j] == "'":
                if j + 1 < n and texto[j + 1] == "'":
                    j += 2
                    continue
                j += 1
                cerrada = True
                break
            j += 1
        return _Token("cadena", texto[i:j], i, j, cerrada)
    if c == "[":
        fin = texto.find("]", i)
        fin = n if fin == -1 else fin + 1
        return _Token("valor", texto[i:fin], i, fin)
    m = _NUMERO.match(texto, i) or _PALABRA.match(texto, i)
    if m:
        return _Token("valor", m.group(0), i, m.end())
    return _Token("otro", c, i, i + 1)


def _valor_desde_token(token: _Token) -> ValorArgumento:
    crudo = token.crudo
    if token.tipo == "cadena":
        contenido = crudo[2:] if crudo[:1] in "Nn" else crudo[1:]
        if token.cadena_cerrada:
            contenido = contenido[:-1]
        return ValorArgumento(crudo, contenido.replace("''", "'"), True)
    if crudo.startswith("[") and crudo.endswith("]"):
        return ValorArgumento(crudo, crudo[1:-1], False)
    if crudo.upper() == "NULL":
        return ValorArgumento(crudo, "", False)
    return ValorArgumento(crudo, crudo, False)


def _es_fin_de_sentencia(token: _Token) -> bool:
    """GO o el inicio de otro EXEC cierran la sentencia aunque falte el ';'."""
    return token.tipo == "fin" or (
        token.tipo == "valor" and token.crudo.upper() in {"GO", "EXEC", "EXECUTE"}
    )


def _leer_argumentos(texto: str, i: int, llamada: LlamadaPropiedad, original: str) -> None:
    posicional = 0
    esperando_argumento = True
    ultimo: Optional[str] = None
    ultima_coma = i

    def error(posicion: int, mensaje: str) -> None:
        llamada.errores.append((_linea(original, posicion), mensaje))

    def guardar(nombre: str, valor: ValorArgumento, posicion: int) -> None:
        if nombre in llamada.argumentos:
            llamada.repetidos.append(nombre)
            error(posicion, f"El parámetro @{nombre} está repetido en la misma sentencia.")
        llamada.argumentos[nombre] = valor

    while True:
        token = _siguiente_token(texto, i)

        if esperando_argumento:
            if token.tipo == "parametro":
                nombre = token.crudo[1:].lower()
                if nombre not in PARAMETROS:
                    error(token.inicio, f"El parámetro {token.crudo} no es válido para sp_addextendedproperty.")
                igual = _siguiente_token(texto, token.fin)
                if igual.tipo == "igual":
                    valor = _siguiente_token(texto, igual.fin)
                else:
                    # Se recupera tomando el siguiente valor como si tuviera '='.
                    error(token.inicio, f"Falta el signo '=' después de {token.crudo}.")
                    valor = igual
                if valor.tipo not in ("cadena", "valor") or _es_fin_de_sentencia(valor):
                    error(token.inicio, f"Falta el valor de {token.crudo}.")
                    i = igual.fin if igual.tipo == "igual" else token.fin
                    esperando_argumento = False
                    ultimo = nombre
                    continue
                if valor.tipo == "cadena" and not valor.cadena_cerrada:
                    error(valor.inicio, f"La cadena de {token.crudo} no está cerrada con comilla simple.")
                guardar(nombre, _valor_desde_token(valor), token.inicio)
                i = valor.fin
                esperando_argumento = False
                ultimo = nombre
                continue

            if token.tipo in ("cadena", "valor") and not _es_fin_de_sentencia(token):
                if posicional >= len(PARAMETROS):
                    error(token.inicio, "La sentencia tiene más valores de los que admite sp_addextendedproperty.")
                else:
                    guardar(PARAMETROS[posicional], _valor_desde_token(token), token.inicio)
                    ultimo = PARAMETROS[posicional]
                posicional += 1
                i = token.fin
                esperando_argumento = False
                continue

            # Se esperaba un argumento y no llegó: coma sobrante o sentencia vacía.
            if ultimo is not None:
                error(ultima_coma, f"Coma sobrante después de @{ultimo}: la sentencia termina sin otro parámetro.")
            elif not llamada.argumentos:
                error(token.inicio, "La llamada a sp_addextendedproperty no tiene parámetros.")
            return

        # Después de un valor solo puede venir ",", ";" o el fin de la sentencia.
        if token.tipo == "coma":
            ultima_coma = token.inicio
            i = token.fin
            esperando_argumento = True
            continue
        if token.tipo == "puntoycoma" or _es_fin_de_sentencia(token):
            return
        if token.tipo == "parametro":
            error(token.inicio, f"Falta una coma entre @{ultimo} y {token.crudo}.")
            esperando_argumento = True
            continue
        error(token.inicio, f"Texto inesperado '{token.crudo}' después de @{ultimo}.")
        return


# ---------------------------------------------------------------------------
# API PÚBLICA
# ---------------------------------------------------------------------------

def leer_propiedades_extendidas(texto: str) -> List[LlamadaPropiedad]:
    """Devuelve cada llamada a sp_add/updateextendedproperty del script."""
    if not texto:
        return []
    limpio, cadenas = _neutralizar_comentarios(texto)
    llamadas: List[LlamadaPropiedad] = []
    for coincidencia in _INICIO_LLAMADA.finditer(limpio):
        if _dentro_de_cadena(coincidencia.start(), cadenas):
            continue
        llamada = LlamadaPropiedad(
            posicion=coincidencia.start(),
            linea=_linea(texto, coincidencia.start()),
            operacion=coincidencia.group(1).lower(),
        )
        _leer_argumentos(limpio, coincidencia.end(), llamada, texto)
        llamadas.append(llamada)
    return llamadas


def como_llamadas_crudas(llamadas: List[LlamadaPropiedad]) -> List[Tuple[int, Dict[str, str]]]:
    """
    Adaptador al formato histórico [(posición, {parámetro: valor_crudo})]
    que usan los validadores del diccionario de procedimientos.
    """
    return [
        (llamada.posicion, {nombre: valor.crudo for nombre, valor in llamada.argumentos.items()})
        for llamada in llamadas
    ]
