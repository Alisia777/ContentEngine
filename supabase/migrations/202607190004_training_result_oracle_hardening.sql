begin;

-- Preserve idempotent retries while removing grading diagnostics that older
-- receipts may contain. A learner may see pass/fail and retry timing, but never
-- an exact score delta that can be used to reconstruct a private answer key.
update content_factory.command_receipts receipt
set result = case receipt.command_name
  when 'creator_submit_platform_simulator' then
    case
      when jsonb_typeof(receipt.result -> 'attempt') = 'object' then
        jsonb_set(
          receipt.result
            - 'correct_count'
            - 'critical_error_count'
            - 'score_percent'
            - 'review_topics',
          '{attempt}',
          (receipt.result -> 'attempt')
            - 'correct_count'
            - 'critical_error_count'
            - 'score_percent'
            - 'review_topics',
          false
        )
      else receipt.result
        - 'correct_count'
        - 'critical_error_count'
        - 'score_percent'
        - 'review_topics'
    end
  else receipt.result
    - 'correct_count'
    - 'critical_error_count'
    - 'score_percent'
    - 'review_topics'
    - 'topics'
end
where receipt.command_name in (
  'creator_submit_course_check',
  'creator_submit_platform_simulator',
  'creator_submit_exam'
);

-- The practical-review migration owns the final-exam gate. Keep that gate as
-- the only implementation and put this narrow disclosure filter in front of
-- it, so every fresh call and every replay is sanitized consistently.
alter function public.creator_submit_exam(jsonb)
  set schema content_factory_private;
alter function content_factory_private.creator_submit_exam(jsonb)
  rename to creator_submit_exam_pre_result_sanitize;

revoke all on function
  content_factory_private.creator_submit_exam_pre_result_sanitize(jsonb)
  from public, anon, authenticated;

create or replace function public.creator_submit_exam(
  p_payload jsonb default '{}'::jsonb
)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  result jsonb;
begin
  result := content_factory_private.creator_submit_exam_pre_result_sanitize(
    p_payload
  );

  return result
    - 'correct_count'
    - 'critical_error_count'
    - 'score_percent'
    - 'review_topics'
    - 'topics';
end;
$$;

revoke all on function public.creator_submit_exam(jsonb)
  from public, anon;
grant execute on function public.creator_submit_exam(jsonb)
  to authenticated;

comment on function public.creator_submit_exam(jsonb) is
  'Runs the practical-gated final exam and returns only coarse pass/fail state, never score diagnostics or answer remediation.';

do $$
declare
  public_exam_definition text;
begin
  select pg_get_functiondef(
    'public.creator_submit_exam(jsonb)'::regprocedure
  ) into public_exam_definition;

  if strpos(public_exam_definition, '- ''correct_count''') = 0
     or strpos(public_exam_definition, '- ''score_percent''') = 0
     or strpos(public_exam_definition, 'creator_submit_exam_pre_result_sanitize') = 0 then
    raise exception 'final_exam_result_sanitizer_not_installed';
  end if;

  if has_function_privilege(
    'authenticated',
    'content_factory_private.creator_submit_exam_pre_result_sanitize(jsonb)',
    'EXECUTE'
  ) then
    raise exception 'private_final_exam_implementation_is_browser_callable';
  end if;
end;
$$;

commit;
