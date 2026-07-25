begin;

-- PostgREST caches function volatility. After the archive RPC changed from
-- STABLE to VOLATILE, the stale cache could still open its POST transaction as
-- read-only and reject current_profile_id() when it synchronized the profile.
alter function public.creator_generation_archive(jsonb) volatile;

notify pgrst, 'reload schema';

commit;
