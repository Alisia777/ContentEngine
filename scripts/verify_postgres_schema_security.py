from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import bindparam, text

from app.database import engine
from app.postgres_security import (
    SUPABASE_API_ROLES,
    inspect_postgresql_public_schema_security,
)
from app.readiness import CRITICAL_TABLES


def verify_postgresql_public_schema_security() -> None:
    """Fail CI unless migrated PostgreSQL is isolated from Supabase Data API roles."""

    if engine.dialect.name != "postgresql":
        raise RuntimeError("PostgreSQL schema security verification requires PostgreSQL")

    with engine.connect() as connection:
        critical = inspect_postgresql_public_schema_security(
            connection,
            CRITICAL_TABLES,
        )
        if not critical.rls_enabled:
            raise RuntimeError("Critical public tables do not all have RLS enabled")
        if not critical.api_roles_restricted:
            raise RuntimeError(
                "A Supabase API role retains effective privileges on a critical table"
            )

        non_rls_tables = connection.execute(
            text(
                """
                SELECT table_info.relname
                FROM pg_catalog.pg_class AS table_info
                JOIN pg_catalog.pg_namespace AS table_schema
                  ON table_schema.oid = table_info.relnamespace
                WHERE table_schema.nspname = 'public'
                  AND table_info.relkind IN ('r', 'p')
                  AND NOT table_info.relrowsecurity
                  AND NOT EXISTS (
                      SELECT 1
                      FROM pg_catalog.pg_depend AS object_dependency
                      WHERE object_dependency.classid = 'pg_catalog.pg_class'::regclass
                        AND object_dependency.objid = table_info.oid
                        AND object_dependency.deptype = 'e'
                  )
                ORDER BY table_info.relname
                """
            )
        ).scalars().all()
        if non_rls_tables:
            raise RuntimeError(
                "Public application tables without RLS: "
                + ",".join(str(name) for name in non_rls_tables)
            )

        exposed_sequences = connection.execute(
            text(
                """
                SELECT api_role.rolname, sequence_info.relname
                FROM pg_catalog.pg_roles AS api_role
                CROSS JOIN pg_catalog.pg_class AS sequence_info
                JOIN pg_catalog.pg_namespace AS sequence_schema
                  ON sequence_schema.oid = sequence_info.relnamespace
                WHERE api_role.rolname IN ('anon', 'authenticated', 'service_role')
                  AND sequence_schema.nspname = 'public'
                  AND sequence_info.relkind = 'S'
                  AND (
                      has_sequence_privilege(api_role.oid, sequence_info.oid, 'USAGE')
                      OR has_sequence_privilege(api_role.oid, sequence_info.oid, 'SELECT')
                      OR has_sequence_privilege(api_role.oid, sequence_info.oid, 'UPDATE')
                  )
                ORDER BY api_role.rolname, sequence_info.relname
                """
            )
        ).all()
        if exposed_sequences:
            raise RuntimeError(
                "A Supabase API role retains effective public-sequence privileges"
            )

        exposed_defaults = connection.execute(
            text(
                """
                SELECT default_acl.defaclobjtype, granted_role.rolname
                FROM pg_catalog.pg_default_acl AS default_acl
                JOIN pg_catalog.pg_roles AS owner_role
                  ON owner_role.oid = default_acl.defaclrole
                JOIN pg_catalog.pg_namespace AS object_schema
                  ON object_schema.oid = default_acl.defaclnamespace
                CROSS JOIN LATERAL pg_catalog.aclexplode(default_acl.defaclacl) AS acl
                JOIN pg_catalog.pg_roles AS granted_role
                  ON granted_role.oid = acl.grantee
                WHERE owner_role.rolname = current_user
                  AND object_schema.nspname = 'public'
                  AND default_acl.defaclobjtype IN ('r', 'S')
                  AND granted_role.rolname IN ('anon', 'authenticated', 'service_role')
                """
            )
        ).all()
        if exposed_defaults:
            raise RuntimeError(
                "Current owner still auto-grants future tables or sequences to an API role"
            )

        owner_statement = text(
            """
            SELECT table_info.relname
            FROM pg_catalog.pg_class AS table_info
            JOIN pg_catalog.pg_namespace AS table_schema
              ON table_schema.oid = table_info.relnamespace
            JOIN pg_catalog.pg_roles AS owner_role
              ON owner_role.oid = table_info.relowner
            WHERE table_schema.nspname = 'public'
              AND table_info.relname IN :critical_tables
              AND owner_role.rolname <> current_user
            ORDER BY table_info.relname
            """
        ).bindparams(bindparam("critical_tables", expanding=True))
        non_owner_critical_tables = connection.execute(
            owner_statement,
            {"critical_tables": tuple(sorted(CRITICAL_TABLES))},
        ).scalars().all()
        if non_owner_critical_tables:
            raise RuntimeError(
                "Direct application database role does not own critical tables: "
                + ",".join(str(name) for name in non_owner_critical_tables)
            )

        # An enabled, non-forced RLS table remains directly readable by its
        # owner even with no API-facing policies.
        connection.execute(text("SELECT 1 FROM public.organizations LIMIT 1")).all()

    print(
        "PostgreSQL public-schema security verified: "
        f"{len(CRITICAL_TABLES)} critical tables, "
        f"API roles={','.join(SUPABASE_API_ROLES)}"
    )


if __name__ == "__main__":
    verify_postgresql_public_schema_security()
