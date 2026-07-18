from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
MIGRATION_PATH = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607170008_generation_archive_scale.sql"
)
SQL = MIGRATION_PATH.read_text(encoding="utf-8")
INDEX_SQL = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607130004_creator_rpcs.sql"
).read_text(encoding="utf-8")


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def _function_parts() -> tuple[str, str]:
    match = re.search(
        r"create\s+or\s+replace\s+function\s+"
        r"public\.creator_generation_archive\s*\(\s*"
        r"p_payload\s+jsonb[^)]*\)\s*returns\s+jsonb"
        r"(?P<header>.*?)as\s+\$\$(?P<body>.*?)\$\$;",
        SQL,
        flags=re.IGNORECASE | re.DOTALL,
    )
    assert match, "missing creator_generation_archive(p_payload jsonb)"
    return match.group("header"), match.group("body")


def _call_arguments(source: str, marker: str) -> list[str]:
    """Return the top-level arguments of a SQL call following marker."""
    start = source.casefold().index(marker.casefold()) + len(marker)
    assert source[start - 1] == "("
    depth = 0
    quoted = False
    index = start
    argument_start = start
    arguments: list[str] = []

    while index < len(source):
        character = source[index]
        if quoted:
            if character == "'":
                if index + 1 < len(source) and source[index + 1] == "'":
                    index += 2
                    continue
                quoted = False
        elif character == "'":
            quoted = True
        elif character == "(":
            depth += 1
        elif character == ")":
            if depth == 0:
                arguments.append(source[argument_start:index].strip())
                return arguments
            depth -= 1
        elif character == "," and depth == 0:
            arguments.append(source[argument_start:index].strip())
            argument_start = index + 1
        index += 1

    raise AssertionError(f"unterminated SQL call after {marker!r}")


def _literal_object_keys(arguments: list[str]) -> list[str]:
    assert len(arguments) % 2 == 0
    keys: list[str] = []
    for token in arguments[::2]:
        match = re.fullmatch(r"'([^']+)'", token.strip())
        assert match, f"JSON object key is not a literal: {token}"
        keys.append(match.group(1))
    return keys


def test_archive_rpc_is_hardened_and_authenticated_only() -> None:
    header, _ = _function_parts()
    normalized_header = _normalized(header)

    assert "language plpgsql" in normalized_header
    assert "security definer" in normalized_header
    assert "stable" in normalized_header
    assert "set search_path = ''" in normalized_header
    assert re.search(
        r"revoke\s+all\s+on\s+function\s+"
        r"public\.creator_generation_archive\s*\(\s*jsonb\s*\)\s+"
        r"from\s+public\s*,\s*anon",
        SQL,
        flags=re.IGNORECASE,
    )
    grants = re.findall(
        r"grant\s+execute\s+on\s+function\s+"
        r"public\.creator_generation_archive\s*\(\s*jsonb\s*\)\s+"
        r"to\s+([a-z_,\s]+?)\s*;",
        SQL,
        flags=re.IGNORECASE,
    )
    assert [grant.strip().casefold() for grant in grants] == ["authenticated"]


def test_archive_rpc_rejects_unknown_and_malformed_filters() -> None:
    _, body = _function_parts()
    normalized = _normalized(body)

    assert "content_factory_private.require_payload(p_payload)" in normalized
    assert (
        "payload_key <> all(array[ 'organization_id', 'period', 'status', "
        "'query', 'page_size', 'cursor' ])"
    ) in normalized
    assert "generation_archive_payload_invalid" in normalized

    assert "jsonb_typeof(p_payload -> 'period') <> 'string'" in normalized
    assert "period_value not in ('week', '4w', '12w', 'all')" in normalized
    assert "generation_archive_period_invalid" in normalized

    assert "jsonb_typeof(p_payload -> 'status') <> 'string'" in normalized
    assert "status_value not in ('all', 'active', 'ready', 'issue')" in normalized
    assert "generation_archive_status_invalid" in normalized

    assert "jsonb_typeof(p_payload -> 'query') <> 'string'" in normalized
    assert "length(query_value) > 120" in normalized
    assert "query_value ~ '[[:cntrl:]]'" in normalized
    assert "generation_archive_query_invalid" in normalized

    assert "jsonb_typeof(p_payload -> 'page_size') <> 'number'" in normalized
    assert "coalesce(p_payload ->> 'page_size', '') !~ '^[0-9]+$'" in normalized
    assert "page_size not between 1 and 100" in normalized
    assert "numeric_value_out_of_range" in normalized
    assert "generation_archive_page_size_invalid" in normalized

    assert "jsonb_typeof(p_payload -> 'cursor') <> 'object'" in normalized
    assert "cursor_key <> all(array['at', 'id'])" in normalized
    assert "jsonb_typeof(p_payload #> '{cursor,at}') <> 'string'" in normalized
    assert "jsonb_typeof(p_payload #> '{cursor,id}') <> 'string'" in normalized
    assert "(p_payload #>> '{cursor,at}')::timestamptz" in normalized
    assert "(p_payload #>> '{cursor,id}')::uuid" in normalized
    assert "invalid_text_representation" in normalized
    assert "invalid_datetime_format" in normalized
    assert "datetime_field_overflow" in normalized
    assert "generation_archive_cursor_invalid" in normalized
    assert "period_value text := '4w'" in _normalized(SQL)
    assert "when '4w' then date_trunc('week', now()) - interval '3 weeks'" in normalized


def test_archive_uses_stable_keyset_pagination_and_exact_output_shape() -> None:
    _, body = _function_parts()
    normalized = _normalized(body)

    assert "(batch.created_at, batch.id) < (cursor_at, cursor_id)" in normalized
    assert "order by batch.created_at desc, batch.id desc" in normalized
    assert "limit page_size + 1" in normalized
    assert "count(*) > page_size as has_more" in normalized
    assert "limit page_size" in normalized

    outer_arguments = _call_arguments(body, "select jsonb_build_object(")
    assert _literal_object_keys(outer_arguments) == ["ok", "batches", "_meta"]

    meta_arguments = _call_arguments(
        outer_arguments[5],
        "jsonb_build_object(",
    )
    assert _literal_object_keys(meta_arguments) == [
        "page_size",
        "has_more",
        "next_cursor",
        "period",
        "status",
        "query",
        "cursor_mode",
    ]
    assert "'cursor_mode', 'keyset_created_at_id'" in normalized
    assert "when page_stats.has_more then jsonb_build_object(" in normalized
    assert "'at', last_row.created_at" in normalized
    assert "'id', last_row.id" in normalized


def test_archive_scope_is_tenant_bound_team_or_self() -> None:
    _, body = _function_parts()
    normalized = _normalized(body)

    assert "user_id := content_factory_private.current_profile_id()" in normalized
    assert "content_factory_private.resolve_organization(p_payload)" in normalized
    assert (
        "content_factory_private.membership_role( organization_id, true, null )"
        in normalized
    )
    assert (
        "actor_role = any(array[ 'owner', 'admin', 'producer', 'reviewer' ])"
        in normalized
    )
    assert "batch.organization_id = organization_id" in normalized
    assert "(team_scope or batch.created_by = user_id)" in normalized
    assert "product.organization_id = batch.organization_id" in normalized


def test_archive_rpc_is_read_only() -> None:
    _, body = _function_parts()
    for command in ("insert", "update", "delete", "truncate", "merge"):
        assert not re.search(rf"\b{command}\b", body, flags=re.IGNORECASE)


def test_archive_has_tenant_and_creator_keyset_indexes() -> None:
    normalized = _normalized(INDEX_SQL)

    assert "generation_batches_workspace_org_page_idx" in INDEX_SQL
    assert "generation_batches_workspace_owner_page_idx" in INDEX_SQL
    assert (
        "create index if not exists generation_batches_workspace_org_page_idx "
        "on content_factory.generation_batches "
        "(organization_id, created_at desc, id desc)"
    ) in normalized
    assert (
        "create index if not exists generation_batches_workspace_owner_page_idx "
        "on content_factory.generation_batches "
        "(organization_id, created_by, created_at desc, id desc)"
    ) in normalized
