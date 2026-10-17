# -*- coding: utf-8 -*-
"""
Reglas para el bloque de índices que acompaña al script de una tabla
(segunda cajita de la pestaña Tablas), según el manual de CAJA ICA:

    PK    Llave primaria
    FK    Llave foránea
    IX    Índice clúster
    IXN   Índice nonclustered
    IXU   Unique índice clúster
    IXUN  Unique índice nonclustered

    Nombre: <Prefijo>_<Tabla>_<Campos indexados...>_INC<nn>, donde nn es el
    número de columnas incluidas con dos dígitos (INC02), solo si hay INCLUDE.
    Ej.: IXN_PERSONA_CPERSCOD_NPERSCLASIFICACION_CPERSESTADO_INC02.
    Los corchetes y ASC/DESC son opcionales; los paréntesis, obligatorios.

Si los índices son de la tabla que se crea en el mismo script, se cruzan con
ella: columnas que existen, tipos que se pueden indexar y clave primaria.
Las líneas de los hallazgos son las de la cajita de índices.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.modelos.hallazgo import Hallazgo, OrigenAnalisis, Severidad
from app.reglas.reglas_tablas import REGLAS_TABLAS

# Más columnas que esta en el INCLUDE se piden validar (ocupan espacio en el índice).
_MAXIMO_INCLUIDAS = 5
_IDENTIFICADOR = r"(?:\[[^\]]+\]|[#@]?[A-Za-z_][\w$#]*)"
_REFERENCIA = rf"{_IDENTIFICADOR}(?:\s*\.\s*{_IDENTIFICADOR}){{0,2}}"
_TIPOS_NO_INDEXABLES = re.compile(r"^(?:N?VARCHAR|VARBINARY)\s*\(\s*MAX\s*\)$|^(?:N?TEXT|IMAGE|XML)$", re.IGNORECASE)
# Columnas de texto descriptivo: no sirven para buscar ni filtrar y vuelven pesado el
# índice. Se reconocen por una parte de su nombre (cDescripcion, CPERSDIRECCION...).
# Se busca la palabra dentro del nombre, así se reconocen también columnas de tablas
# antiguas sin el prefijo del estándar (opinion, copinion, CPERSOPINION...).
_COLUMNAS_DESCRIPTIVAS = {
    "descripcion": "descripción", "direccion": "dirección", "domicilio": "domicilio",
    "observacion": "observación", "comentario": "comentario", "opinion": "opinión",
    "detalle": "detalle", "glosa": "glosa", "mensaje": "mensaje", "referencia": "referencia",
    "motivo": "motivo", "sugerencia": "sugerencia", "justificacion": "justificación",
    "explicacion": "explicación", "aclaracion": "aclaración", "anotacion": "anotación",
    "resena": "reseña", "reseña": "reseña", "reclamo": "reclamo", "queja": "queja",
    "narrativa": "narrativa", "resumen": "resumen", "contenido": "contenido", "respuesta": "respuesta",
    "(?<!con)texto": "texto",  # no dentro de "contexto"
    # Nombres en inglés de tablas heredadas.
    "description": "descripción", "comment": "comentario", "address": "dirección",
    "remark": "observación", "notes": "notas",
}


def _texto_descriptivo(columna: str) -> str:
    """Qué texto descriptivo guarda la columna según su nombre ('' si no lo es)."""
    nombre = columna.lower()
    return next((descripcion for palabra, descripcion in _COLUMNAS_DESCRIPTIVAS.items()
                 if re.search(palabra, nombre)), "")


@dataclass
class _Tabla:
    nombre: str  # sin esquema
    columnas: Dict[str, str] = field(default_factory=dict)  # nombre en minúscula → tipo
    nombres: Dict[str, str] = field(default_factory=dict)  # nombre en minúscula → como se escribió
    pk: List[str] = field(default_factory=list)
    pk_clustered: bool = False
    pk_nombre: str = ""


@dataclass
class _Indice:
    posicion: int
    nombre: str
    unico: bool
    clustered: bool
    tabla: str  # como se escribió (con esquema si lo trae)
    claves: List[str]
    incluidas: List[str]
    posicion_tabla: int
    tipo_explicito: bool = True  # False si dice solo CREATE INDEX (SQL Server lo toma NONCLUSTERED)


def _limpiar(nombre: str) -> str:
    return re.sub(r"\s*\.\s*", ".", nombre.strip()).replace("[", "").replace("]", "")


def _sin_comentarios(texto: str) -> str:
    texto = re.sub(r"/\*.*?\*/", lambda m: re.sub(r"[^\n]", " ", m.group(0)), texto, flags=re.DOTALL)
    return re.sub(r"--[^\n]*", lambda m: " " * len(m.group(0)), texto)


def _linea(texto: str, posicion: int) -> int:
    return texto.count("\n", 0, posicion) + 1


def _hallazgo(texto: str, posicion: int, regla: str, mensaje: str) -> Hallazgo:
    hallazgo = Hallazgo(
        linea=_linea(texto, posicion),
        origen=OrigenAnalisis.REGLAS_ESTATICAS,
        severidad=Severidad(REGLAS_TABLAS[regla].severidad),
        regla=regla,
        mensaje=mensaje,
    )
    hallazgo.seccion = "indices"  # la línea es de la cajita de índices
    return hallazgo


def _contenido_parentesis(texto: str, apertura: int) -> Tuple[str, int]:
    """Contenido entre el paréntesis que abre en `apertura` y su cierre; -1 si no cierra."""
    profundidad = 0
    for indice in range(apertura, len(texto)):
        if texto[indice] == "(":
            profundidad += 1
        elif texto[indice] == ")":
            profundidad -= 1
            if profundidad == 0:
                return texto[apertura + 1:indice], indice
    return texto[apertura + 1:], -1


def _separar(contenido: str) -> List[str]:
    partes, profundidad, actual = [], 0, ""
    for caracter in contenido:
        if caracter == "(":
            profundidad += 1
        elif caracter == ")":
            profundidad -= 1
        if caracter == "," and profundidad == 0:
            partes.append(actual)
            actual = ""
        else:
            actual += caracter
    partes.append(actual)
    return [parte.strip() for parte in partes if parte.strip()]


def _tabla_del_script(texto_tabla: str) -> Optional[_Tabla]:
    """Columnas, tipos y clave primaria del CREATE TABLE del script de la tabla."""
    limpio = _sin_comentarios(texto_tabla or "")
    creacion = re.search(rf"\bCREATE\s+TABLE\s+({_REFERENCIA})\s*\(", limpio, re.IGNORECASE)
    if not creacion:
        return None
    tabla = _Tabla(nombre=_limpiar(creacion.group(1)).split(".")[-1])
    contenido, _ = _contenido_parentesis(limpio, creacion.end() - 1)
    for definicion in _separar(contenido):
        restriccion = re.match(
            r"(?:CONSTRAINT\s+(\S+)\s+)?PRIMARY\s+KEY\s*(NONCLUSTERED|CLUSTERED)?\s*\(([^)]*)\)",
            definicion, re.IGNORECASE,
        )
        if restriccion:
            tabla.pk_nombre = _limpiar(restriccion.group(1) or "")
            tabla.pk = [_limpiar(c.split()[0]) for c in restriccion.group(3).split(",") if c.strip()]
            tabla.pk_clustered = (restriccion.group(2) or "CLUSTERED").upper() == "CLUSTERED"
            continue
        if re.match(r"(?:CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|INDEX)\b", definicion, re.IGNORECASE):
            continue
        columna = re.match(rf"({_IDENTIFICADOR})\s+([A-Za-z]+\s*(?:\([^)]*\))?)", definicion)
        if not columna:
            continue
        nombre = _limpiar(columna.group(1))
        tabla.columnas[nombre.lower()] = re.sub(r"\s+", "", columna.group(2)).upper()
        tabla.nombres[nombre.lower()] = nombre
        en_linea = re.search(r"\bPRIMARY\s+KEY\s*(NONCLUSTERED|CLUSTERED)?", definicion, re.IGNORECASE)
        if en_linea:
            tabla.pk = [nombre]
            tabla.pk_clustered = (en_linea.group(1) or "CLUSTERED").upper() == "CLUSTERED"
    return tabla


def _prefijo(unico: bool, clustered: bool) -> str:
    return {(False, True): "IX", (False, False): "IXN", (True, True): "IXU", (True, False): "IXUN"}[(unico, clustered)]


def _tipo(unico: bool, clustered: bool) -> str:
    return f"{'UNIQUE ' if unico else ''}{'CLUSTERED' if clustered else 'NONCLUSTERED'}"


def _sin_repetir(columnas: List[str], excluir: List[str] = ()) -> List[str]:
    """Columnas sin repetidas (sin distinguir mayúsculas), en su orden."""
    vistas = {c.lower() for c in excluir}
    unicas = []
    for columna in columnas:
        if columna.lower() not in vistas:
            vistas.add(columna.lower())
            unicas.append(columna)
    return unicas


def _nombre_esperado(indice: _Indice, estandar: bool = False) -> str:
    """
    Nombre según el manual; las columnas repetidas cuentan una sola vez.
    estandar: la tabla se crea en el script y también se le pide corregir su nombre, así que
    el índice usa el nombre estándar (TB_cliente_datos -> ClienteDatos). En una tabla que ya
    existe se usa su nombre real.
    """
    tabla = _nombre_estandar_tabla(indice.tabla) if estandar else _limpiar(indice.tabla).split(".")[-1]
    claves = _sin_repetir(indice.claves)
    incluidas = _sin_repetir(indice.incluidas, excluir=claves)
    partes = [_prefijo(indice.unico, indice.clustered), tabla] + claves
    if incluidas:
        partes.append(f"INC{len(incluidas):02d}")
    return "_".join(partes)


_SENTENCIA = re.compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b", re.IGNORECASE)


def verificar_indices(texto_indices: str, texto_tabla: str = "") -> List[Hallazgo]:
    """Valida la sintaxis, el nombre y la estructura de cada CREATE INDEX."""
    texto = texto_indices or ""
    limpio = _sin_comentarios(texto)
    tabla_script = _tabla_del_script(texto_tabla)
    hallazgos: List[Hallazgo] = []
    indices: List[_Indice] = []

    hallazgos.extend(_validar_sentencias_ajenas(texto, limpio))
    inicios = [m.start() for m in _SENTENCIA.finditer(limpio)]
    for numero, inicio in enumerate(inicios):
        fin = inicios[numero + 1] if numero + 1 < len(inicios) else len(limpio)
        sentencia = re.split(r";|\bGO\b", limpio[inicio:fin], maxsplit=1, flags=re.IGNORECASE)[0]
        indice = _leer_indice(texto, inicio, sentencia, hallazgos)
        if indice:
            indices.append(indice)

    for indice in indices:
        hallazgos.extend(_validar_indice(texto, indice, tabla_script))
    duplicados = _validar_duplicados(texto, indices, tabla_script)
    # Un índice duplicado se elimina, no se renombra: sugerir otro nombre podría coincidir
    # con el del índice que ya existe (IXN_Cliente_cCodigo2 -> IXN_Cliente_cCodigo).
    lineas_duplicadas = {h.linea for h in duplicados}
    lineas_por_indice = [texto.count("\n", 0, indice.posicion) + 1 for indice in indices]
    # Si en esa línea hay otro índice (script en una sola línea), no se puede saber de cuál es: se conserva.
    lineas_duplicadas = {linea for linea in lineas_duplicadas if lineas_por_indice.count(linea) == 1}
    hallazgos = [
        h for h in hallazgos
        if not (h.regla in ("INDICE_NOMBRE_NO_ESTANDAR", "INDICE_PREFIJO_INVALIDO") and h.linea in lineas_duplicadas)
    ]
    hallazgos.extend(duplicados)
    return sorted(hallazgos, key=lambda h: h.linea)


def _validar_sentencias_ajenas(texto: str, limpio: str) -> List[Hallazgo]:
    """Instrucciones de la cajita de índices que no son un CREATE INDEX: no se ignoran en silencio."""
    hallazgos = []
    for match in re.finditer(r"[^;]+", limpio):
        for parte in re.split(r"\bGO\b", match.group(0), flags=re.IGNORECASE):
            if not parte.strip() or _SENTENCIA.search(parte):
                continue
            inicio = match.start() + match.group(0).find(parte) + (len(parte) - len(parte.lstrip()))
            primeras = " ".join(parte.split()[:3])
            if re.match(r"\s*DROP\s+INDEX\b", parte, re.IGNORECASE):
                mensaje = (
                    "Se identificó un DROP INDEX en la cajita de índices. Se recomienda quitarlo del script de "
                    "creación, ya que elimina un índice y esta cajita es para revisar los índices que se crean."
                )
            else:
                mensaje = (
                    f"Se identificó una instrucción que no es un CREATE INDEX ({primeras}...). Se recomienda dejar "
                    f"en esta cajita solo los CREATE INDEX de la tabla y revisar si está bien escrita, ya que lo "
                    f"demás no se revisa como índice."
                )
            hallazgos.append(_hallazgo(texto, inicio, "INDICE_SENTENCIA_NO_RECONOCIDA", mensaje))
    return hallazgos


def _leer_indice(texto: str, inicio: int, sentencia: str, hallazgos: List[Hallazgo]) -> Optional[_Indice]:
    """Lee un CREATE INDEX; si su sintaxis no es válida, registra el hallazgo y devuelve None."""
    # a) El nombre del índice no lleva esquema (CREATE INDEX dbo.IXN_... no es válido).
    con_esquema = re.match(
        rf"CREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+({_IDENTIFICADOR})\s*\.\s*({_IDENTIFICADOR})",
        sentencia, re.IGNORECASE,
    )
    if con_esquema:
        esquema, nombre = _limpiar(con_esquema.group(1)), _limpiar(con_esquema.group(2))
        hallazgos.append(_hallazgo(
            texto, inicio, "INDICE_SINTAXIS_INVALIDA",
            f"Se identificó que el nombre del índice {esquema}.{nombre} incluye el esquema ({esquema}), por lo que "
            f"SQL Server no podrá crearlo. Se recomienda escribir solo el nombre del índice ({nombre}) y poner el "
            f"esquema en la tabla (ON {esquema}.Tabla), ya que el índice siempre pertenece al esquema de su tabla.",
        ))
        return None
    cabecera = re.match(
        rf"CREATE\s+(UNIQUE\s+)?(CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\s+({_IDENTIFICADOR})?\s*"
        rf"(?:ON\s+({_REFERENCIA})\s*)?(\()?",
        sentencia, re.IGNORECASE,
    )
    nombre = _limpiar(cabecera.group(3)) if cabecera.group(3) else ""
    if nombre.upper() == "ON":  # CREATE INDEX ON ...: la palabra ON no es el nombre
        nombre = ""
    falta = None
    if not nombre:
        falta = "el nombre"
    elif not cabecera.group(4):
        falta = "la tabla a la que pertenece (ON Esquema.Tabla)"
    elif not cabecera.group(5):
        falta = "la lista de columnas entre paréntesis"
    else:
        claves_texto, cierre = _contenido_parentesis(sentencia, cabecera.end(5) - 1)
        if cierre < 0:
            falta = "el paréntesis que cierra la lista de columnas"
        elif not claves_texto.strip():
            falta = "al menos una columna dentro de los paréntesis"
    if falta:
        sujeto = f"al índice {nombre}" if nombre else "a un índice"
        hallazgos.append(_hallazgo(
            texto, inicio, "INDICE_SINTAXIS_INVALIDA",
            f"Se identificó que {sujeto} le falta {falta}, por lo que SQL Server no podrá crearlo. Se "
            f"recomienda completarlo con esta estructura: CREATE NONCLUSTERED INDEX Nombre ON Esquema.Tabla "
            f"(Columna1, Columna2), ya que es la forma que exige SQL Server para crear un índice.",
        ))
        return None

    claves = [_limpiar(re.sub(r"\s+(?:ASC|DESC)\s*$", "", c, flags=re.IGNORECASE)) for c in _separar(claves_texto)]
    sin_coma = next((c for c in claves if re.search(r"\s", c)), None)
    if sin_coma:
        palabras = sin_coma.split()
        hallazgos.append(_hallazgo(
            texto, inicio, "INDICE_SINTAXIS_INVALIDA",
            f"Se identificó que al índice {nombre} le falta la coma entre las columnas {palabras[0]} y "
            f"{palabras[1]}, por lo que SQL Server no podrá crearlo. Se recomienda separar cada columna con una "
            f"coma (ej.: ({', '.join(palabras)})), ya que así SQL Server reconoce cada columna del índice.",
        ))
        return None
    resto = sentencia[cabecera.end(5) - 1 + len(claves_texto) + 2:]
    incluidas: List[str] = []
    include = re.search(r"\bINCLUDE\s*\(", resto, re.IGNORECASE)
    if include:
        contenido, _ = _contenido_parentesis(resto, include.end() - 1)
        incluidas = [_limpiar(c) for c in _separar(contenido)]
    return _Indice(
        posicion=inicio,
        nombre=nombre,
        unico=bool(cabecera.group(1)),
        clustered=bool(cabecera.group(2)) and cabecera.group(2).strip().upper() == "CLUSTERED",
        tipo_explicito=bool(cabecera.group(2)),
        tabla=cabecera.group(4),
        claves=claves,
        incluidas=incluidas,
        posicion_tabla=inicio + cabecera.start(4),
    )


def _validar_indice(texto: str, indice: _Indice, tabla_script: Optional[_Tabla]) -> List[Hallazgo]:
    hallazgos = []
    tipo = _tipo(indice.unico, indice.clustered)
    prefijo = _prefijo(indice.unico, indice.clustered)
    tabla = _limpiar(indice.tabla)
    tabla_nueva = bool(tabla_script) and tabla.split(".")[-1].lower() == tabla_script.nombre.lower()
    esperado = _nombre_esperado(indice, estandar=tabla_nueva)
    # Con el nombre real de la tabla el índice también se considera correcto.
    validos = {esperado.lower(), _nombre_esperado(indice).lower()}

    # Columnas repetidas en la clave, o columnas clave repetidas en el INCLUDE: SQL Server
    # no crea el índice ("Cannot use duplicate column names in index").
    repetidas = [c for i, c in enumerate(indice.claves) if c.lower() in {x.lower() for x in indice.claves[:i]}]
    en_include = [c for c in indice.incluidas if c.lower() in {x.lower() for x in indice.claves}]
    repetidas += [c for i, c in enumerate(indice.incluidas)
                  if c.lower() in {x.lower() for x in indice.incluidas[:i]}]
    for columna in dict.fromkeys(repetidas):
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_COLUMNA_REPETIDA",
            f"Se identificó que la columna {columna} aparece dos veces en el índice {indice.nombre}. Se "
            f"recomienda dejarla una sola vez, ya que SQL Server no permite repetir una columna en un índice.",
        ))
    for columna in dict.fromkeys(en_include):
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_COLUMNA_REPETIDA",
            f"Se identificó que la columna {columna} está a la vez entre las columnas del índice {indice.nombre} "
            f"y en su INCLUDE. Se recomienda quitarla del INCLUDE, ya que una columna del índice no puede "
            f"repetirse en el INCLUDE.",
        ))

    # Muchas columnas en el INCLUDE: cada una se copia dentro del índice.
    incluidas_unicas = _sin_repetir(indice.incluidas, excluir=indice.claves)
    if len(incluidas_unicas) > _MAXIMO_INCLUIDAS:
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_INCLUDE_EXTENSO",
            f"Se ha identificado que el índice {indice.nombre} lleva {len(incluidas_unicas)} columnas en su "
            f"INCLUDE ({', '.join(incluidas_unicas)}). Se recomienda validar si realmente necesita todas esas "
            f"columnas y dejar solo las que las consultas usan, ya que cada columna incluida se copia dentro "
            f"del índice: ocupa más espacio y vuelve más lentas las inserciones y actualizaciones.",
        ))

    # Nombre: prefijo según el tipo y formato <Prefijo>_<Tabla>_<Campos>_INC<nn>.
    hay_repetidas = bool(repetidas or en_include)
    if indice.nombre.split("_")[0].upper() != prefijo:
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_PREFIJO_INVALIDO",
            (
                f"El índice {indice.nombre} no indica su tipo, por lo que SQL Server lo crea como {tipo}. "
                f"Declarar el tipo y usar el prefijo que le corresponde: CREATE {tipo} INDEX {esperado}."
            ) if not indice.tipo_explicito else (
                f"El índice {indice.nombre} es {tipo}, pero su nombre no empieza con {prefijo}_. "
                f"Renombrarlo como {esperado}, ya que el prefijo indica el tipo de índice."
            ),
        ))
    elif indice.nombre.lower() not in validos and not hay_repetidas:
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_NOMBRE_NO_ESTANDAR",
            f"El nombre del índice {indice.nombre} no corresponde a la tabla y las columnas que indexa. "
            f"Renombrarlo como {esperado} (formato {prefijo}_Tabla_Columnas"
            f"{'_INC' + esperado.rsplit('_INC', 1)[1] if '_INC' in esperado else ''}).",
        ))

    if "." not in tabla:
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_SIN_ESQUEMA",
            f"El índice {indice.nombre} indica la tabla {tabla} sin su esquema. Se recomienda especificar el "
            f"esquema de la tabla al crear el índice, incluso si pertenece a dbo (ejemplo: ON dbo.{tabla}), "
            f"para evitar referencias incorrectas.",
        ))

    # Una descripción nunca identifica los registros: si un índice UNIQUE o CLUSTERED
    # la usa como clave, la tabla debe identificarse por su clave primaria identidad.
    identificadoras = [c for c in indice.claves if _texto_descriptivo(c)] if (indice.unico or indice.clustered) else []
    for columna in identificadoras:
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_IDENTIFICA_POR_DESCRIPCION",
            f"El índice {indice.nombre} usa la columna {columna} para identificar los registros, pero una "
            f"descripción puede repetirse o cambiar con el tiempo. Identificar los registros por la clave "
            f"primaria de la tabla ({_identificador_de(indice, tabla_script)}).",
        ))

    # Columnas de texto descriptivo (descripción, dirección...): se busca indexar lo que sirve.
    for columna in indice.claves + indice.incluidas:
        que = _texto_descriptivo(columna)
        tipo_columna = tabla_script.columnas.get(columna.lower(), "") if tabla_script else ""
        if columna in identificadoras:
            continue  # ya se marca como identificador por descripción (alto)
        if columna in indice.claves and _TIPOS_NO_INDEXABLES.match(tipo_columna or "-"):
            continue  # ya se marca como columna no indexable (crítico)
        if que:
            donde = "" if columna in indice.claves else " en su INCLUDE"
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_COLUMNA_DESCRIPTIVA",
                f"Se identificó que el índice {indice.nombre} incluye{donde} la columna {columna}, que guarda "
                f"texto descriptivo ({que}). Se recomienda quitarla del índice y usar columnas por las que se "
                f"busca o filtra (códigos, fechas, estados), ya que un texto largo hace pesado el índice y no "
                f"acelera las búsquedas.",
            ))

    # La clave primaria siempre es el índice clúster (identidad): ningún otro índice
    # puede serlo. No se prohíbe tajantemente: se pide definirlo NONCLUSTERED.
    if indice.clustered and indice.unico:
        # Un UNIQUE CLUSTERED hace el papel de la clave primaria: se declara la PK directamente.
        identificador = _identificador_de(indice, tabla_script)
        tabla_pk = _nombre_estandar_tabla(indice.tabla)
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_CLUSTERED_CON_PK",
            f"Se identificó que el índice {indice.nombre} se crea como UNIQUE CLUSTERED, es decir, hace el "
            f"papel de la clave primaria de la tabla. Se recomienda declarar la clave primaria directamente "
            f"con un CONSTRAINT sobre una columna identidad, en lugar de un índice UNIQUE CLUSTERED, ya que así "
            f"el índice clúster queda en la clave primaria y se maneja mejor "
            f"(ej.: CONSTRAINT PK_{tabla_pk} PRIMARY KEY CLUSTERED ({identificador})).",
        ))
    elif indice.clustered:
        sugerido = _nombre_esperado(_Indice(**{**indice.__dict__, "clustered": False}), estandar=tabla_nueva)
        hallazgos.append(_hallazgo(
            texto, indice.posicion, "INDICE_CLUSTERED_CON_PK",
            f"Se identificó que el índice {indice.nombre} se crea como CLUSTERED, pero el índice clúster le "
            f"corresponde a la clave primaria identidad de la tabla. Se recomienda definirlo como NONCLUSTERED, "
            f"ya que una tabla solo puede tener un índice clúster y ese lugar es de la clave primaria "
            f"(ej.: {sugerido}).",
        ))

    # Tabla que ya existe (no se crea en el script de la tabla): además de la estructura,
    # se pide validar si de verdad necesita el índice. Sus columnas no se pueden cruzar.
    if not tabla_script or tabla.split(".")[-1].lower() != tabla_script.nombre.lower():
        hallazgos.append(_hallazgo(
            texto, indice.posicion_tabla, "INDICE_TABLA_EXISTENTE",
            f"Se identificó que el índice {indice.nombre} es para la tabla {tabla}, que ya existe (su CREATE "
            f"TABLE no está en el script de la tabla). Se recomienda validar que la tabla realmente necesite este "
            f"índice, revisando las consultas que lo usarán y los índices que ya tiene, ya que en una tabla con "
            f"datos un índice nuevo ocupa espacio, vuelve más lentas las inserciones y podría repetir uno existente.",
        ))
        return hallazgos

    # Columnas que no existen y columnas que no se pueden indexar.
    for columna in indice.claves + indice.incluidas:
        if columna.lower() not in tabla_script.columnas:
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_COLUMNA_NO_EXISTE",
                f"Se identificó que el índice {indice.nombre} usa la columna {columna}, pero la tabla "
                f"{tabla_script.nombre} no tiene una columna con ese nombre. Se recomienda corregir el nombre de la "
                f"columna, ya que así como está SQL Server no podrá crear el índice.",
            ))
    # (N)VARCHAR(MAX), VARBINARY(MAX) y XML no pueden ser columna clave, pero sí ir en el INCLUDE.
    # TEXT, NTEXT e IMAGE no pueden ir en un índice de ninguna forma (ni en el INCLUDE).
    for columna in indice.claves + indice.incluidas:
        tipo_columna = tabla_script.columnas.get(columna.lower(), "")
        if not tipo_columna or not _TIPOS_NO_INDEXABLES.match(tipo_columna):
            continue
        es_max = "(MAX)" in tipo_columna or tipo_columna == "XML"
        en_include = columna not in indice.claves
        if es_max and en_include:
            continue  # válido: una columna MAX sí puede ir en el INCLUDE
        if es_max:
            mensaje = (
                f"Se identificó que la columna {columna} es de tipo {tipo_columna} y está entre las columnas "
                f"clave del índice {indice.nombre}. Se recomienda quitarla de esa lista (si se necesita, puede ir "
                f"en el INCLUDE){' o darle una longitud fija' if '(MAX)' in tipo_columna else ''}, ya que SQL "
                f"Server no permite usar una columna "
                f"{tipo_columna} como columna clave de un índice."
            )
        else:
            donde = "en el INCLUDE" if en_include else "entre las columnas clave"
            mensaje = (
                f"Se identificó que la columna {columna} es de tipo {tipo_columna} y está {donde} del índice "
                f"{indice.nombre}. Se recomienda quitarla del índice, ya que SQL Server no permite usar una "
                f"columna {tipo_columna} en un índice, ni siquiera en el INCLUDE."
            )
        hallazgos.append(_hallazgo(texto, indice.posicion, "INDICE_COLUMNA_NO_INDEXABLE", mensaje))

    return hallazgos


def _nombre_estandar_tabla(tabla: str) -> str:
    """Nombre de la tabla sin esquema ni prefijos TB_/T_ y en PascalCase (TB_cliente_datos → ClienteDatos)."""
    tabla = _limpiar(tabla).split(".")[-1]
    tabla = re.sub(r"^(?:TB|TBL|T)_", "", tabla, flags=re.IGNORECASE)
    return "".join(parte[:1].upper() + parte[1:] for parte in re.split(r"[_\s]+", tabla) if parte)


def _identificador_de(indice: _Indice, tabla_script: Optional[_Tabla]) -> str:
    """Columna identidad de la tabla: la PK del script o, si no la hay, n + NombreTabla + Id."""
    if tabla_script and tabla_script.pk:
        return ", ".join(tabla_script.pk)
    return f"n{_nombre_estandar_tabla(indice.tabla)}Id"


def _validar_duplicados(texto: str, indices: List[_Indice], tabla_script: Optional[_Tabla]) -> List[Hallazgo]:
    """Dos índices con las mismas columnas clave (o uno igual a la clave primaria)."""
    hallazgos = []
    vistos: Dict[Tuple[str, Tuple[str, ...]], str] = {}
    if tabla_script and tabla_script.pk:
        clave_pk = (tabla_script.nombre.lower(), tuple(c.lower() for c in tabla_script.pk))
        vistos[clave_pk] = tabla_script.pk_nombre or "la clave primaria"
    for indice in indices:
        clave = (_limpiar(indice.tabla).split(".")[-1].lower(), tuple(c.lower() for c in indice.claves))
        if clave in vistos:
            es_pk = bool(tabla_script) and vistos[clave] == (tabla_script.pk_nombre or "la clave primaria")
            accion = (f"eliminar el índice {indice.nombre}, ya que la clave primaria ya cubre esas columnas y"
                      if es_pk else "eliminar uno de los dos, ya que")
            hallazgos.append(_hallazgo(
                texto, indice.posicion, "INDICE_DUPLICADO",
                f"Se identificó que el índice {indice.nombre} indexa las mismas columnas ({', '.join(indice.claves)}) "
                f"que {vistos[clave]}. Se recomienda {accion} un índice repetido ocupa espacio y vuelve más lentas "
                f"las inserciones sin acelerar las consultas.",
            ))
        else:
            vistos[clave] = indice.nombre
    return hallazgos
