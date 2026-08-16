begin;

-- Stop stale working-draft writes from being retried as serialization errors.
--
-- The original RPC used SQLSTATE 40001 for an application-level compare-and-
-- swap conflict. PostgREST treats 40001 as retryable, so a single stale browser
-- write can keep one database backend busy indefinitely. PT409 preserves the
-- conflict semantics for the HTTP client and is terminal for the transaction.

do $contentengine_working_draft_conflict_hotfix$
declare
  function_definition text;
  retryable_fragment constant text := 'errcode = ''40001''';
  terminal_fragment constant text := 'errcode = ''PT409''';
  retryable_occurrences integer;
begin
  select pg_get_functiondef(
    'public.contentengine_generation_ai_research_working_draft(jsonb)'
      ::regprocedure
  )
  into function_definition;

  if position(terminal_fragment in function_definition) > 0
     and position(retryable_fragment in function_definition) = 0 then
    return;
  end if;

  retryable_occurrences := (
    length(function_definition)
      - length(replace(function_definition, retryable_fragment, ''))
  ) / length(retryable_fragment);

  if retryable_occurrences <> 1 then
    raise exception using
      errcode = 'P0001',
      message = 'working_draft_conflict_hotfix_source_mismatch',
      detail = format(
        'expected one retryable fragment, found %s',
        retryable_occurrences
      );
  end if;

  execute replace(
    function_definition,
    retryable_fragment,
    terminal_fragment
  );
end;
$contentengine_working_draft_conflict_hotfix$;

comment on function
  public.contentengine_generation_ai_research_working_draft(jsonb) is
  'Project-shared, CAS-protected AI research working draft. Revision conflicts return terminal HTTP 409 and never use retryable SQLSTATE 40001.';

commit;
