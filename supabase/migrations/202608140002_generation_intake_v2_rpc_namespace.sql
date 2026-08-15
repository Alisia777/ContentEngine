begin;

-- Compact intake saving is a preparation operation, not a full creator
-- generation command. Keep it beside the exact-YouTube preparation RPCs so the
-- creator_* namespace remains reserved for the established workspace command
-- surface and its fixed security contract.
alter function public.creator_save_generation_intake_v2(jsonb)
  rename to contentengine_save_generation_intake_v2;

revoke all on function
  public.contentengine_save_generation_intake_v2(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_save_generation_intake_v2(jsonb)
  to authenticated, service_role;

comment on function
  public.contentengine_save_generation_intake_v2(jsonb) is
  'Validates and stores one compact Copy/Avatar preparation intake. It never reserves budget or starts a provider call.';

notify pgrst, 'reload schema';

commit;
