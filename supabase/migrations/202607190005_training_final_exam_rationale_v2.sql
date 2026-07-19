begin;

-- The final exam must prove that the learner can explain four irreversible
-- production decisions. The existing answer catalog and private answer keys
-- remain untouched; this wrapper only adds a written-evidence gate.
alter function public.creator_submit_exam(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_submit_exam(jsonb)
  rename to creator_submit_exam_pre_rationale_v2;

revoke all on function
  content_factory_private.creator_submit_exam_pre_rationale_v2(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_submit_exam(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
#variable_conflict use_variable
declare
  user_id uuid;
  organization_id uuid;
  exam_code text;
  idempotency_key text;
  submitted_rationales jsonb;
  required_rationale_codes constant text[] := array[
    'exam_sku_mismatch',
    'exam_qa_requirements',
    'exam_publication_evidence',
    'exam_payout_separation'
  ];
  rationale_code text;
  distinct_rationale_count integer;
  attempt_id uuid;
  existing_rationales jsonb;
  result jsonb;
begin
  p_payload := content_factory_private.require_payload(p_payload);
  user_id := content_factory_private.current_profile_id();
  organization_id := content_factory_private.resolve_organization(p_payload);
  perform content_factory_private.membership_role(
    organization_id,
    false,
    null
  );

  exam_code := coalesce(
    nullif(btrim(p_payload ->> 'module_code'), ''),
    'operator_final_exam'
  );
  idempotency_key := content_factory_private.require_text(
    p_payload,
    'idempotency_key',
    8,
    180
  );
  submitted_rationales := coalesce(p_payload -> 'rationales', '{}'::jsonb);

  if jsonb_typeof(submitted_rationales) <> 'object'
     or (select count(*) from jsonb_object_keys(submitted_rationales)) <> 4
     or exists (
       select 1
       from jsonb_object_keys(submitted_rationales) submitted(code)
       where submitted.code <> all(required_rationale_codes)
     )
     or exists (
       select 1
       from unnest(required_rationale_codes) required(code)
       where not submitted_rationales ? required.code
     ) then
    raise exception using
      errcode = '22023',
      message = 'final_exam_rationales_required';
  end if;

  foreach rationale_code in array required_rationale_codes loop
    if not content_factory_private.valid_training_rationale(
      submitted_rationales -> rationale_code
    ) then
      raise exception using
        errcode = '22023',
        message = 'final_exam_rationale_invalid';
    end if;
  end loop;

  select count(distinct lower(regexp_replace(
    btrim(rationale.value),
    '\s+',
    ' ',
    'g'
  )))
  into distinct_rationale_count
  from jsonb_each_text(submitted_rationales) rationale(code, value);

  if distinct_rationale_count <> 4 then
    raise exception using
      errcode = '22023',
      message = 'final_exam_rationales_must_be_unique';
  end if;

  -- An exact retry may return the existing receipt, but its written evidence
  -- cannot be replaced. The post-call check below also closes the concurrent
  -- first-submit race between two tabs.
  select attempt.id, attempt.rationales
    into attempt_id, existing_rationales
  from content_factory.training_attempts attempt
  where attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = exam_code
    and attempt.idempotency_key = left('exam:' || idempotency_key, 180)
  for update;

  if found
     and existing_rationales <> '{}'::jsonb
     and existing_rationales <> submitted_rationales then
    raise exception using
      errcode = '22023',
      message = 'final_exam_rationales_immutable';
  end if;

  result := content_factory_private.creator_submit_exam_pre_rationale_v2(
    p_payload - 'rationales'
  );

  if coalesce(result ->> 'attempt_id', '') !~
       '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' then
    raise exception using
      errcode = '55000',
      message = 'final_exam_attempt_receipt_invalid';
  end if;
  attempt_id := (result ->> 'attempt_id')::uuid;

  select attempt.rationales
    into existing_rationales
  from content_factory.training_attempts attempt
  where attempt.id = attempt_id
    and attempt.organization_id = organization_id
    and attempt.profile_id = user_id
    and attempt.module_code = exam_code
  for update;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'final_exam_attempt_not_found';
  end if;

  if existing_rationales <> '{}'::jsonb
     and existing_rationales <> submitted_rationales then
    raise exception using
      errcode = '22023',
      message = 'final_exam_rationales_immutable';
  end if;

  update content_factory.training_attempts attempt
  set
    rationales = submitted_rationales,
    assessment_version = greatest(attempt.assessment_version, 2),
    request_hash = content_factory_private.json_hash(jsonb_build_object(
      'answers', attempt.answers,
      'rationales', submitted_rationales
    ))
  where attempt.id = attempt_id;

  return result;
end;
$$;

revoke all on function public.creator_submit_exam(jsonb)
  from public, anon;
grant execute on function public.creator_submit_exam(jsonb)
  to authenticated;

comment on function public.creator_submit_exam(jsonb) is
  'Requires four structured, unique and immutable written rationales before running the practical-gated private final exam.';

do $$
declare
  public_exam_definition text;
begin
  select pg_get_functiondef(
    'public.creator_submit_exam(jsonb)'::regprocedure
  ) into public_exam_definition;

  if strpos(public_exam_definition, 'creator_submit_exam_pre_rationale_v2') = 0
     or strpos(public_exam_definition, 'valid_training_rationale') = 0
     or strpos(public_exam_definition, 'p_payload - ''rationales''') = 0
     or strpos(public_exam_definition, 'final_exam_rationales_immutable') = 0 then
    raise exception 'final_exam_rationale_v2_not_installed';
  end if;

  if has_function_privilege(
    'authenticated',
    'content_factory_private.creator_submit_exam_pre_rationale_v2(jsonb)',
    'EXECUTE'
  ) then
    raise exception 'private_final_exam_rationale_implementation_is_browser_callable';
  end if;
end;
$$;

commit;
