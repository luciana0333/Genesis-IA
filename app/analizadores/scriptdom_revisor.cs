// Revisor de Genesis sobre el árbol de ScriptDom (el código ya desarmado como lo entiende SQL Server).
// PowerShell lo compila una sola vez al abrir (Add-Type, C# 5 de .NET Framework: sin $"..." ni ?.).
// Devuelve hechos (tipo, línea y datos); los mensajes se redactan en Python (scriptdom.py).
//
// Cada caso se comprobó en SQL Server: el script falla con el error indicado.
using System;
using System.Collections.Generic;
using System.Linq;
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

public class GenesisVisitante : TSqlFragmentVisitor
{
    public readonly List<Dictionary<string, object>> Hallazgos = new List<Dictionary<string, object>>();
    // Tablas temporales creadas en el bloque actual (entre GO): nombre -> línea de la primera creación.
    private Dictionary<string, int> temporales = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);

    private void Agregar(string tipo, int linea, params object[] pares)
    {
        var hallazgo = new Dictionary<string, object>();
        hallazgo["tipo"] = tipo;
        hallazgo["linea"] = linea;
        for (int i = 0; i + 1 < pares.Length; i += 2) hallazgo[(string)pares[i]] = pares[i + 1];
        Hallazgos.Add(hallazgo);
    }

    private static string Nombre(SchemaObjectName nombre)
    {
        if (nombre == null) return "";
        return string.Join(".", nombre.Identifiers.Select(i => i.Value));
    }

    // --- 5. Misma tabla temporal creada dos veces en un bloque (error 2714), aunque haya DROP en medio,
    //        esté en un IF / ELSE o se cree con SELECT INTO.
    public override void ExplicitVisit(TSqlBatch lote)
    {
        temporales = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        RevisarPuntoYComa(lote.Statements);
        base.ExplicitVisit(lote);
    }

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

    public override void Visit(SelectStatement sentencia)
    {
        if (sentencia.Into != null) CreaTemporal(sentencia.Into, sentencia.Into.StartLine);
    }

    // --- 4. Columna repetida (2705) y 6. dos PRIMARY KEY (8110), en CREATE TABLE y en DECLARE @T TABLE.
    public override void Visit(CreateTableStatement tabla)
    {
        CreaTemporal(tabla.SchemaObjectName, tabla.StartLine);
        RevisarDefinicion(Nombre(tabla.SchemaObjectName), tabla.Definition);
    }

    public override void Visit(DeclareTableVariableBody tabla)
    {
        RevisarDefinicion(tabla.VariableName != null ? tabla.VariableName.Value : "", tabla.Definition);
    }

    private void RevisarDefinicion(string tabla, TableDefinition definicion)
    {
        if (definicion == null) return;
        var vistas = new Dictionary<string, int>(StringComparer.OrdinalIgnoreCase);
        int primaryKeys = 0;
        int lineaSegundaPk = 0;
        foreach (var columna in definicion.ColumnDefinitions)
        {
            string nombre = columna.ColumnIdentifier.Value;
            int primera;
            if (vistas.TryGetValue(nombre, out primera))
                Agregar("COLUMNA_REPETIDA_EN_TABLA", columna.StartLine, "tabla", tabla, "columna", nombre, "primera", primera);
            else
                vistas[nombre] = columna.StartLine;
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
        }
        if (primaryKeys > 1) Agregar("DOS_PRIMARY_KEY", lineaSegundaPk, "tabla", tabla, "cantidad", primaryKeys);
    }

    // --- 3. INSERT con distinta cantidad de columnas y de valores (109 / 110) o de columnas del SELECT (120 / 121).
    public override void Visit(InsertSpecification insert)
    {
        int columnas = insert.Columns.Count;
        if (columnas == 0) return;  // sin lista de columnas se necesitaría la tabla real
        string tabla = "";
        var nombrada = insert.Target as NamedTableReference;
        var variable = insert.Target as VariableTableReference;
        if (nombrada != null) tabla = Nombre(nombrada.SchemaObject);
        else if (variable != null) tabla = variable.Variable.Name;

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
        var select = insert.InsertSource as SelectInsertSource;
        if (select == null) return;
        var consulta = PrimeraConsulta(select.Select);
        if (consulta == null || consulta.SelectElements.Any(e => e is SelectStarExpression)) return;
        if (consulta.SelectElements.Count != columnas)
            Agregar("INSERT_COLUMNAS_NO_COINCIDEN", consulta.StartLine, "tabla", tabla, "columnas", columnas,
                    "valores", consulta.SelectElements.Count, "origen", "SELECT");
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

    // --- 7. Alias repetido en el mismo FROM (1011) o la misma tabla sin alias dos veces (1013).
    //        Cada FROM es su propio ámbito: el mismo alias en una subconsulta es válido.
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

    // --- 8. «;» faltante: un WITH (CTE) o un THROW después de una instrucción sin «;» en el mismo bloque
    //        (319 / 102). Si es lo primero tras BEGIN, AS, IF, ELSE o BEGIN TRY, es válido.
    public override void Visit(StatementList lista)
    {
        RevisarPuntoYComa(lista.Statements);
    }

    private void RevisarPuntoYComa(IList<TSqlStatement> sentencias)
    {
        for (int i = 1; i < sentencias.Count; i++)
        {
            var sentencia = sentencias[i];
            var conCte = sentencia as StatementWithCtesAndXmlNamespaces;
            string instruccion = null;
            if (conCte != null && conCte.WithCtesAndXmlNamespaces != null) instruccion = "WITH";
            else if (sentencia is ThrowStatement) instruccion = "THROW";
            if (instruccion != null && !TerminaEnPuntoYComa(sentencias[i - 1]))
                Agregar("PUNTO_Y_COMA_FALTANTE", sentencia.StartLine, "instruccion", instruccion,
                        "anterior", sentencias[i - 1].StartLine);
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

    // --- 8b. SELECT 2 seguido de THROW sin «;»: SQL Server toma THROW como nombre de columna y el error
    //         no se relanza (no falla: se pierde en silencio).
    public override void Visit(SelectScalarExpression elemento)
    {
        if (elemento.ColumnName == null || elemento.ColumnName.Identifier == null) return;
        var alias = elemento.ColumnName.Identifier;
        if (alias.QuoteType == QuoteType.NotQuoted && string.Equals(alias.Value, "THROW", StringComparison.OrdinalIgnoreCase))
            Agregar("THROW_TOMADO_COMO_ALIAS", alias.StartLine);
    }
}
