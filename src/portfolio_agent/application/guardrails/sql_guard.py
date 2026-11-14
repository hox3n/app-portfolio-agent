"""SQL validation: one read-only query over allowed tables, with an enforced row LIMIT."""

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

ALLOWED_TABLES = frozenset({"app_metrics"})
MAX_SQL_CHARS = 2000

FORBIDDEN_NODES: tuple[type[exp.Expression], ...] = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Merge,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Copy,
    exp.Set,
    exp.Pragma,
    exp.Attach,
    exp.Detach,
    exp.Use,
    exp.Install,
    exp.Export,
    exp.Describe,
    exp.Command,
    exp.Into,
)

# Defense in depth: DuckDB also blocks file access, but these never belong in an analytics query.
FORBIDDEN_FUNCTION_PREFIXES = (
    "read_",
    "write_",
    "glob",
    "getenv",
    "query",
    "sniff_",
    "parquet_",
    "duckdb_",
    "pragma_",
    "current_setting",
    "json_execute",
    "load",
    "install",
)


class SqlGuardError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _function_name(node: exp.Func) -> str:
    return (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()


def _check_tables(tree: exp.Query, allowed_tables: frozenset[str]) -> None:

    cte_names = {cte.alias_or_name.lower() for cte in tree.find_all(exp.CTE)}
    for table in tree.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            raise SqlGuardError("function_not_allowed", "table functions are not allowed")

        if table.db or table.catalog:
            raise SqlGuardError(
                "table_not_allowed", f"qualified table names are not allowed: {table.sql()}"
            )
        name = table.name.lower()

        if name not in allowed_tables and name not in cte_names:
            allowed = ", ".join(sorted(allowed_tables))

            raise SqlGuardError(
                "table_not_allowed", f"unknown table '{table.name}'; allowed: {allowed}"
            )


def _apply_limit(tree: exp.Query, max_rows: int) -> exp.Query:

    limit = tree.args.get("limit")
    value = limit.expression if isinstance(limit, exp.Limit) else None

    if isinstance(value, exp.Literal) and value.is_int and int(value.this) <= max_rows:
        return tree

    return tree.limit(max_rows)


def validate_select(
    sql: str, max_rows: int, allowed_tables: frozenset[str] = ALLOWED_TABLES
) -> str:

    if not sql.strip():
        raise SqlGuardError("empty_sql", "SQL is empty")

    if len(sql) > MAX_SQL_CHARS:
        raise SqlGuardError("sql_too_long", f"SQL is longer than {MAX_SQL_CHARS} characters")

    try:
        statements = [s for s in sqlglot.parse(sql, read="duckdb") if s is not None]
    except SqlglotError as e:
        raise SqlGuardError("parse_error", f"could not parse SQL: {e}") from e
    if len(statements) != 1:
        raise SqlGuardError("multiple_statements", "exactly one statement is allowed")

    tree = statements[0]
    if not isinstance(tree, exp.Query):
        raise SqlGuardError(
            "not_select", f"only SELECT queries are allowed, got {tree.key.upper()}"
        )

    for node in tree.walk():
        if isinstance(node, FORBIDDEN_NODES):
            raise SqlGuardError("forbidden_operation", f"{node.key.upper()} is not allowed")
        if isinstance(node, exp.Func) and _function_name(node).startswith(
            FORBIDDEN_FUNCTION_PREFIXES
        ):
            raise SqlGuardError(
                "function_not_allowed", f"function {_function_name(node)}() is not allowed"
            )

    _check_tables(tree, allowed_tables)
    return _apply_limit(tree, max_rows).sql(dialect="duckdb")
