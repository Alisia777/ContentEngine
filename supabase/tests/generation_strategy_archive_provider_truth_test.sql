begin;

select plan(6);

select is(
  (
    length(regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )), '[[:space:]]+', '', 'g')) - length(replace(
      regexp_replace(lower(pg_get_functiondef(
        'public.creator_generation_archive_pre_execution_v1(jsonb)'
          ::regprocedure
      )), '[[:space:]]+', '', 'g'),
      'casewhenstrategy_snapshot.idisnotnullthenbatch.providerelselaunch.providerend',
      ''
    ))
  ) / length(
    'casewhenstrategy_snapshot.idisnotnullthenbatch.providerelselaunch.providerend'
  ),
  2,
  'strategy archive projects and filters by the persisted batch provider'
);

select ok(
  position(
    $v$provider_valuenotin('all','runway','google','fal')$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) > 0,
  'strategy archive accepts the exact fal provider filter'
);

select ok(
  position(
    $v$coalesce(launch.generation_job_id,strategy_snapshot.generation_job_id)asgeneration_job_id$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) > 0,
  'base archive selects the immutable legacy or strategy job identity'
);

select ok(
  position(
    $v$'generation_job_id',page.generation_job_id$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive_pre_execution_v1(jsonb)'
        ::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) > 0,
  'base archive exposes the immutable job identity at the top level'
);

select ok(
  position(
    $v$'provider',receipt_row.provider$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) > 0
  and position(
    $v$'provider','runway'$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) = 0,
  'public archive provider comes from the signed readiness receipt'
);

select ok(
  position(
    $v$receipt_row.providerisdistinctfrombatch_value->>'provider'$v$
    in regexp_replace(lower(pg_get_functiondef(
      'public.creator_generation_archive(jsonb)'::regprocedure
    )), '[[:space:]]+', '', 'g')
  ) > 0,
  'archive fails closed if persisted batch and signed receipt providers differ'
);

select * from finish();

rollback;
