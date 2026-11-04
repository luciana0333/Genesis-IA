// Revisor de Genesis sobre el árbol de ScriptDom (el código ya desarmado como lo entiende SQL Server).
// PowerShell lo compila una sola vez al abrir (Add-Type, C# 5 de .NET Framework: sin $"..." ni ?.).
// Devuelve hechos (tipo, línea y datos); los mensajes y la severidad se definen en Python (scriptdom.py).
//
// Los casos que hacen fallar el script o que dan un resultado equivocado se comprobaron en SQL Server.
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Microsoft.SqlServer.TransactSql.ScriptDom;

public static class GenesisRevisor
{
    public static List<Dictionary<string, object>> Revisar(TSqlFragment arbol)
    {
        var visitante = new GenesisVisitante();
        arbol.Accept(visitante);
        return visitante.Hallazgos.OrderBy(h => (int)h["linea"]).ToList();
    }
}

// Variable o parámetro declarado en el bloque, con su tipo.
public class GenesisDeclaracion
{
    public string Nombre;
    public int Posicion;
    public int Linea;
    public string Familia = "";   // varchar, nvarchar, int, datetime...
    public int Largo;             // tamaño declarado; -1 = MAX; 0 = sin tamaño o no aplica
    public bool EsTabla;
    public bool EsParametro;
    public bool EsSalida;
    public bool TieneValor;
}

// ¿La expresión usa alguna columna? (una función que solo recibe variables da lo mismo en cada fila).
public class GenesisBuscaColumna : TSqlFragmentVisitor
{
    public bool Encontrada;
    public override void Visit(ColumnReferenceExpression columna) { Encontrada = true; }
}

// Busca un agregado (SUM, COUNT...) sin entrar en subconsultas: en ellas el agregado es válido.
public class GenesisBuscaAgregado : TSqlFragmentVisitor
{
    public int Linea;
    public override void ExplicitVisit(ScalarSubquery nodo) { }
    public override void ExplicitVisit(QueryDerivedTable nodo) { }
    public override void Visit(FunctionCall funcion)
    {
        if (Linea == 0 && funcion.OverClause == null && GenesisVisitante.EsAgregado(funcion)) Linea = funcion.StartLine;
    }
}

public class GenesisVisitante : TSqlFragmentVisitor
{
    public readonly List<Dictionary<string, object>> Hallazgos = new List<Dictionary<string, object>>();

    private static readonly HashSet<string> Agregados = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "SUM", "COUNT", "COUNT_BIG", "AVG", "MIN", "MAX", "STDEV", "STDEVP", "VAR", "VARP", "STRING_AGG" };
    private static readonly HashSet<string> FuncionesSobreColumna = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "YEAR", "MONTH", "DAY", "DATEPART", "DATEDIFF", "DATEADD", "ISNULL", "UPPER", "LOWER", "LTRIM", "RTRIM",
          "TRIM", "REPLACE", "ABS", "EOMONTH", "FORMAT" };
    private static readonly HashSet<string> TiposFecha = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "datetime", "smalldatetime", "datetime2" };
    private static readonly HashSet<string> TiposTexto = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "varchar", "char", "nvarchar", "nchar" };
    private static readonly HashSet<string> TiposNumero = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "int", "bigint", "smallint", "tinyint", "decimal", "numeric", "money", "smallmoney", "float", "real" };
    // Métodos de los tipos XML, hierarchyid y geography (R.X.value(...)): no son funciones propias.
    private static readonly HashSet<string> MetodosDeTipos = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        { "value", "query", "exist", "nodes", "modify", "ToString", "GetAncestor", "GetDescendant", "GetLevel",
          "IsDescendantOf", "GetReparentedValue", "STDistance", "STAsText", "STContains", "STIntersects", "Lat", "Long" };
    private static readonly Regex PalabrasSql = new Regex(@"\b(SELECT|INSERT|UPDATE|DELETE|WHERE|EXEC|EXECUTE|FROM)\b", RegexOptions.IgnoreCase);
    private static readonly Regex Credencial = new Regex(@"\b(pwd|password)\s*=\s*[^;'\s]+", RegexOptions.IgnoreCase);
    private static readonly Regex SoloFecha = new Regex(@"^\s*\d{4}-?\d{2}-?\d{2}\s*$");

    // --- Estado del bloque actual (entre GO) ---------------------------------------------------------
    private Dictionary<string, int> temporales;
    private Dictionary<string, GenesisDeclaracion> declaraciones;
    private Dictionary<string, Dictionary<string, string>> columnasDeTablas;   // #T / @T -> columna -> tipo
    private HashSet<int> objetivos;      // posición de las variables que reciben un valor (no son lecturas)
    private HashSet<int> ignoradas;      // @p = ... de un EXEC: es el parámetro del procedimiento llamado
    private HashSet<int> lecturasNulas;  // @x IS NULL, ISNULL(@x, ...): leer NULL ahí es intencional
    private List<KeyValuePair<string, int>> escrituras;   // variable -> posición desde la que ya tiene valor
    private List<Tuple<string, int, int>> usos;           // variable, posición, línea
    private List<Tuple<string, int>> etiquetasGoto;       // etiqueta, línea del GOTO
    private HashSet<string> etiquetas;
    private List<Tuple<string, int, string>> sentencias;  // texto normalizado, línea, tipo (bloques repetidos)
    private List<Tuple<int, string>> concatenaciones;     // SQL dinámico armado con un parámetro de texto
    private bool ejecutaDinamico;
    private bool xactAbort;
    private bool anidamientoAvisado;

    private int profundidadWhile, profundidadCondicion, profundidadCase, profundidadExists, profundidadTry,
                profundidadCatch, profundidadGuarda, profundidadAnidamiento;
    private readonly Stack<Dictionary<string, string>> tablasDelFrom = new Stack<Dictionary<string, string>>();
    private readonly Stack<HashSet<string>> opcionalesDelFrom = new Stack<HashSet<string>>();
    // ISNULL sobre columnas: columnas NOT NULL de las temporales del script (tabla -> columna -> línea) y de dónde
    // se llena cada columna de una temporal (tabla -> columna -> tabla física y columna de origen).
    private Dictionary<string, Dictionary<string, int>> columnasNoNulas;
    private Dictionary<string, Dictionary<string, Tuple<string, string>>> origenes;
    private readonly HashSet<int> isnullRevisados = new HashSet<int>();
    private readonly Stack<bool> consultasConFrom = new Stack<bool>();

    private void Agregar(string tipo, int linea, params object[] pares)
    {
        var hallazgo = new Dictionary<string, object>();
        hallazgo["tipo"] = tipo;
        hallazgo["linea"] = linea;
        for (int i = 0; i + 1 < pares.Length; i += 2) hallazgo[(string)pares[i]] = pares[i + 1];
        Hallazgos.Add(hallazgo);
    }

    // --- Utilidades ------------------------------------------------------------------------------------
    private static string Nombre(SchemaObjectName nombre)
    {
        if (nombre == null) return "";
        return string.Join(".", nombre.Identifiers.Select(i => i.Value));
    }

    private static bool TieneColumna(ScalarExpression expresion)
    {
        var buscador = new GenesisBuscaColumna();
        if (expresion != null) expresion.Accept(buscador);
        return buscador.Encontrada;
    }

    public static bool EsAgregado(FunctionCall funcion)
    {
        return funcion.CallTarget == null && Agregados.Contains(funcion.FunctionName.Value);
    }

    private static string Texto(TSqlFragment fragmento)
    {
        if (fragmento == null || fragmento.FirstTokenIndex < 0) return "";
        var texto = new StringBuilder();
        for (int i = fragmento.FirstTokenIndex; i <= fragmento.LastTokenIndex; i++)
        {
            var ficha = fragmento.ScriptTokenStream[i];
            if (ficha.TokenType == TSqlTokenType.SingleLineComment || ficha.TokenType == TSqlTokenType.MultilineComment) continue;
            texto.Append(ficha.TokenType == TSqlTokenType.WhiteSpace ? " " : ficha.Text);
        }
        return Regex.Replace(texto.ToString(), @"\s+", " ").Trim();
    }

    // Texto para comparar dos fragmentos: sin espacios, comentarios ni mayúsculas.
    private static string Normalizado(TSqlFragment fragmento)
    {
        if (fragmento == null || fragmento.FirstTokenIndex < 0) return "";
        var partes = new List<string>();
        for (int i = fragmento.FirstTokenIndex; i <= fragmento.LastTokenIndex; i++)
        {
            var ficha = fragmento.ScriptTokenStream[i];
            if (ficha.TokenType == TSqlTokenType.WhiteSpace || ficha.TokenType == TSqlTokenType.SingleLineComment
                || ficha.TokenType == TSqlTokenType.MultilineComment) continue;
            partes.Add(ficha.Text.ToUpperInvariant());
        }
        return string.Join(" ", partes);
    }

    private static int CantidadDeFichas(TSqlFragment fragmento)
    {
        int cantidad = 0;
        for (int i = fragmento.FirstTokenIndex; i <= fragmento.LastTokenIndex; i++)
        {
            var tipo = fragmento.ScriptTokenStream[i].TokenType;
            if (tipo != TSqlTokenType.WhiteSpace && tipo != TSqlTokenType.SingleLineComment
                && tipo != TSqlTokenType.MultilineComment) cantidad++;
        }
        return cantidad;
    }

    private static bool Contiene(TSqlFragment fragmento, params string[] palabras)
    {
        if (fragmento == null || fragmento.FirstTokenIndex < 0) return false;
        for (int i = fragmento.FirstTokenIndex; i <= fragmento.LastTokenIndex; i++)
        {
            string texto = fragmento.ScriptTokenStream[i].Text;
            if (palabras.Any(p => string.Equals(texto, p, StringComparison.OrdinalIgnoreCase))) return true;
        }
        return false;
    }

    private static ScalarExpression SinParentesis(ScalarExpression expresion)
    {
        while (expresion is ParenthesisExpression) expresion = ((ParenthesisExpression)expresion).Expression;
        return expresion;
    }

    private static BooleanExpression SinParentesis(BooleanExpression expresion)
    {
        while (expresion is BooleanParenthesisExpression) expresion = ((BooleanParenthesisExpression)expresion).Expression;
        return expresion;
    }

    private static QuerySpecification PrimeraConsulta(QueryExpression consulta)
    {
        while (true)
        {
            var parentesis = consulta as QueryParenthesisExpression;
            var union = consulta as BinaryQueryExpression;
            if (parentesis != null) consulta = parentesis.QueryExpression;
            else if (union != null) consulta = union.FirstQueryExpression;
            else return consulta as QuerySpecification;
        }
    }

    private static void TipoDe(DataTypeReference tipo, GenesisDeclaracion declaracion)
    {
        var sql = tipo as SqlDataTypeReference;
        if (sql == null) { declaracion.Familia = tipo != null ? Nombre(tipo.Name).ToLowerInvariant() : ""; return; }
        declaracion.Familia = sql.SqlDataTypeOption.ToString().ToLowerInvariant();
        if (sql.Parameters.Count == 0) return;
        if (sql.Parameters[0] is MaxLiteral) declaracion.Largo = -1;
        else
        {
            int largo;
            if (int.TryParse(sql.Parameters[0].Value, out largo)) declaracion.Largo = largo;
        }
    }

    private GenesisDeclaracion Declarada(string nombre, int posicion)
    {
        GenesisDeclaracion declaracion;
        if (declaraciones.TryGetValue(nombre, out declaracion) && declaracion.Posicion <= posicion) return declaracion;
        return null;
    }

    private static bool EsTemporal(string tabla)
    {
        return tabla != null && (tabla.StartsWith("#") || tabla.StartsWith("@"));
    }

    // Tabla de una columna (c.cCodigo -> la tabla del alias c), según el FROM de la consulta actual.
    private string TablaDe(ColumnReferenceExpression columna)
    {
        if (columna.MultiPartIdentifier == null || tablasDelFrom.Count == 0) return null;
        var partes = columna.MultiPartIdentifier.Identifiers;
        var actual = tablasDelFrom.Peek();
        if (partes.Count >= 2)
        {
            string calificador = partes[partes.Count - 2].Value;
            foreach (var mapa in tablasDelFrom)
            {
                string tabla;
                if (mapa.TryGetValue(calificador, out tabla)) return tabla;
            }
            return null;
        }
        return actual.Count == 1 ? actual.Values.First() : null;
    }

    private static string NombreColumna(ColumnReferenceExpression columna)
    {
        if (columna.MultiPartIdentifier == null) return "";
        return columna.MultiPartIdentifier.Identifiers.Last().Value;
    }

    private static Dictionary<string, string> MapaDelFrom(FromClause from)
    {
        return MapaDelFrom(from, null);
    }

    // `opcionales`: nombres (alias) de las tablas del lado opcional de un LEFT / RIGHT / FULL JOIN u OUTER APPLY,
    // cuyas columnas pueden llegar en NULL aunque en la tabla sean NOT NULL.
    private static Dictionary<string, string> MapaDelFrom(FromClause from, HashSet<string> opcionales)
    {
        var mapa = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        if (from != null) foreach (var referencia in from.TableReferences) LlenarMapa(referencia, mapa, opcionales, false);
        return mapa;
    }

    private static void LlenarMapa(TableReference referencia, Dictionary<string, string> mapa)
    {
        LlenarMapa(referencia, mapa, null, false);
    }

    private static void LlenarMapa(TableReference referencia, Dictionary<string, string> mapa, HashSet<string> opcionales,
                                   bool opcional)
    {
        var calificado = referencia as QualifiedJoin;
        var sinCalificar = referencia as UnqualifiedJoin;
        var parentesis = referencia as JoinParenthesisTableReference;
        if (calificado != null)
        {
            var tipo = calificado.QualifiedJoinType;
            LlenarMapa(calificado.FirstTableReference, mapa, opcionales,
                       opcional || tipo == QualifiedJoinType.RightOuter || tipo == QualifiedJoinType.FullOuter);
            LlenarMapa(calificado.SecondTableReference, mapa, opcionales,
                       opcional || tipo == QualifiedJoinType.LeftOuter || tipo == QualifiedJoinType.FullOuter);
            return;
        }
        if (sinCalificar != null)
        {
            LlenarMapa(sinCalificar.FirstTableReference, mapa, opcionales, opcional);
            LlenarMapa(sinCalificar.SecondTableReference, mapa, opcionales,
                       opcional || sinCalificar.UnqualifiedJoinType == UnqualifiedJoinType.OuterApply);
            return;
        }
        if (parentesis != null) { LlenarMapa(parentesis.Join, mapa, opcionales, opcional); return; }
        var nombrada = referencia as NamedTableReference;
        var variable = referencia as VariableTableReference;
        var conAlias = referencia as TableReferenceWithAlias;
        string tabla = nombrada != null ? Nombre(nombrada.SchemaObject) : variable != null ? variable.Variable.Name : "(subconsulta)";
        var nombres = new List<string>();
        if (conAlias != null && conAlias.Alias != null) nombres.Add(conAlias.Alias.Value);
        else if (nombrada != null) { nombres.Add(tabla); nombres.Add(nombrada.SchemaObject.BaseIdentifier.Value); }
        else if (variable != null) nombres.Add(tabla);
        foreach (var nombre in nombres)
        {
            mapa[nombre] = tabla;
            if (opcional && opcionales != null) opcionales.Add(nombre);
        }
    }

    // Tabla de la columna y si está del lado opcional de un OUTER JOIN, según los FROM que la rodean.
    private string TablaDe(ColumnReferenceExpression columna, out bool opcional)
    {
        opcional = false;
        if (columna.MultiPartIdentifier == null || tablasDelFrom.Count == 0) return null;
        var partes = columna.MultiPartIdentifier.Identifiers;
        var mapas = tablasDelFrom.ToArray();
        var opcionales = opcionalesDelFrom.ToArray();
        if (partes.Count >= 2)
        {
            string calificador = partes[partes.Count - 2].Value;
            for (int i = 0; i < mapas.Length; i++)
            {
                string tabla;
                if (!mapas[i].TryGetValue(calificador, out tabla)) continue;
                opcional = opcionales[i].Contains(calificador);
                return tabla;
            }
            return null;
        }
        if (mapas[0].Count == 0) return null;
        var unica = mapas[0].Values.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
        if (unica.Count != 1) return null;
        opcional = opcionales[0].Count > 0;
        return unica[0];
    }

    // --- Bloque (entre GO): se reinicia el estado y al final se revisan las variables --------------------
    public override void ExplicitVisit(TSqlBatch lote)
    {
        temporales = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        declaraciones = new Dictionary<string, GenesisDeclaracion>(StringComparer.OrdinalIgnoreCase);
        columnasDeTablas = new Dictionary<string, Dictionary<string, string>>(StringComparer.OrdinalIgnoreCase);
        columnasNoNulas = new Dictionary<string, Dictionary<string, int>>(StringComparer.OrdinalIgnoreCase);
        origenes = new Dictionary<string, Dictionary<string, Tuple<string, string>>>(StringComparer.OrdinalIgnoreCase);
        objetivos = new HashSet<int>();
        ignoradas = new HashSet<int>();
        lecturasNulas = new HashSet<int>();
        escrituras = new List<KeyValuePair<string, int>>();
        usos = new List<Tuple<string, int, int>>();
        etiquetasGoto = new List<Tuple<string, int>>();
        etiquetas = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        sentencias = new List<Tuple<string, int, string>>();
        concatenaciones = new List<Tuple<int, string>>();
        ejecutaDinamico = xactAbort = anidamientoAvisado = false;

        RevisarLista(lote.Statements);
        base.ExplicitVisit(lote);
        CerrarBloque();
    }

    private void CerrarBloque()
    {
        var avisadas = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var uso in usos)
        {
            string nombre = uso.Item1;
            var declaracion = Declarada(nombre, uso.Item2);
            // 137: la variable no está declarada (o se usa antes de su DECLARE).
            if (declaracion == null)
            {
                if (avisadas.Add(nombre)) Agregar("VARIABLE_NO_DECLARADA", uso.Item3, "variable", nombre);
                continue;
            }
            // Se lee antes de recibir un valor: vale NULL.
            if (declaracion.EsParametro || declaracion.EsTabla || declaracion.TieneValor || declaracion.Familia == "cursor") continue;
            if (objetivos.Contains(uso.Item2) || lecturasNulas.Contains(uso.Item2)) continue;
            bool asignada = escrituras.Any(e => string.Equals(e.Key, nombre, StringComparison.OrdinalIgnoreCase) && e.Value <= uso.Item2);
            if (!asignada && avisadas.Add(nombre))
                Agregar("VARIABLE_SIN_VALOR", uso.Item3, "variable", nombre, "familia", declaracion.Familia);
        }
        foreach (var declaracion in declaraciones.Values.Where(d => d.EsParametro))
        {
            bool usado = usos.Any(u => string.Equals(u.Item1, declaracion.Nombre, StringComparison.OrdinalIgnoreCase));
            if (!usado) Agregar("PARAMETRO_SIN_USO", declaracion.Linea, "variable", declaracion.Nombre);
            else if (declaracion.EsSalida && !escrituras.Any(e => string.Equals(e.Key, declaracion.Nombre, StringComparison.OrdinalIgnoreCase)))
                Agregar("PARAMETRO_OUTPUT_SIN_VALOR", declaracion.Linea, "variable", declaracion.Nombre);
        }
        foreach (var salto in etiquetasGoto.Where(g => !etiquetas.Contains(g.Item1)))
            Agregar("GOTO_SIN_ETIQUETA", salto.Item2, "etiqueta", salto.Item1);
        foreach (var grupo in sentencias.GroupBy(s => s.Item1).Where(g => g.Count() > 1))
            Agregar("BLOQUE_REPETIDO", grupo.Skip(1).First().Item2, "lineas", grupo.Select(s => s.Item2).ToArray(),
                    "instruccion", grupo.First().Item3);
        if (ejecutaDinamico)
            foreach (var concatenacion in concatenaciones)
                Agregar("SQL_DINAMICO_CONCATENA_PARAMETRO", concatenacion.Item1, "variable", concatenacion.Item2);
    }

    // --- Declaraciones y asignaciones de variables ---------------------------------------------------
    public override void Visit(DeclareVariableElement elemento)
    {
        string nombre = elemento.VariableName.Value;
        var parametro = elemento as ProcedureParameter;
        if (declaraciones.ContainsKey(nombre))
            Agregar("VARIABLE_DECLARADA_DOS_VECES", elemento.StartLine, "variable", nombre, "primera", declaraciones[nombre].Linea);
        var declaracion = new GenesisDeclaracion
        {
            Nombre = nombre, Posicion = elemento.StartOffset, Linea = elemento.StartLine,
            EsParametro = parametro != null, EsSalida = parametro != null && parametro.Modifier == ParameterModifier.Output,
            TieneValor = elemento.Value != null,
        };
        TipoDe(elemento.DataType, declaracion);
        if (!declaraciones.ContainsKey(nombre)) declaraciones[nombre] = declaracion;
        if (elemento.Value != null)
        {
            escrituras.Add(new KeyValuePair<string, int>(nombre, elemento.StartOffset + elemento.FragmentLength));
            RevisarTextoLargo(declaracion, elemento.Value, elemento.StartLine);
            RevisarConcatenacion(elemento.Value, nombre);
        }
    }

    public override void Visit(DeclareTableVariableBody tabla)
    {
        if (tabla.VariableName == null) return;
        string nombre = tabla.VariableName.Value;
        if (declaraciones.ContainsKey(nombre))
            Agregar("VARIABLE_DECLARADA_DOS_VECES", tabla.StartLine, "variable", nombre, "primera", declaraciones[nombre].Linea);
        else
            declaraciones[nombre] = new GenesisDeclaracion { Nombre = nombre, Posicion = tabla.StartOffset, Linea = tabla.StartLine, EsTabla = true };
        RevisarDefinicion(nombre, tabla.Definition);
    }

    private void Asigna(VariableReference variable, TSqlFragment hasta, AssignmentKind tipo)
    {
        if (variable == null) return;
        // SET @i += 1 también lee la variable: no se marca como solo escritura.
        if (tipo == AssignmentKind.Equals) objetivos.Add(variable.StartOffset);
        escrituras.Add(new KeyValuePair<string, int>(variable.Name, hasta.StartOffset + hasta.FragmentLength));
    }

    public override void Visit(SetVariableStatement asignacion)
    {
        Asigna(asignacion.Variable, asignacion, asignacion.AssignmentKind);
        if (asignacion.Variable == null || asignacion.Expression == null) return;
        var declaracion = Declarada(asignacion.Variable.Name, asignacion.StartOffset);
        if (asignacion.AssignmentKind == AssignmentKind.Equals) RevisarTextoLargo(declaracion, asignacion.Expression, asignacion.StartLine);
        RevisarConcatenacion(asignacion.Expression, asignacion.Variable.Name);
    }

    public override void Visit(SelectSetVariable asignacion)
    {
        Asigna(asignacion.Variable, asignacion, asignacion.AssignmentKind);
        var declaracion = Declarada(asignacion.Variable.Name, asignacion.StartOffset);
        if (asignacion.AssignmentKind == AssignmentKind.Equals) RevisarTextoLargo(declaracion, asignacion.Expression, asignacion.StartLine);
        RevisarConcatenacion(asignacion.Expression, asignacion.Variable.Name);
    }

    public override void Visit(AssignmentSetClause asignacion)
    {
        if (asignacion.Variable != null) Asigna(asignacion.Variable, asignacion, asignacion.AssignmentKind);
    }

    public override void Visit(FetchCursorStatement fetch)
    {
        foreach (var variable in fetch.IntoVariables) Asigna(variable, fetch, AssignmentKind.Equals);
    }

    public override void Visit(ExecuteParameter parametro)
    {
        if (parametro.Variable != null) ignoradas.Add(parametro.Variable.StartOffset);
        var valor = parametro.ParameterValue as VariableReference;
        if (parametro.IsOutput && valor != null) Asigna(valor, parametro, AssignmentKind.Equals);
    }

    public override void Visit(ExecuteSpecification ejecucion)
    {
        if (ejecucion.Variable != null) Asigna(ejecucion.Variable, ejecucion, AssignmentKind.Equals);
        if (ejecucion.ExecutableEntity is ExecutableStringList)
        {
            ejecutaDinamico = true;
            foreach (var parte in ((ExecutableStringList)ejecucion.ExecutableEntity).Strings) RevisarConcatenacion(parte, null);
        }
    }

    public override void Visit(VariableReference variable)
    {
        if (ignoradas.Contains(variable.StartOffset)) return;
        usos.Add(Tuple.Create(variable.Name, variable.StartOffset, variable.StartLine));
    }

    public override void Visit(BooleanIsNullExpression expresion)
    {
        var variable = SinParentesis(expresion.Expression) as VariableReference;
        if (variable != null) lecturasNulas.Add(variable.StartOffset);
    }

    public override void Visit(CoalesceExpression expresion)
    {
        var variable = expresion.Expressions.Count > 0 ? SinParentesis(expresion.Expressions[0]) as VariableReference : null;
        if (variable != null) lecturasNulas.Add(variable.StartOffset);
    }

    // --- Texto más largo que la variable / ISNULL que corta -------------------------------------------
    private void RevisarTextoLargo(GenesisDeclaracion declaracion, ScalarExpression valor, int linea)
    {
        var literal = SinParentesis(valor) as StringLiteral;
        if (declaracion == null || literal == null || !TiposTexto.Contains(declaracion.Familia) || declaracion.Largo <= 0) return;
        if (literal.Value.Length > declaracion.Largo)
            Agregar("TEXTO_MAS_LARGO_QUE_VARIABLE", linea, "variable", declaracion.Nombre, "largo", declaracion.Largo,
                    "texto", literal.Value, "queda", literal.Value.Substring(0, declaracion.Largo));
    }

    public override void Visit(FunctionCall funcion)
    {
        string nombre = funcion.FunctionName.Value;
        // ISNULL(columna, ...) fuera de una comparación (en el SELECT, un SET, un IN...): validar si la columna
        // acepta NULL. Las de una comparación se revisan con su condición (RevisarFuncionSobreColumna).
        if (funcion.CallTarget == null && string.Equals(nombre, "ISNULL", StringComparison.OrdinalIgnoreCase)
            && funcion.Parameters.Count == 2 && !isnullRevisados.Contains(funcion.StartOffset))
        {
            var columnaIsnull = SinParentesis(funcion.Parameters[0]) as ColumnReferenceExpression;
            if (columnaIsnull != null) RevisarIsnull(funcion, columnaIsnull, profundidadCondicion > 0 ? "condicion" : "select", "");
        }
        if (funcion.CallTarget == null && string.Equals(nombre, "ISNULL", StringComparison.OrdinalIgnoreCase) && funcion.Parameters.Count == 2)
        {
            var primera = SinParentesis(funcion.Parameters[0]) as VariableReference;
            if (primera != null)
            {
                lecturasNulas.Add(primera.StartOffset);
                var declaracion = Declarada(primera.Name, funcion.StartOffset);
                var literal = SinParentesis(funcion.Parameters[1]) as StringLiteral;
                if (declaracion != null && TiposTexto.Contains(declaracion.Familia) && declaracion.Largo > 0
                    && literal != null && literal.Value.Length > declaracion.Largo)
                    Agregar("ISNULL_TRUNCA", funcion.StartLine, "variable", primera.Name, "largo", declaracion.Largo,
                            "texto", literal.Value, "queda", literal.Value.Substring(0, declaracion.Largo));
            }
        }
        // Función escalar propia (dbo.fn_...) que recibe una columna, dentro de una consulta con FROM: se ejecuta
        // fila por fila. No cuentan los métodos de XML (R.X.value(...)) ni una función que solo recibe variables.
        if (funcion.CallTarget is MultiPartIdentifierCallTarget && !MetodosDeTipos.Contains(nombre)
            && consultasConFrom.Count > 0 && consultasConFrom.Peek() && funcion.Parameters.Any(TieneColumna))
        {
            var objetivo = (MultiPartIdentifierCallTarget)funcion.CallTarget;
            string esquema = string.Join(".", objetivo.MultiPartIdentifier.Identifiers.Select(i => i.Value));
            Agregar("FUNCION_ESCALAR_POR_FILA", funcion.StartLine, "funcion", esquema + "." + nombre);
        }
    }

    // --- Tablas: columna repetida, dos PK, dos IDENTITY, temporal creada dos veces ---------------------
    private void CreaTemporal(SchemaObjectName nombre, int linea)
    {
        string tabla = Nombre(nombre);
        if (!tabla.StartsWith("#")) return;
        int primera;
        if (temporales.TryGetValue(tabla, out primera))
            Agregar("TEMPORAL_CREADA_DOS_VECES", linea, "tabla", tabla, "primera", primera);
        else
            temporales[tabla] = linea;
    }

    public override void Visit(CreateTableStatement tabla)
    {
        CreaTemporal(tabla.SchemaObjectName, tabla.StartLine);
        RevisarDefinicion(Nombre(tabla.SchemaObjectName), tabla.Definition);
    }

    private void RevisarDefinicion(string tabla, TableDefinition definicion)
    {
        if (definicion == null) return;
        var vistas = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        var tipos = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        int primaryKeys = 0, lineaSegundaPk = 0, identidades = 0, lineaSegundaIdentidad = 0;
        var noNulas = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        foreach (var columna in definicion.ColumnDefinitions)
        {
            // NOT NULL, IDENTITY o PRIMARY KEY: la columna nunca tiene NULL.
            bool noNula = columna.IdentityOptions != null || columna.Constraints.Any(r =>
                (r is NullableConstraintDefinition && !((NullableConstraintDefinition)r).Nullable)
                || (r is UniqueConstraintDefinition && ((UniqueConstraintDefinition)r).IsPrimaryKey));
            if (noNula) noNulas[columna.ColumnIdentifier.Value] = columna.StartLine;
            string nombre = columna.ColumnIdentifier.Value;
            int primera;
            if (vistas.TryGetValue(nombre, out primera))
                Agregar("COLUMNA_REPETIDA_EN_TABLA", columna.StartLine, "tabla", tabla, "columna", nombre, "primera", primera);
            else
                vistas[nombre] = columna.StartLine;
            var tipo = new GenesisDeclaracion();
            TipoDe(columna.DataType, tipo);
            tipos[nombre] = tipo.Familia;
            if (columna.IdentityOptions != null && ++identidades == 2) lineaSegundaIdentidad = columna.StartLine;
            foreach (var restriccion in columna.Constraints)
            {
                var unica = restriccion as UniqueConstraintDefinition;
                if (unica != null && unica.IsPrimaryKey && ++primaryKeys == 2) lineaSegundaPk = restriccion.StartLine;
            }
        }
        foreach (var restriccion in definicion.TableConstraints)
        {
            var unica = restriccion as UniqueConstraintDefinition;
            if (unica != null && unica.IsPrimaryKey && ++primaryKeys == 2) lineaSegundaPk = restriccion.StartLine;
            if (unica != null && unica.IsPrimaryKey)
                foreach (var columnaPk in unica.Columns)
                {
                    string nombre = NombreColumna(columnaPk.Column);
                    if (!noNulas.ContainsKey(nombre)) noNulas[nombre] = restriccion.StartLine;
                }
        }
        if (EsTemporal(tabla)) columnasNoNulas[tabla] = noNulas;
        if (primaryKeys > 1) Agregar("DOS_PRIMARY_KEY", lineaSegundaPk, "tabla", tabla, "cantidad", primaryKeys);
        if (identidades > 1) Agregar("DOS_IDENTITY", lineaSegundaIdentidad, "tabla", tabla, "cantidad", identidades);
        if (EsTemporal(tabla)) columnasDeTablas[tabla] = tipos;
    }

    // --- Tipos: mal escritos, tamaños fuera de rango, VARCHAR sin tamaño -----------------------------
    private readonly HashSet<int> tiposDeConversion = new HashSet<int>();

    public override void Visit(CastCall llamada) { if (llamada.DataType != null) tiposDeConversion.Add(llamada.DataType.StartOffset); }
    public override void Visit(ConvertCall llamada) { if (llamada.DataType != null) tiposDeConversion.Add(llamada.DataType.StartOffset); }
    public override void Visit(TryCastCall llamada) { if (llamada.DataType != null) tiposDeConversion.Add(llamada.DataType.StartOffset); }
    public override void Visit(TryConvertCall llamada) { if (llamada.DataType != null) tiposDeConversion.Add(llamada.DataType.StartOffset); }

    public override void Visit(UserDataTypeReference tipo)
    {
        // Un tipo de una sola parte que SQL Server no conoce (VARCHR, DATTIME); en Python se compara con los
        // tipos de SQL Server para no confundirlo con un tipo propio de la base.
        if (tipo.Name != null && tipo.Name.Identifiers.Count == 1)
            Agregar("TIPO_DESCONOCIDO", tipo.StartLine, "tipoDato", tipo.Name.BaseIdentifier.Value);
    }

    public override void Visit(SqlDataTypeReference tipo)
    {
        var opcion = tipo.SqlDataTypeOption;
        string nombre = opcion.ToString().ToUpperInvariant();
        bool largoVariable = opcion == SqlDataTypeOption.VarChar || opcion == SqlDataTypeOption.NVarChar || opcion == SqlDataTypeOption.VarBinary;
        bool largoFijo = opcion == SqlDataTypeOption.Char || opcion == SqlDataTypeOption.NChar || opcion == SqlDataTypeOption.Binary;
        bool enConversion = tiposDeConversion.Contains(tipo.StartOffset);
        if ((largoVariable || largoFijo) && tipo.Parameters.Count == 0)
        {
            // VARCHAR sin tamaño: 1 carácter al declarar y 30 en CAST/CONVERT. CHAR sin tamaño en una columna o
            // variable suele ser a propósito (1 carácter); en CAST/CONVERT no.
            if (largoVariable || enConversion)
                Agregar("VARCHAR_SIN_TAMANO", tipo.StartLine, "tipoDato", nombre, "largo", enConversion ? 30 : 1,
                        "contexto", enConversion ? "conversion" : "declaracion");
            return;
        }
        if (tipo.Parameters.Count == 0 || tipo.Parameters[0] is MaxLiteral) return;
        int primero, segundo = -1;
        if (!int.TryParse(tipo.Parameters[0].Value, out primero)) return;
        if (tipo.Parameters.Count > 1) int.TryParse(tipo.Parameters[1].Value, out segundo);
        if (largoVariable || largoFijo)
        {
            bool unicode = opcion == SqlDataTypeOption.NVarChar || opcion == SqlDataTypeOption.NChar;
            int limite = unicode ? 4000 : 8000;
            if (primero == 0) Agregar("TAMANO_FUERA_DE_RANGO", tipo.StartLine, "tipoDato", nombre, "valor", Texto(tipo), "limite", "mayor que 0", "error", 1001);
            else if (primero > limite) Agregar("TAMANO_FUERA_DE_RANGO", tipo.StartLine, "tipoDato", nombre, "valor", Texto(tipo), "limite", "hasta " + limite + " (o MAX)", "error", unicode ? 2717 : 131);
        }
        else if (opcion == SqlDataTypeOption.Decimal || opcion == SqlDataTypeOption.Numeric)
        {
            if (primero < 1 || primero > 38) Agregar("TAMANO_FUERA_DE_RANGO", tipo.StartLine, "tipoDato", nombre, "valor", Texto(tipo), "limite", "una precisión de 1 a 38", "error", 2717);
            else if (segundo > primero) Agregar("TAMANO_FUERA_DE_RANGO", tipo.StartLine, "tipoDato", nombre, "valor", Texto(tipo), "limite", "una escala que no supere la precisión", "error", 192);
        }
    }

    // --- Consultas -------------------------------------------------------------------------------------
    public override void ExplicitVisit(QuerySpecification consulta)
    {
        var opcionales = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        tablasDelFrom.Push(MapaDelFrom(consulta.FromClause, opcionales));
        opcionalesDelFrom.Push(opcionales);
        consultasConFrom.Push(consulta.FromClause != null);
        base.ExplicitVisit(consulta);
        consultasConFrom.Pop();
        opcionalesDelFrom.Pop();
        tablasDelFrom.Pop();
    }

    public override void ExplicitVisit(UpdateSpecification actualizacion)
    {
        var opcionales = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var mapa = MapaDelFrom(actualizacion.FromClause, opcionales);
        if (actualizacion.Target != null) LlenarMapa(actualizacion.Target, mapa);
        tablasDelFrom.Push(mapa);
        opcionalesDelFrom.Push(opcionales);
        consultasConFrom.Push(false);
        base.ExplicitVisit(actualizacion);
        consultasConFrom.Pop();
        opcionalesDelFrom.Pop();
        tablasDelFrom.Pop();
    }

    public override void ExplicitVisit(DeleteSpecification eliminacion)
    {
        var opcionales = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        var mapa = MapaDelFrom(eliminacion.FromClause, opcionales);
        if (eliminacion.Target != null) LlenarMapa(eliminacion.Target, mapa);
        tablasDelFrom.Push(mapa);
        opcionalesDelFrom.Push(opcionales);
        consultasConFrom.Push(false);
        base.ExplicitVisit(eliminacion);
        consultasConFrom.Pop();
        opcionalesDelFrom.Pop();
        tablasDelFrom.Pop();
    }

    public override void Visit(QuerySpecification consulta)
    {
        var elementos = consulta.SelectElements;
        bool soloAsignaciones = elementos.Count > 0 && elementos.All(e => e is SelectSetVariable);
        bool todoAgregado = elementos.Count > 0 && elementos.All(e => EsElementoAgregado(e));

        // SELECT @x = col FROM T sin WHERE, TOP ni agregado: si trae varias filas, @x queda con cualquiera.
        if (soloAsignaciones && consulta.FromClause != null && consulta.WhereClause == null && consulta.TopRowFilter == null
            && consulta.GroupByClause == null && !todoAgregado)
        {
            var asignaciones = elementos.Cast<SelectSetVariable>().ToList();
            bool acumula = asignaciones.Any(a => a.AssignmentKind != AssignmentKind.Equals
                || Contiene(a.Expression, a.Variable.Name));
            if (!acumula)
                Agregar("ASIGNACION_VARIAS_FILAS", consulta.StartLine, "variable", asignaciones[0].Variable.Name);
        }

        // TOP sin ORDER BY: puede traer una fila distinta en cada ejecución.
        if (consulta.TopRowFilter != null && consulta.OrderByClause == null && consulta.FromClause != null
            && profundidadExists == 0 && !todoAgregado && !consulta.TopRowFilter.WithTies)
            Agregar("TOP_SIN_ORDER_BY", consulta.TopRowFilter.StartLine, "top", Texto(consulta.TopRowFilter));

        // DISTINCT con JOIN: puede estar ocultando filas repetidas por una condición incompleta.
        if (consulta.UniqueRowFilter == UniqueRowFilter.Distinct && consulta.FromClause != null
            && consulta.FromClause.TableReferences.Any(r => r is QualifiedJoin))
            Agregar("DISTINCT_CON_JOIN", consulta.StartLine);

        RevisarSubconsultasRepetidas(consulta);
    }

    private static bool EsElementoAgregado(SelectElement elemento)
    {
        ScalarExpression expresion = null;
        var escalar = elemento as SelectScalarExpression;
        var asignacion = elemento as SelectSetVariable;
        if (escalar != null) expresion = escalar.Expression;
        if (asignacion != null) expresion = asignacion.Expression;
        var funcion = SinParentesis(expresion) as FunctionCall;
        return funcion != null && EsAgregado(funcion) && funcion.OverClause == null;
    }

    // Subconsultas escalares a la misma tabla con la misma condición: se pueden unir en un APPLY.
    private void RevisarSubconsultasRepetidas(QuerySpecification consulta)
    {
        var candidatas = new List<Tuple<string, QuerySpecification, string, int>>();
        int numero = 0;
        foreach (var elemento in consulta.SelectElements.OfType<SelectScalarExpression>())
        {
            var subconsulta = SinParentesis(elemento.Expression) as ScalarSubquery;
            if (subconsulta == null) continue;
            var interna = subconsulta.QueryExpression as QuerySpecification;
            if (interna == null || interna.FromClause == null || interna.WhereClause == null || interna.SelectElements.Count != 1
                || !(interna.SelectElements[0] is SelectScalarExpression)) continue;
            numero++;
            string clave = Normalizado(interna.TopRowFilter) + "|" + Normalizado(interna.FromClause) + "|"
                + Normalizado(interna.WhereClause) + "|" + Normalizado(interna.GroupByClause) + "|" + Normalizado(interna.OrderByClause);
            string alias = elemento.ColumnName != null ? elemento.ColumnName.Value : "cValor" + numero;
            candidatas.Add(Tuple.Create(clave, interna, alias, subconsulta.StartLine));
        }
        foreach (var grupo in candidatas.GroupBy(c => c.Item1).Where(g => g.Count() > 1))
        {
            var primera = grupo.First().Item2;
            bool siempreUnaFila = grupo.All(c => EsElementoAgregado(c.Item2.SelectElements[0])) && primera.GroupByClause == null;
            string apply = siempreUnaFila ? "CROSS APPLY" : "OUTER APPLY";
            var columnas = grupo.Select(c => Texto(((SelectScalarExpression)c.Item2.SelectElements[0]).Expression) + " AS " + c.Item3);
            string ejemplo = apply + " (SELECT " + (primera.TopRowFilter != null ? Texto(primera.TopRowFilter) + " " : "")
                + string.Join(", ", columnas) + " " + Texto(primera.FromClause) + " " + Texto(primera.WhereClause)
                + (primera.GroupByClause != null ? " " + Texto(primera.GroupByClause) : "")
                + (primera.OrderByClause != null ? " " + Texto(primera.OrderByClause) : "") + ") x";
            string tabla = MapaDelFrom(primera.FromClause).Values.FirstOrDefault() ?? "";
            Agregar("SUBCONSULTAS_A_APPLY", grupo.First().Item4, "tabla", tabla, "cantidad", grupo.Count(),
                    "lineas", grupo.Select(c => c.Item4).ToArray(), "apply", apply, "ejemplo", ejemplo);
        }
    }

    public override void ExplicitVisit(ExistsPredicate existe)
    {
        profundidadExists++;
        base.ExplicitVisit(existe);
        profundidadExists--;
    }

    // UNION con distinta cantidad de columnas (205) y UNION sin ALL.
    public override void Visit(BinaryQueryExpression union)
    {
        var izquierda = PrimeraConsulta(union.FirstQueryExpression);
        var derecha = PrimeraConsulta(union.SecondQueryExpression);
        if (izquierda != null && derecha != null && !izquierda.SelectElements.Any(e => e is SelectStarExpression)
            && !derecha.SelectElements.Any(e => e is SelectStarExpression) && izquierda.SelectElements.Count != derecha.SelectElements.Count)
            Agregar("UNION_COLUMNAS_DISTINTAS", derecha.StartLine, "primera", izquierda.SelectElements.Count,
                    "segunda", derecha.SelectElements.Count, "operacion", union.BinaryQueryExpressionType.ToString().ToUpperInvariant());
        if (union.BinaryQueryExpressionType == BinaryQueryExpressionType.Union && !union.All)
            Agregar("UNION_SIN_ALL", derecha != null ? derecha.StartLine : union.StartLine);
    }

    // CTE con otra cantidad de columnas que su lista (8159) y dos CTE con el mismo nombre (239).
    public override void Visit(WithCtesAndXmlNamespaces conCtes)
    {
        var nombres = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        foreach (var cte in conCtes.CommonTableExpressions)
        {
            if (!nombres.Add(cte.ExpressionName.Value))
                Agregar("CTE_NOMBRE_REPETIDO", cte.StartLine, "cte", cte.ExpressionName.Value);
            var consulta = PrimeraConsulta(cte.QueryExpression);
            if (cte.Columns.Count > 0 && consulta != null && !consulta.SelectElements.Any(e => e is SelectStarExpression)
                && consulta.SelectElements.Count != cte.Columns.Count)
                Agregar("CTE_COLUMNAS_DISTINTAS", cte.StartLine, "cte", cte.ExpressionName.Value,
                        "columnas", cte.Columns.Count, "consulta", consulta.SelectElements.Count);
        }
    }

    // ORDER BY dentro de una subconsulta, tabla derivada, CTE o vista sin TOP (1033).
    private void RevisarOrdenSinTop(QueryExpression consulta)
    {
        if (consulta == null || consulta.OrderByClause == null || consulta.OffsetClause != null || consulta.ForClause != null) return;
        var especificacion = consulta as QuerySpecification;
        if (especificacion != null && especificacion.TopRowFilter != null) return;
        Agregar("ORDER_BY_EN_SUBCONSULTA", consulta.OrderByClause.StartLine);
    }

    public override void Visit(ScalarSubquery subconsulta) { RevisarOrdenSinTop(subconsulta.QueryExpression); }
    public override void Visit(QueryDerivedTable derivada) { RevisarOrdenSinTop(derivada.QueryExpression); }
    public override void Visit(CommonTableExpression cte) { RevisarOrdenSinTop(cte.QueryExpression); }
    public override void Visit(ViewStatementBody vista) { if (vista.SelectStatement != null) RevisarOrdenSinTop(vista.SelectStatement.QueryExpression); }

    // --- INSERT ------------------------------------------------------------------------------------------
    public override void Visit(InsertSpecification insert)
    {
        string tabla = "";
        var nombrada = insert.Target as NamedTableReference;
        var variable = insert.Target as VariableTableReference;
        if (nombrada != null) tabla = Nombre(nombrada.SchemaObject);
        else if (variable != null) tabla = variable.Variable.Name;
        var select = insert.InsertSource as SelectInsertSource;
        var consulta = select != null ? select.Select : null;

        // ORDER BY en un INSERT ... SELECT sin TOP: no deja la tabla ordenada y solo consume.
        if (consulta != null && consulta.OrderByClause != null && consulta.OffsetClause == null)
        {
            var especificacion = consulta as QuerySpecification;
            if (especificacion == null || especificacion.TopRowFilter == null)
                Agregar("ORDER_BY_EN_INSERT", consulta.OrderByClause.StartLine, "tabla", tabla);
        }

        int columnas = insert.Columns.Count;
        if (EsTemporal(tabla) && columnas > 0 && consulta is QuerySpecification)
        {
            var especificacion = (QuerySpecification)consulta;
            if (especificacion.SelectElements.Count == columnas)
                for (int i = 0; i < columnas; i++)
                    GuardarOrigen(tabla, NombreColumna(insert.Columns[i]), especificacion.SelectElements[i], especificacion.FromClause);
        }
        if (columnas == 0) return;  // sin lista de columnas se necesitaría la tabla real
        var valores = insert.InsertSource as ValuesInsertSource;
        if (valores != null)
        {
            foreach (var fila in valores.RowValues)
            {
                if (fila.ColumnValues.Count != columnas)
                {
                    Agregar("INSERT_COLUMNAS_NO_COINCIDEN", fila.StartLine, "tabla", tabla, "columnas", columnas,
                            "valores", fila.ColumnValues.Count, "origen", "VALUES");
                    return;
                }
            }
            return;
        }
        var primera = consulta != null ? PrimeraConsulta(consulta) : null;
        if (primera == null || primera.SelectElements.Any(e => e is SelectStarExpression)) return;
        if (primera.SelectElements.Count != columnas)
            Agregar("INSERT_COLUMNAS_NO_COINCIDEN", primera.StartLine, "tabla", tabla, "columnas", columnas,
                    "valores", primera.SelectElements.Count, "origen", "SELECT");
    }

    public override void Visit(SelectStatement sentencia)
    {
        if (sentencia.Into != null) CreaTemporal(sentencia.Into, sentencia.Into.StartLine);
        var especificacion = sentencia.QueryExpression as QuerySpecification;
        string destino = sentencia.Into != null ? Nombre(sentencia.Into) : null;
        if (destino != null && EsTemporal(destino) && especificacion != null)
            foreach (var elemento in especificacion.SelectElements.OfType<SelectScalarExpression>())
            {
                var columna = SinParentesis(elemento.Expression) as ColumnReferenceExpression;
                string nombre = elemento.ColumnName != null ? elemento.ColumnName.Value : columna != null ? NombreColumna(columna) : null;
                if (nombre != null) GuardarOrigen(destino, nombre, elemento, especificacion.FromClause);
            }
        GuardarSentencia(sentencia, "SELECT");
    }

    // La columna de la temporal se llena directo desde una columna de una tabla física (no de un cálculo, una
    // temporal ni el lado opcional de un OUTER JOIN): para el ISNULL se valida esa columna de origen.
    private void GuardarOrigen(string temporal, string columnaTemporal, SelectElement elemento, FromClause from)
    {
        var escalar = elemento as SelectScalarExpression;
        var columna = escalar != null ? SinParentesis(escalar.Expression) as ColumnReferenceExpression : null;
        Tuple<string, string> origen = null;
        if (columna != null && columna.MultiPartIdentifier != null)
        {
            var opcionales = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            var mapa = MapaDelFrom(from, opcionales);
            var partes = columna.MultiPartIdentifier.Identifiers;
            string clave = partes.Count >= 2 ? partes[partes.Count - 2].Value : null;
            string tabla = null;
            if (clave != null) mapa.TryGetValue(clave, out tabla);
            else if (mapa.Values.Distinct(StringComparer.OrdinalIgnoreCase).Count() == 1) { tabla = mapa.Values.First(); clave = mapa.Keys.First(); }
            if (tabla != null && !EsTemporal(tabla) && tabla != "(subconsulta)" && !opcionales.Contains(clave))
                origen = Tuple.Create(tabla, NombreColumna(columna));
        }
        Dictionary<string, Tuple<string, string>> deLaTabla;
        if (!origenes.TryGetValue(temporal, out deLaTabla))
            origenes[temporal] = deLaTabla = new Dictionary<string, Tuple<string, string>>(StringComparer.OrdinalIgnoreCase);
        Tuple<string, string> anterior;
        // Si dos INSERT llenan la columna desde orígenes distintos, ya no se sabe cuál validar.
        if (deLaTabla.TryGetValue(columnaTemporal, out anterior))
        {
            if (anterior == null || origen == null || !string.Equals(anterior.Item1 + "." + anterior.Item2,
                origen.Item1 + "." + origen.Item2, StringComparison.OrdinalIgnoreCase)) deLaTabla[columnaTemporal] = null;
        }
        else deLaTabla[columnaTemporal] = origen;
    }

    public override void Visit(InsertStatement sentencia) { GuardarSentencia(sentencia, "INSERT"); }
    public override void Visit(UpdateStatement sentencia) { GuardarSentencia(sentencia, "UPDATE"); }
    public override void Visit(DeleteStatement sentencia) { GuardarSentencia(sentencia, "DELETE"); }

    // Bloques repetidos: la misma instrucción (de cierto tamaño) escrita dos o más veces en el bloque.
    private void GuardarSentencia(TSqlStatement sentencia, string tipo)
    {
        if (CantidadDeFichas(sentencia) >= 40) sentencias.Add(Tuple.Create(Normalizado(sentencia), sentencia.StartLine, tipo));
    }

    // --- 7. Alias repetido en el mismo FROM (1011) o la misma tabla sin alias dos veces (1013) ----------
    public override void Visit(FromClause from)
    {
        var nombres = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);
        foreach (var referencia in from.TableReferences) RevisarExpuestos(referencia, nombres);
    }

    private void RevisarExpuestos(TableReference referencia, Dictionary<string, bool> nombres)
    {
        var calificado = referencia as QualifiedJoin;
        var sinCalificar = referencia as UnqualifiedJoin;
        var parentesis = referencia as JoinParenthesisTableReference;
        if (calificado != null) { RevisarExpuestos(calificado.FirstTableReference, nombres); RevisarExpuestos(calificado.SecondTableReference, nombres); return; }
        if (sinCalificar != null) { RevisarExpuestos(sinCalificar.FirstTableReference, nombres); RevisarExpuestos(sinCalificar.SecondTableReference, nombres); return; }
        if (parentesis != null) { RevisarExpuestos(parentesis.Join, nombres); return; }

        string expuesto = null;
        bool esAlias = false;
        int linea = referencia.StartLine;
        var conAlias = referencia as TableReferenceWithAlias;
        if (conAlias != null && conAlias.Alias != null)
        {
            expuesto = conAlias.Alias.Value;
            esAlias = true;
            linea = conAlias.Alias.StartLine;
        }
        else if (referencia is NamedTableReference)
        {
            expuesto = Nombre(((NamedTableReference)referencia).SchemaObject);
        }
        else if (referencia is VariableTableReference)
        {
            expuesto = ((VariableTableReference)referencia).Variable.Name;
        }
        if (expuesto == null) return;
        bool primeroEraAlias;
        if (nombres.TryGetValue(expuesto, out primeroEraAlias))
            Agregar("ALIAS_REPETIDO_EN_FROM", linea, "nombre", expuesto, "esAlias", esAlias && primeroEraAlias);
        else
            nombres[expuesto] = esAlias;
    }

    // --- Condiciones (WHERE y ON) ----------------------------------------------------------------------
    public override void ExplicitVisit(WhereClause donde)
    {
        // 147: agregado en el WHERE (fuera de una subconsulta).
        var buscador = new GenesisBuscaAgregado();
        if (donde.SearchCondition != null) donde.SearchCondition.Accept(buscador);
        if (buscador.Linea > 0) Agregar("AGREGADO_EN_WHERE", buscador.Linea);
        RevisarOrEntreColumnas(donde.SearchCondition);
        profundidadCondicion++;
        base.ExplicitVisit(donde);
        profundidadCondicion--;
    }

    public override void ExplicitVisit(QualifiedJoin union)
    {
        union.FirstTableReference.Accept(this);
        union.SecondTableReference.Accept(this);
        if (union.SearchCondition == null) return;
        profundidadCondicion++;
        union.SearchCondition.Accept(this);
        profundidadCondicion--;
    }

    private void RevisarOrEntreColumnas(BooleanExpression condicion)
    {
        var o = SinParentesis(condicion) as BooleanBinaryExpression;
        if (o == null || o.BinaryExpressionType != BooleanBinaryExpressionType.Or) return;
        var izquierda = ColumnaComparada(SinParentesis(o.FirstExpression));
        var derecha = ColumnaComparada(SinParentesis(o.SecondExpression));
        if (izquierda != null && derecha != null && !string.Equals(izquierda, derecha, StringComparison.OrdinalIgnoreCase))
            Agregar("OR_ENTRE_COLUMNAS", condicion.StartLine, "primera", izquierda, "segunda", derecha);
    }

    // «col = valor» (valor: literal o variable): devuelve el nombre de la columna; si no, null.
    private static string ColumnaComparada(BooleanExpression expresion)
    {
        var comparacion = expresion as BooleanComparisonExpression;
        if (comparacion == null) return null;
        var columna = SinParentesis(comparacion.FirstExpression) as ColumnReferenceExpression;
        var valor = SinParentesis(comparacion.SecondExpression);
        if (columna == null || !(valor is Literal || valor is VariableReference)) return null;
        return Texto(columna);
    }

    public override void Visit(BooleanComparisonExpression comparacion)
    {
        var primera = SinParentesis(comparacion.FirstExpression);
        var segunda = SinParentesis(comparacion.SecondExpression);
        var tipo = comparacion.ComparisonType;
        bool igualdad = tipo == BooleanComparisonType.Equals || tipo == BooleanComparisonType.NotEqualToBrackets
            || tipo == BooleanComparisonType.NotEqualToExclamation;

        // = NULL / <> NULL: con ANSI_NULLS (lo normal) nunca es verdadero.
        if (igualdad && (primera is NullLiteral || segunda is NullLiteral))
            Agregar("COMPARACION_CON_NULL", comparacion.StartLine, "comparacion", Texto(comparacion),
                    "negada", tipo != BooleanComparisonType.Equals);

        RevisarConteo(primera, segunda, tipo, comparacion);
        RevisarConteo(segunda, primera, Espejo(tipo), comparacion);

        if (profundidadCondicion == 0) return;
        RevisarFuncionSobreColumna(primera, segunda, tipo, comparacion);
        RevisarFuncionSobreColumna(segunda, primera, Espejo(tipo), comparacion);
        RevisarConversion(primera, segunda, comparacion);
        RevisarConversion(segunda, primera, comparacion);
    }

    private static BooleanComparisonType Espejo(BooleanComparisonType tipo)
    {
        switch (tipo)
        {
            case BooleanComparisonType.GreaterThan: return BooleanComparisonType.LessThan;
            case BooleanComparisonType.LessThan: return BooleanComparisonType.GreaterThan;
            case BooleanComparisonType.GreaterThanOrEqualTo: return BooleanComparisonType.LessThanOrEqualTo;
            case BooleanComparisonType.LessThanOrEqualTo: return BooleanComparisonType.GreaterThanOrEqualTo;
            default: return tipo;
        }
    }

    // (SELECT COUNT(*) ...) > 0  ->  EXISTS (...); = 0  ->  NOT EXISTS (...).
    private void RevisarConteo(ScalarExpression lado, ScalarExpression otro, BooleanComparisonType tipo, TSqlFragment comparacion)
    {
        var subconsulta = lado as ScalarSubquery;
        var numero = otro as IntegerLiteral;
        if (subconsulta == null || numero == null) return;
        var consulta = subconsulta.QueryExpression as QuerySpecification;
        if (consulta == null || consulta.GroupByClause != null || consulta.SelectElements.Count != 1) return;
        var elemento = consulta.SelectElements[0] as SelectScalarExpression;
        var funcion = elemento != null ? SinParentesis(elemento.Expression) as FunctionCall : null;
        if (funcion == null || funcion.CallTarget != null
            || !(string.Equals(funcion.FunctionName.Value, "COUNT", StringComparison.OrdinalIgnoreCase)
                 || string.Equals(funcion.FunctionName.Value, "COUNT_BIG", StringComparison.OrdinalIgnoreCase))) return;
        string valor = numero.Value;
        bool existe = (valor == "0" && (tipo == BooleanComparisonType.GreaterThan || tipo == BooleanComparisonType.NotEqualToBrackets
                        || tipo == BooleanComparisonType.NotEqualToExclamation))
                      || (valor == "1" && tipo == BooleanComparisonType.GreaterThanOrEqualTo);
        bool noExiste = (valor == "0" && tipo == BooleanComparisonType.Equals) || (valor == "1" && tipo == BooleanComparisonType.LessThan);
        if (existe || noExiste)
            Agregar("COUNT_EN_LUGAR_DE_EXISTS", comparacion.StartLine, "comparacion", Texto(comparacion),
                    "propuesta", noExiste ? "NOT EXISTS" : "EXISTS");
    }

    private static string Operador(BooleanComparisonType tipo)
    {
        switch (tipo)
        {
            case BooleanComparisonType.Equals: return "=";
            case BooleanComparisonType.GreaterThan: return ">";
            case BooleanComparisonType.LessThan: return "<";
            case BooleanComparisonType.GreaterThanOrEqualTo: return ">=";
            case BooleanComparisonType.LessThanOrEqualTo: return "<=";
            default: return "<>";
        }
    }

    // `lado` tiene la función; `otro` es lo que se compara; `tipo`, el operador visto desde `lado`.
    private void RevisarFuncionSobreColumna(ScalarExpression lado, ScalarExpression otro, BooleanComparisonType tipo,
                                            TSqlFragment comparacion)
    {
        string funcion = null;
        ColumnReferenceExpression columna = null;
        var llamada = lado as FunctionCall;
        if (llamada != null && llamada.CallTarget == null && FuncionesSobreColumna.Contains(llamada.FunctionName.Value))
        {
            funcion = llamada.FunctionName.Value.ToUpperInvariant();
            columna = llamada.Parameters.Select(p => SinParentesis(p) as ColumnReferenceExpression).FirstOrDefault(c => c != null);
        }
        var cast = lado as CastCall;
        var convert = lado as ConvertCall;
        if (cast != null) { funcion = "CAST"; columna = SinParentesis(cast.Parameter) as ColumnReferenceExpression; }
        if (convert != null) { funcion = "CONVERT"; columna = SinParentesis(convert.Parameter) as ColumnReferenceExpression; }
        if (funcion == null || columna == null) return;
        // ISNULL(col, r) op v: sin la función queda «(col op v OR col IS NULL)» si r es el mismo valor, o
        // «(col op v OR (col IS NULL AND r op v))» en general; así no se pierden las filas con NULL.
        string ejemplo = "";
        if (funcion == "ISNULL" && llamada.Parameters.Count == 2)
        {
            string col = Texto(columna), op = Operador(tipo), valor = Texto(otro), reemplazo = Texto(llamada.Parameters[1]);
            ejemplo = reemplazo == valor && op == "="
                ? "(" + col + " = " + valor + " OR " + col + " IS NULL)"
                : "(" + col + " " + op + " " + valor + " OR (" + col + " IS NULL AND " + reemplazo + " " + op + " " + valor + "))";
        }
        if (funcion == "ISNULL")
        {
            // Primero se valida si la columna acepta NULL (con la consulta); si no se puede saber de qué tabla
            // física es, queda como función sobre la columna.
            isnullRevisados.Add(llamada.StartOffset);
            if (RevisarIsnull(llamada, columna, "condicion", ejemplo)) return;
        }
        if (EsTemporal(TablaDe(columna))) return;
        Agregar("FUNCION_SOBRE_COLUMNA", comparacion.StartLine, "funcion", funcion, "columna", Texto(columna),
                "expresion", Texto(lado), "comparacion", Texto(comparacion), "ejemplo", ejemplo);
    }

    // ISNULL sobre una columna: si es de una tabla física (o de una temporal que se llena desde una), se pide
    // validar si acepta NULL con una consulta; si es de una temporal definida NOT NULL, ya se sabe que sobra.
    // No se marca la columna del lado opcional de un OUTER JOIN: ahí el NULL llega aunque la tabla no lo tenga.
    private bool RevisarIsnull(FunctionCall isnull, ColumnReferenceExpression columna, string contexto, string ejemplo)
    {
        bool opcional;
        string tabla = TablaDe(columna, out opcional);
        if (tabla == null || opcional || tabla == "(subconsulta)") return false;
        string nombre = NombreColumna(columna);
        string tipo = contexto == "condicion" ? "ISNULL_EN_CONDICION" : "ISNULL_VALIDAR_NULOS";
        if (!EsTemporal(tabla))
        {
            Agregar(tipo, isnull.StartLine, "tabla", tabla, "columna", nombre, "expresion", Texto(isnull), "ejemplo", ejemplo);
            return true;
        }
        Dictionary<string, int> noNulas;
        int lineaDefinicion;
        if (columnasNoNulas.TryGetValue(tabla, out noNulas) && noNulas.TryGetValue(nombre, out lineaDefinicion))
        {
            Agregar("ISNULL_EN_COLUMNA_NOT_NULL", isnull.StartLine, "tabla", tabla, "columna", nombre,
                    "expresion", Texto(isnull), "definicion", lineaDefinicion, "contexto", contexto);
            return true;
        }
        Dictionary<string, Tuple<string, string>> deLaTabla;
        Tuple<string, string> origen;
        if (origenes.TryGetValue(tabla, out deLaTabla) && deLaTabla.TryGetValue(nombre, out origen) && origen != null)
        {
            Agregar(tipo, isnull.StartLine, "tabla", origen.Item1, "columna", origen.Item2, "expresion", Texto(isnull),
                    "ejemplo", ejemplo, "temporal", tabla, "columnaTemporal", nombre);
            return true;
        }
        return false;
    }

    // Conversión implícita previsible: la columna de texto se convierte para compararla con un número o con
    // un NVARCHAR, y entonces no se puede usar su índice.
    private void RevisarConversion(ScalarExpression ladoColumna, ScalarExpression otro, TSqlFragment comparacion)
    {
        var columna = ladoColumna as ColumnReferenceExpression;
        if (columna == null) return;
        string tabla = TablaDe(columna);
        string nombre = NombreColumna(columna);
        string familia = null;
        Dictionary<string, string> tipos = null;
        // El tipo exacto solo se conoce en las temporales del script; en una tabla real el prefijo c dice que es
        // texto, pero no si es VARCHAR o NVARCHAR: ahí solo se observa la comparación con un número.
        bool tipoConocido = tabla != null && columnasDeTablas.TryGetValue(tabla, out tipos);
        if (tipoConocido) tipos.TryGetValue(nombre, out familia);
        else if (!EsTemporal(tabla) && Regex.IsMatch(nombre, "^c[A-Z]")) familia = "texto";
        if (familia != "varchar" && familia != "char" && familia != "texto") return;

        string otroTipo = null;
        var variable = otro as VariableReference;
        var literal = otro as StringLiteral;
        if (otro is IntegerLiteral || otro is NumericLiteral) otroTipo = "número";
        else if (literal != null && literal.IsNational && familia != "texto") otroTipo = "NVARCHAR";
        else if (variable != null)
        {
            var declaracion = Declarada(variable.Name, variable.StartOffset);
            if (declaracion != null && TiposNumero.Contains(declaracion.Familia)) otroTipo = declaracion.Familia.ToUpperInvariant();
            else if (declaracion != null && familia != "texto" && (declaracion.Familia == "nvarchar" || declaracion.Familia == "nchar"))
                otroTipo = declaracion.Familia.ToUpperInvariant();
        }
        if (otroTipo != null)
            Agregar("CONVERSION_PREVISIBLE", comparacion.StartLine, "columna", Texto(columna), "otro", Texto(otro), "tipoDato", otroTipo);
    }

    public override void Visit(InPredicate predicado)
    {
        if (predicado.NotDefined && predicado.Subquery != null)
            Agregar("NOT_IN_SUBCONSULTA", predicado.StartLine, "expresion", Texto(predicado.Expression));
    }

    public override void Visit(LikePredicate predicado)
    {
        var columna = SinParentesis(predicado.FirstExpression) as ColumnReferenceExpression;
        var patron = SinParentesis(predicado.SecondExpression) as StringLiteral;
        if (columna != null && patron != null && patron.Value.StartsWith("%") && !EsTemporal(TablaDe(columna)))
            Agregar("LIKE_COMODIN_INICIO", predicado.StartLine, "columna", Texto(columna), "patron", patron.Value);
    }

    // BETWEEN con una fecha sin hora sobre un DATETIME: se pierde el último día después de las 00:00.
    public override void Visit(BooleanTernaryExpression rango)
    {
        if (rango.TernaryExpressionType != BooleanTernaryExpressionType.Between) return;
        string familia = null;
        var variable = SinParentesis(rango.FirstExpression) as VariableReference;
        var columna = SinParentesis(rango.FirstExpression) as ColumnReferenceExpression;
        if (variable != null)
        {
            var declaracion = Declarada(variable.Name, variable.StartOffset);
            if (declaracion != null) familia = declaracion.Familia;
        }
        else if (columna != null)
        {
            Dictionary<string, string> tipos;
            string tabla = TablaDe(columna);
            if (tabla != null && columnasDeTablas.TryGetValue(tabla, out tipos)) tipos.TryGetValue(NombreColumna(columna), out familia);
        }
        if (familia == null || !TiposFecha.Contains(familia)) return;
        var fin = SinParentesis(rango.ThirdExpression);
        var literal = fin as StringLiteral;
        var hasta = fin as VariableReference;
        bool soloFecha = literal != null && SoloFecha.IsMatch(literal.Value);
        if (hasta != null)
        {
            var declaracion = Declarada(hasta.Name, hasta.StartOffset);
            soloFecha = declaracion != null && declaracion.Familia == "date";
        }
        if (soloFecha)
            Agregar("BETWEEN_FECHA_SIN_HORA", rango.StartLine, "expresion", Texto(rango.FirstExpression), "hasta", Texto(fin));
    }

    // --- Variables de sistema y división ----------------------------------------------------------------
    public override void Visit(GlobalVariableExpression variable)
    {
        if (string.Equals(variable.Name, "@@IDENTITY", StringComparison.OrdinalIgnoreCase))
            Agregar("USO_ARROBA_IDENTITY", variable.StartLine);
    }

    public override void ExplicitVisit(SearchedCaseExpression caso) { RevisarCaseSinElse(caso, caso.ElseExpression); profundidadCase++; base.ExplicitVisit(caso); profundidadCase--; }
    public override void ExplicitVisit(SimpleCaseExpression caso)
    {
        RevisarCaseSinElse(caso, caso.ElseExpression);
        foreach (var cuando in caso.WhenClauses)
            if (SinParentesis(cuando.WhenExpression) is NullLiteral)
                Agregar("COMPARACION_CON_NULL", cuando.StartLine, "comparacion", Texto(caso.InputExpression) + " WHEN NULL", "negada", false);
        profundidadCase++;
        base.ExplicitVisit(caso);
        profundidadCase--;
    }
    public override void ExplicitVisit(IIfCall llamada) { profundidadCase++; base.ExplicitVisit(llamada); profundidadCase--; }

    private void RevisarCaseSinElse(TSqlFragment caso, ScalarExpression sino)
    {
        if (sino == null) Agregar("CASE_SIN_ELSE", caso.StartLine);
    }

    public override void Visit(BinaryExpression expresion)
    {
        if (expresion.BinaryExpressionType != BinaryExpressionType.Divide || profundidadCase > 0) return;
        var divisor = SinParentesis(expresion.SecondExpression);
        if (divisor is Literal) return;
        var funcion = divisor as FunctionCall;
        if (funcion != null && string.Equals(funcion.FunctionName.Value, "NULLIF", StringComparison.OrdinalIgnoreCase)) return;
        if (!Contiene(divisor, "@") && !(divisor is ColumnReferenceExpression) && !(divisor is VariableReference) && !(divisor is FunctionCall)
            && !(divisor is BinaryExpression)) return;
        Agregar("DIVISION_SIN_NULLIF", expresion.StartLine, "expresion", Texto(expresion), "divisor", Texto(divisor));
    }

    // --- Control de flujo y transacciones -----------------------------------------------------------------
    public override void ExplicitVisit(IfStatement si)
    {
        // Un ELSE IF no es un nivel más de anidamiento.
        bool guarda = Contiene(si.Predicate, "@@TRANCOUNT", "XACT_STATE");
        if (guarda) profundidadGuarda++;
        si.Predicate.Accept(this);
        Anidar(si.StartLine, +1);
        si.ThenStatement.Accept(this);
        if (si.ElseStatement is IfStatement) { Anidar(0, -1); si.ElseStatement.Accept(this); }
        else { if (si.ElseStatement != null) si.ElseStatement.Accept(this); Anidar(0, -1); }
        if (guarda) profundidadGuarda--;
    }

    public override void ExplicitVisit(WhileStatement mientras)
    {
        mientras.Predicate.Accept(this);
        profundidadWhile++;
        Anidar(mientras.StartLine, +1);
        mientras.Statement.Accept(this);
        Anidar(0, -1);
        profundidadWhile--;
    }

    private void Anidar(int linea, int paso)
    {
        profundidadAnidamiento += paso;
        if (paso > 0 && profundidadAnidamiento == 4 && !anidamientoAvisado)
        {
            anidamientoAvisado = true;
            Agregar("ANIDAMIENTO_EXCESIVO", linea, "niveles", profundidadAnidamiento);
        }
    }

    public override void Visit(BreakStatement salida) { if (profundidadWhile == 0) Agregar("BREAK_FUERA_DE_WHILE", salida.StartLine, "instruccion", "BREAK"); }
    public override void Visit(ContinueStatement salida) { if (profundidadWhile == 0) Agregar("BREAK_FUERA_DE_WHILE", salida.StartLine, "instruccion", "CONTINUE"); }
    public override void Visit(LabelStatement etiqueta) { etiquetas.Add(etiqueta.Value.TrimEnd(':')); }
    public override void Visit(GoToStatement salto) { etiquetasGoto.Add(Tuple.Create(salto.LabelName.Value, salto.StartLine)); }

    // BEGIN TRAN justo antes de BEGIN TRY (patrón de los scripts de pase): la transacción ya está abierta
    // cuando entra al TRY, así que el BEGIN TRAN está protegido y el ROLLBACK de su CATCH es seguro.
    private readonly HashSet<int> transaccionesProtegidas = new HashSet<int>();
    private readonly HashSet<int> intentosConTransaccion = new HashSet<int>();
    private int profundidadCatchProtegido;

    public override void ExplicitVisit(TryCatchStatement intento)
    {
        bool protegido = intentosConTransaccion.Contains(intento.StartOffset);
        profundidadTry++;
        intento.TryStatements.Accept(this);
        profundidadTry--;
        profundidadCatch++;
        if (protegido) profundidadCatchProtegido++;
        intento.CatchStatements.Accept(this);
        if (protegido) profundidadCatchProtegido--;
        profundidadCatch--;
    }

    public override void Visit(PredicateSetStatement opcion)
    {
        if ((opcion.Options & SetOptions.XactAbort) == SetOptions.XactAbort && opcion.IsOn) xactAbort = true;
    }

    public override void Visit(BeginTransactionStatement inicio)
    {
        if (profundidadTry == 0 && !xactAbort && !transaccionesProtegidas.Contains(inicio.StartOffset))
            Agregar("TRANSACCION_SIN_TRY", inicio.StartLine);
    }

    public override void Visit(RollbackTransactionStatement deshacer)
    {
        if (profundidadCatch > 0 && profundidadGuarda == 0 && profundidadCatchProtegido == 0)
            Agregar("ROLLBACK_SIN_VALIDAR", deshacer.StartLine);
    }

    // --- Listas de instrucciones: «;», @@ROWCOUNT y código después de RETURN -----------------------------
    public override void Visit(StatementList lista) { RevisarLista(lista.Statements); }

    private void RevisarLista(IList<TSqlStatement> lista)
    {
        for (int i = 0; i + 1 < lista.Count; i++)
        {
            if (lista[i] is BeginTransactionStatement && lista[i + 1] is TryCatchStatement)
            {
                transaccionesProtegidas.Add(lista[i].StartOffset);
                intentosConTransaccion.Add(lista[i + 1].StartOffset);
            }
        }
        for (int i = 1; i < lista.Count; i++)
        {
            var sentencia = lista[i];
            var anterior = lista[i - 1];
            var conCte = sentencia as StatementWithCtesAndXmlNamespaces;
            string instruccion = null;
            if (conCte != null && conCte.WithCtesAndXmlNamespaces != null) instruccion = "WITH";
            else if (sentencia is ThrowStatement) instruccion = "THROW";
            if (instruccion != null && !TerminaEnPuntoYComa(anterior))
                Agregar("PUNTO_Y_COMA_FALTANTE", sentencia.StartLine, "instruccion", instruccion, "anterior", anterior.StartLine);

            // @@ROWCOUNT / @@ERROR justo después de un SET, DECLARE o PRINT: ya no son los del INSERT/UPDATE.
            TSqlFragment dondeSeLee = sentencia is IfStatement ? (TSqlFragment)((IfStatement)sentencia).Predicate
                : sentencia is WhileStatement ? (TSqlFragment)((WhileStatement)sentencia).Predicate
                : sentencia is BeginEndBlockStatement ? null : sentencia;
            if (dondeSeLee != null && Contiene(dondeSeLee, "@@ROWCOUNT", "@@ERROR")
                && (anterior is SetVariableStatement || anterior is DeclareVariableStatement || anterior is PrintStatement))
                Agregar("ROWCOUNT_DESPUES_DE_OTRA", sentencia.StartLine, "variable",
                        Contiene(dondeSeLee, "@@ROWCOUNT") ? "@@ROWCOUNT" : "@@ERROR", "anterior", anterior.StartLine);

            if (anterior is ReturnStatement && !(sentencia is LabelStatement))
            {
                Agregar("CODIGO_INALCANZABLE", sentencia.StartLine, "retorno", anterior.StartLine);
                break;
            }
        }
    }

    private static bool TerminaEnPuntoYComa(TSqlFragment sentencia)
    {
        var fichas = sentencia.ScriptTokenStream;
        if (fichas == null || sentencia.LastTokenIndex < 0) return true;
        if (fichas[sentencia.LastTokenIndex].TokenType == TSqlTokenType.Semicolon) return true;
        for (int j = sentencia.LastTokenIndex + 1; j < fichas.Count; j++)
        {
            var tipo = fichas[j].TokenType;
            if (tipo == TSqlTokenType.WhiteSpace || tipo == TSqlTokenType.SingleLineComment
                || tipo == TSqlTokenType.MultilineComment) continue;
            return tipo == TSqlTokenType.Semicolon;
        }
        return true;
    }

    // SELECT 2 seguido de THROW sin «;»: SQL Server toma THROW como nombre de columna y el error no se relanza.
    public override void Visit(SelectScalarExpression elemento)
    {
        if (elemento.ColumnName == null || elemento.ColumnName.Identifier == null) return;
        var alias = elemento.ColumnName.Identifier;
        if (alias.QuoteType == QuoteType.NotQuoted && string.Equals(alias.Value, "THROW", StringComparison.OrdinalIgnoreCase))
            Agregar("THROW_TOMADO_COMO_ALIAS", alias.StartLine);
    }

    // --- Seguridad --------------------------------------------------------------------------------------
    // SQL dinámico armado concatenando un parámetro de texto: riesgo de inyección (se avisa si se ejecuta).
    private void RevisarConcatenacion(ScalarExpression expresion, string destino)
    {
        var partes = new List<ScalarExpression>();
        Partes(expresion, partes);
        if (partes.Count < 2) return;
        bool tieneSql = partes.OfType<StringLiteral>().Any(l => PalabrasSql.IsMatch(l.Value));
        if (!tieneSql) return;
        foreach (var variable in partes.OfType<VariableReference>())
        {
            var declaracion = Declarada(variable.Name, variable.StartOffset);
            if (declaracion != null && declaracion.EsParametro && TiposTexto.Contains(declaracion.Familia))
            {
                concatenaciones.Add(Tuple.Create(expresion.StartLine, variable.Name));
                return;
            }
        }
    }

    private static void Partes(ScalarExpression expresion, List<ScalarExpression> partes)
    {
        expresion = SinParentesis(expresion);
        var suma = expresion as BinaryExpression;
        if (suma != null && suma.BinaryExpressionType == BinaryExpressionType.Add)
        {
            Partes(suma.FirstExpression, partes);
            Partes(suma.SecondExpression, partes);
        }
        else if (expresion != null) partes.Add(expresion);
    }

    public override void Visit(ExecutableProcedureReference referencia)
    {
        if (referencia.ProcedureReference == null || referencia.ProcedureReference.ProcedureReference == null) return;
        string nombre = referencia.ProcedureReference.ProcedureReference.Name.BaseIdentifier.Value;
        if (string.Equals(nombre, "sp_executesql", StringComparison.OrdinalIgnoreCase)) ejecutaDinamico = true;
        if (string.Equals(nombre, "xp_cmdshell", StringComparison.OrdinalIgnoreCase)) Agregar("XP_CMDSHELL", referencia.StartLine);
    }

    public override void Visit(StringLiteral literal)
    {
        if (Credencial.IsMatch(literal.Value)) Agregar("CREDENCIAL_EN_CODIGO", literal.StartLine);
    }

    public override void Visit(CreateLoginStatement login) { Agregar("CREDENCIAL_EN_CODIGO", login.StartLine); }

    // --- Mantenibilidad -------------------------------------------------------------------------------
    public override void Visit(ProcedureStatementBody procedimiento)
    {
        int ultima = procedimiento.ScriptTokenStream[procedimiento.LastTokenIndex].Line;
        int lineas = ultima - procedimiento.StartLine + 1;
        if (lineas > 500) Agregar("PROCEDIMIENTO_MUY_LARGO", procedimiento.StartLine, "lineas", lineas);
    }
}
