"""PostgreSQL public-schema isolation for the server-owned application data.

The application talks to PostgreSQL directly as the owner of its tables.  It
does not use Supabase's public Data API for application rows.  RLS is therefore
enabled (but deliberately not forced) and the API-facing Supabase roles are
stripped of table and sequence privileges.  A table owner keeps PostgreSQL's
normal direct access while an accidentally enabled Data API remains unable to
read or mutate application data.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from sqlalchemy import bindparam, text
from sqlalchemy.engine import Connection


SUPABASE_API_ROLES = ("anon", "authenticated", "service_role")


_ENABLE_PUBLIC_TABLE_RLS_SQL = """
DO $contentengine$
DECLARE
    target_table record;
BEGIN
    FOR target_table IN
        SELECT table_schema.nspname AS schema_name, table_info.relname AS table_name
        FROM pg_catalog.pg_class AS table_info
        JOIN pg_catalog.pg_namespace AS table_schema
          ON table_schema.oid = table_info.relnamespace
        WHERE table_schema.nspname = 'public'
          AND table_info.relkind IN ('r', 'p')
          AND NOT EXISTS (
              SELECT 1
              FROM pg_catalog.pg_depend AS object_dependency
              WHERE object_dependency.classid = 'pg_catalog.pg_class'::regclass
                AND object_dependency.objid = table_info.oid
                AND object_dependency.deptype = 'e'
          )
        ORDER BY table_info.relname
    LOOP
        EXECUTE format(
            'ALTER TABLE %I.%I ENABLE ROW LEVEL SECURITY',
            target_table.schema_name,
            target_table.table_name
        );
    END LOOP;
END
$contentengine$;
"""


_REVOKE_SUPABASE_API_PRIVILEGES_SQL = """
DO $contentengine$
DECLARE
    target_role text;
BEGIN
    FOR target_role IN
        SELECT database_role.rolname
        FROM pg_catalog.pg_roles AS database_role
        WHERE database_role.rolname IN ('anon', 'authenticated', 'service_role')
        ORDER BY database_role.rolname
    LOOP
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM %I CASCADE',
            target_role
        );
        EXECUTE format(
            'REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM %I CASCADE',
            target_role
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL PRIVILEGES ON TABLES FROM %I',
            current_user,
            target_role
        );
        EXECUTE format(
            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public REVOKE ALL PRIVILEGES ON SEQUENCES FROM %I',
            current_user,
            target_role
        );
    END LOOP;
END
$contentengine$;
"""


@dataclass(frozen=True)
class PostgresPublicSchemaSecurityResult:
    rls_enabled: bool
    api_roles_restricted: bool


def install_postgresql_public_schema_security(connection: Connection) -> None:
    """Enable fail-closed public-table isolation on a PostgreSQL connection."""

    if connection.dialect.name != "postgresql":
        raise ValueError("PostgreSQL public-schema security requires PostgreSQL")
    connection.execute(text(_ENABLE_PUBLIC_TABLE_RLS_SQL))
    connection.execute(text(_REVOKE_SUPABASE_API_PRIVILEGES_SQL))


def inspect_postgresql_public_schema_security(
    connection: Connection,
    table_names: Collection[str],
) -> PostgresPublicSchemaSecurityResult:
    """Read the effective RLS and API-role state for required public tables.

    The correlated ``EXISTS`` intentionally treats an absent Supabase role as
    secure.  When a role exists, both table-level and column-level effective
    DML privileges are checked, including privileges inherited through another
    role or ``PUBLIC``.
    """

    if connection.dialect.name != "postgresql":
        return PostgresPublicSchemaSecurityResult(
            rls_enabled=False,
            api_roles_restricted=False,
        )

    expected_tables = {str(name) for name in table_names if str(name)}
    if not expected_tables:
        return PostgresPublicSchemaSecurityResult(
            rls_enabled=True,
            api_roles_restricted=True,
        )

    statement = text(
        """
        SELECT
            table_info.relname AS table_name,
            table_info.relrowsecurity AS rls_enabled,
            EXISTS (
                SELECT 1
                FROM pg_catalog.pg_roles AS api_role
                WHERE api_role.rolname IN ('anon', 'authenticated', 'service_role')
                  AND (
                      has_table_privilege(api_role.oid, table_info.oid, 'SELECT')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'INSERT')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'UPDATE')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'DELETE')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'TRUNCATE')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'REFERENCES')
                      OR has_table_privilege(api_role.oid, table_info.oid, 'TRIGGER')
                      OR has_any_column_privilege(api_role.oid, table_info.oid, 'SELECT')
                      OR has_any_column_privilege(api_role.oid, table_info.oid, 'INSERT')
                      OR has_any_column_privilege(api_role.oid, table_info.oid, 'UPDATE')
                      OR has_any_column_privilege(api_role.oid, table_info.oid, 'REFERENCES')
                  )
            ) AS api_role_has_privilege
        FROM pg_catalog.pg_class AS table_info
        JOIN pg_catalog.pg_namespace AS table_schema
          ON table_schema.oid = table_info.relnamespace
        WHERE table_schema.nspname = 'public'
          AND table_info.relkind IN ('r', 'p')
          AND table_info.relname IN :table_names
        """
    ).bindparams(bindparam("table_names", expanding=True))
    rows = connection.execute(
        statement,
        {"table_names": tuple(sorted(expected_tables))},
    ).mappings().all()
    row_by_table = {str(row["table_name"]): row for row in rows}
    complete = set(row_by_table) == expected_tables
    return PostgresPublicSchemaSecurityResult(
        rls_enabled=complete
        and all(bool(row["rls_enabled"]) for row in row_by_table.values()),
        api_roles_restricted=complete
        and not any(
            bool(row["api_role_has_privilege"])
            for row in row_by_table.values()
        ),
    )
