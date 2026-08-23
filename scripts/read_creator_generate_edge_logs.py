#!/usr/bin/env python3
"""Read a narrow creator-generate network-log window from Supabase."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import re
import sys
from urllib import parse, request


def main() -> int:
    # Наряд для фильтра логов приходит аргументом: прежде здесь был вшит UUID
    # закрытого инцидента 21.08, и скрипт был бесполезен для любого другого.
    if len(sys.argv) != 2 or not re.fullmatch(r"[0-9a-f-]{36}", sys.argv[1]):
        print("usage: read_creator_generate_edge_logs.py <generation_job_id>", file=sys.stderr)
        return 2
    job_id = sys.argv[1]
    project_ref = os.environ["SUPABASE_PROJECT_REF"]
    access_token = os.environ["SUPABASE_ACCESS_TOKEN"]
    end = datetime.now(timezone.utc) + timedelta(minutes=1)
    start = end - timedelta(minutes=20)
    sql = f"""
select
  timestamp,
  source,
  log_attributes['request.method'] as method,
  log_attributes['request.path'] as path,
  log_attributes['response.status_code'] as status,
  left(event_message, 300) as event_message
from logs
where source in ('function_edge_logs', 'edge_logs')
  and (
    log_attributes['request.path'] ilike '%creator-generate%'
    or event_message ilike '%creator-generate%'
  )
order by timestamp desc
limit 50
""".strip()
    query = parse.urlencode({
        "sql": sql,
        "iso_timestamp_start": start.isoformat().replace("+00:00", "Z"),
        "iso_timestamp_end": end.isoformat().replace("+00:00", "Z"),
    })
    api_request = request.Request(
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/analytics/endpoints/logs?{query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentEngine-Log-Audit/1",
        },
    )
    with request.urlopen(api_request, timeout=60) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise RuntimeError("log audit response too large")
    parsed = json.loads(payload.decode("utf-8"))

    function_sql = f"""
select
  timestamp,
  source,
  left(event_message, 500) as event_message
from logs
where source = 'function_logs'
  and (
    event_message ilike '%{job_id}%'
    or event_message ilike '%strategy_recovery%'
  )
order by timestamp desc
limit 50
""".strip()
    function_query = parse.urlencode({
        "sql": function_sql,
        "iso_timestamp_start": start.isoformat().replace("+00:00", "Z"),
        "iso_timestamp_end": end.isoformat().replace("+00:00", "Z"),
    })
    function_request = request.Request(
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/analytics/endpoints/logs?{function_query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentEngine-Log-Audit/1",
        },
    )
    with request.urlopen(function_request, timeout=60) as response:
        function_payload = response.read(1_000_001)
    if len(function_payload) > 1_000_000:
        raise RuntimeError("function log audit response too large")
    function_parsed = json.loads(function_payload.decode("utf-8"))

    health_sql = """
select
  source,
  max(timestamp) as latest_timestamp,
  count() as row_count
from logs
where source in ('function_edge_logs', 'edge_logs', 'function_logs')
group by source
order by source
""".strip()
    health_query = parse.urlencode({
        "sql": health_sql,
        "iso_timestamp_start": start.isoformat().replace("+00:00", "Z"),
        "iso_timestamp_end": end.isoformat().replace("+00:00", "Z"),
    })
    health_request = request.Request(
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/analytics/endpoints/logs?{health_query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentEngine-Log-Audit/1",
        },
    )
    with request.urlopen(health_request, timeout=60) as response:
        health_payload = response.read(1_000_001)
    if len(health_payload) > 1_000_000:
        raise RuntimeError("log health response too large")
    health_parsed = json.loads(health_payload.decode("utf-8"))

    legacy_sql = """
select
  datetime(timestamp) as timestamp,
  status_code,
  path,
  event_message
from edge_logs
cross join unnest(metadata) as metadata
cross join unnest(request) as request
cross join unnest(response) as response
where path like '%creator-generate%'
order by timestamp desc
limit 50
""".strip()
    legacy_query = parse.urlencode({
        "sql": legacy_sql,
        "iso_timestamp_start": start.isoformat().replace("+00:00", "Z"),
        "iso_timestamp_end": end.isoformat().replace("+00:00", "Z"),
    })
    legacy_request = request.Request(
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/analytics/endpoints/logs.all?{legacy_query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentEngine-Log-Audit/1",
        },
    )
    with request.urlopen(legacy_request, timeout=60) as response:
        legacy_payload = response.read(1_000_001)
    if len(legacy_payload) > 1_000_000:
        raise RuntimeError("legacy log audit response too large")
    legacy_parsed = json.loads(legacy_payload.decode("utf-8"))
    legacy_function_sql = f"""
select
  datetime(timestamp) as timestamp,
  event_message
from function_logs
where event_message like '%{job_id}%'
  or event_message like '%strategy_recovery%'
order by timestamp desc
limit 50
""".strip()
    legacy_function_query = parse.urlencode({
        "sql": legacy_function_sql,
        "iso_timestamp_start": start.isoformat().replace("+00:00", "Z"),
        "iso_timestamp_end": end.isoformat().replace("+00:00", "Z"),
    })
    legacy_function_request = request.Request(
        "https://api.supabase.com/v1/projects/"
        f"{project_ref}/analytics/endpoints/logs.all?{legacy_function_query}",
        method="GET",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
            "User-Agent": "ContentEngine-Log-Audit/1",
        },
    )
    with request.urlopen(legacy_function_request, timeout=60) as response:
        legacy_function_payload = response.read(1_000_001)
    if len(legacy_function_payload) > 1_000_000:
        raise RuntimeError("legacy function log audit response too large")
    legacy_function_parsed = json.loads(
        legacy_function_payload.decode("utf-8")
    )
    print(json.dumps({
        "unified": parsed,
        "function": function_parsed,
        "health": health_parsed,
        "legacy": legacy_parsed,
        "legacy_function": legacy_function_parsed,
    }, separators=(",", ":"), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
