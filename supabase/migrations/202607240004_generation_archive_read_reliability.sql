begin;

-- creator_generation_archive calls current_profile_id(), which keeps the
-- authenticated profile synchronized with auth.users through an upsert.  A
-- STABLE function runs in a read-only execution context and therefore rejects
-- that legitimate synchronization before the archive query starts.
alter function public.creator_generation_archive(jsonb) volatile;

do $generation_archive_read_reliability_contract$
declare
  archive_volatility "char";
begin
  select procedure.provolatile
    into archive_volatility
  from pg_proc procedure
  join pg_namespace namespace
    on namespace.oid = procedure.pronamespace
  where namespace.nspname = 'public'
    and procedure.proname = 'creator_generation_archive'
    and pg_get_function_identity_arguments(procedure.oid) = 'p_payload jsonb';

  if archive_volatility is distinct from 'v' then
    raise exception 'creator_generation_archive_must_be_volatile';
  end if;
end;
$generation_archive_read_reliability_contract$;

commit;
