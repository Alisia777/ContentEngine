#!/usr/bin/env python3
"""Configure the production background worker with Supabase Cron.

The worker URL and shared secret are stored in Supabase Vault.  The scheduled
command keeps only Vault lookups, never plaintext credentials, in ``cron.job``.
All SQL is sent through the existing Management API client and is deliberately
excluded from console output and exception messages.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import os
import sys
from typing import Mapping, Protocol

if __package__:
    from .deploy_supabase_management_api import (
        ConfigurationError,
        DeploymentError,
        EXPECTED_PROJECT_REF,
        ManagementApiClient,
    )
else:
    from deploy_supabase_management_api import (  # type: ignore[no-redef]
        ConfigurationError,
        DeploymentError,
        EXPECTED_PROJECT_REF,
        ManagementApiClient,
    )


VAULT_URL_SECRET_NAME = "contentengine_background_worker_url"
VAULT_WORKER_SECRET_NAME = "contentengine_background_worker_secret"
CRON_JOB_NAME = "contentengine-background-worker-v1"
CRON_SCHEDULE = "*/2 * * * *"
CRON_LOCK_NAME = "contentengine_background_cron:production"
WORKER_TIMEOUT_MILLISECONDS = 150_000
WORKER_PAYLOAD = {
    "generation_limit": 4,
    "research_limit": 1,
    "review_limit": 1,
}


class SqlClient(Protocol):
    def execute(self, sql: str, *, read_only: bool = False) -> object: ...


@dataclass(frozen=True)
class BackgroundCronSettings:
    project_ref: str
    access_token: str = field(repr=False)
    worker_secret: str = field(repr=False)

    @classmethod
    def from_environment(
        cls, environment: Mapping[str, str]
    ) -> "BackgroundCronSettings":
        project_ref = environment.get("SUPABASE_PROJECT_REF", "").strip()
        access_token = environment.get("SUPABASE_ACCESS_TOKEN", "").strip()
        worker_secret = environment.get("CONTENTENGINE_WORKER_SECRET", "")

        if project_ref != EXPECTED_PROJECT_REF:
            raise ConfigurationError(
                "SUPABASE_PROJECT_REF does not match the reviewed production project"
            )
        if (
            not access_token
            or len(access_token) > 4096
            or _contains_control(access_token)
        ):
            raise ConfigurationError(
                "SUPABASE_ACCESS_TOKEN is required and must be safe"
            )
        if (
            len(worker_secret) < 32
            or len(worker_secret) > 512
            or worker_secret != worker_secret.strip()
            or _contains_control(worker_secret)
        ):
            raise ConfigurationError(
                "CONTENTENGINE_WORKER_SECRET must contain 32 to 512 safe characters"
            )
        return cls(
            project_ref=project_ref,
            access_token=access_token,
            worker_secret=worker_secret,
        )

    @property
    def worker_url(self) -> str:
        return (
            f"https://{self.project_ref}.supabase.co/functions/v1/"
            "creator-background-worker"
        )


def _contains_control(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def build_configuration_sql(settings: BackgroundCronSettings) -> str:
    """Build one atomic, idempotent operational configuration transaction."""

    worker_url = _sql_literal(settings.worker_url)
    worker_secret = _sql_literal(settings.worker_secret)
    url_name = _sql_literal(VAULT_URL_SECRET_NAME)
    secret_name = _sql_literal(VAULT_WORKER_SECRET_NAME)
    job_name = _sql_literal(CRON_JOB_NAME)
    schedule = _sql_literal(CRON_SCHEDULE)
    payload = _sql_literal(
        json.dumps(WORKER_PAYLOAD, ensure_ascii=True, separators=(",", ":"))
    )

    return f"""
begin;
select pg_advisory_xact_lock(hashtextextended({_sql_literal(CRON_LOCK_NAME)}, 0));

create extension if not exists pg_cron with schema pg_catalog;
create extension if not exists pg_net with schema extensions;

do $contentengine_background_cron$
declare
  existing_secret_id uuid;
  existing_job record;
begin
  if to_regclass('vault.secrets') is null
     or to_regclass('vault.decrypted_secrets') is null then
    raise exception using message = 'background_cron_vault_unavailable';
  end if;

  select secret.id into existing_secret_id
  from vault.secrets secret
  where secret.name = {url_name};
  if existing_secret_id is null then
    perform vault.create_secret(
      {worker_url},
      {url_name},
      'ContentEngine background worker URL'
    );
  else
    perform vault.update_secret(
      existing_secret_id,
      {worker_url},
      {url_name},
      'ContentEngine background worker URL'
    );
  end if;

  existing_secret_id := null;
  select secret.id into existing_secret_id
  from vault.secrets secret
  where secret.name = {secret_name};
  if existing_secret_id is null then
    perform vault.create_secret(
      {worker_secret},
      {secret_name},
      'ContentEngine background worker shared secret'
    );
  else
    perform vault.update_secret(
      existing_secret_id,
      {worker_secret},
      {secret_name},
      'ContentEngine background worker shared secret'
    );
  end if;

  for existing_job in
    select job.jobid
    from cron.job job
    where job.jobname = {job_name}
  loop
    perform cron.unschedule(existing_job.jobid);
  end loop;

  perform cron.schedule(
    {job_name},
    {schedule},
    $contentengine_worker_command$
      select net.http_post(
        url := (
          select secret.decrypted_secret
          from vault.decrypted_secrets secret
          where secret.name = {url_name}
        ),
        headers := jsonb_build_object(
          'Content-Type', 'application/json',
          'x-contentengine-internal-worker', '1',
          'x-contentengine-worker-secret', (
            select secret.decrypted_secret
            from vault.decrypted_secrets secret
            where secret.name = {secret_name}
          )
        ),
        body := {payload}::jsonb,
        timeout_milliseconds := {WORKER_TIMEOUT_MILLISECONDS}
      );
    $contentengine_worker_command$
  );

  if (select count(*) from vault.secrets secret where secret.name = {url_name}) <> 1
     or (select count(*) from vault.secrets secret where secret.name = {secret_name}) <> 1 then
    raise exception using message = 'background_cron_vault_postcondition_failed';
  end if;

  if (
    select count(*)
    from cron.job job
    where job.jobname = {job_name}
      and job.active
      and job.schedule = {schedule}
      and position({url_name} in job.command) > 0
      and position({secret_name} in job.command) > 0
      and position({worker_url} in job.command) = 0
      and position({worker_secret} in job.command) = 0
  ) <> 1 then
    raise exception using message = 'background_cron_job_postcondition_failed';
  end if;
end;
$contentengine_background_cron$;

commit;
""".strip()


def configure_background_cron(
    settings: BackgroundCronSettings,
    *,
    client: SqlClient,
) -> None:
    client.execute(build_configuration_sql(settings))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Configure the production Supabase background worker cron"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate protected environment variables without sending SQL",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        settings = BackgroundCronSettings.from_environment(os.environ)
        if args.dry_run:
            print("Supabase background cron settings validated; no request was made.")
            return 0
        client = ManagementApiClient(
            project_ref=settings.project_ref,
            access_token=settings.access_token,
        )
        configure_background_cron(settings, client=client)
    except DeploymentError as exc:
        print(f"Supabase background cron configuration stopped: {exc}", file=sys.stderr)
        return 1
    except Exception:
        print(
            "Supabase background cron configuration stopped: "
            "unexpected internal failure",
            file=sys.stderr,
        )
        return 1

    print("Supabase background cron configured: one native two-minute worker job.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
