begin;

-- Keep the audited creator_* RPC surface stable while exposing this optional
-- learning extension through explicit ContentEngine names. The original queue
-- function remains as an owner/service-only internal dependency because the
-- append-only decision function uses it for the returned snapshot.

revoke all on function public.creator_ai_research_training_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function public.creator_ai_research_training_queue(jsonb)
  to service_role;

create or replace function public.contentengine_ai_research_training_queue(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language sql
stable
security definer
set search_path = ''
as $$
  select public.creator_ai_research_training_queue(p_payload)
$$;

revoke all on function
  public.contentengine_ai_research_training_queue(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_ai_research_training_queue(jsonb)
  to authenticated, service_role;

alter function public.creator_decide_ai_research_training(jsonb)
  rename to contentengine_decide_ai_research_training;
alter function public.creator_generation_research_recommendations(jsonb)
  rename to contentengine_generation_research_recommendations;

revoke all on function
  public.contentengine_decide_ai_research_training(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_decide_ai_research_training(jsonb)
  to authenticated, service_role;

revoke all on function
  public.contentengine_generation_research_recommendations(jsonb)
  from public, anon, authenticated, service_role;
grant execute on function
  public.contentengine_generation_research_recommendations(jsonb)
  to authenticated, service_role;

comment on function public.contentengine_ai_research_training_queue(jsonb) is
  'Read-only ContentEngine extension RPC for the governed research training queue. The creator_* browser RPC count remains stable.';
comment on function public.contentengine_decide_ai_research_training(jsonb) is
  'ContentEngine extension RPC for append-only human selection of research insights and editable recommendations.';
comment on function public.contentengine_generation_research_recommendations(jsonb) is
  'ContentEngine extension RPC returning only human-approved project/category recommendations; exact-product matches may be auto-filled and remain editable.';

notify pgrst, 'reload schema';

commit;
