begin;

-- creator_generation_learning_policy is logically read-only, but the shared
-- current_profile_id() guard refreshes the authenticated profile record.
-- Marking the public RPC STABLE makes PostgREST open a read-only transaction
-- and that safety refresh fails with SQLSTATE 25006.
alter function public.creator_generation_learning_policy(jsonb) volatile;

notify pgrst, 'reload schema';

commit;
