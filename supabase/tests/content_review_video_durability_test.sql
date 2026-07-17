begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select has_table(
  'content_factory', 'content_review_evidence_sets',
  'durable review evidence sets exist'
);
select has_table(
  'content_factory', 'content_review_evidence_frames',
  'durable review evidence frames exist'
);
select has_table(
  'content_factory', 'content_review_attempts',
  'provider dispatch attempts are journaled'
);
select has_column(
  'content_factory', 'content_review_runs', 'evidence_set_id',
  'review run binds durable evidence'
);
select has_column(
  'content_factory', 'content_review_runs', 'attempt_count',
  'review run tracks bounded attempts'
);
select ok(
  (select relrowsecurity
   from pg_class
   where oid =
     'content_factory.content_review_evidence_sets'::regclass),
  'evidence sets use RLS'
);
select ok(
  (select relrowsecurity
   from pg_class
   where oid = 'content_factory.content_review_attempts'::regclass),
  'attempt journal uses RLS'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_prepare_content_review_evidence(jsonb)',
    'execute'
  ),
  'authenticated creators may prepare video evidence'
);
select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_commit_content_review_evidence(jsonb)',
    'execute'
  ),
  'authenticated creators may commit video evidence'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_begin_content_review_provider_dispatch(jsonb)',
    'execute'
  ),
  'browser sessions cannot mark a paid provider dispatch'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_complete_content_review(jsonb)',
    'execute'
  ),
  'service role may execute fenced completion'
);
select is(
  (select count(*)::integer
   from pg_proc procedure
   join pg_namespace namespace on namespace.oid = procedure.pronamespace
   where namespace.nspname = 'public'
     and procedure.proname in (
       'system_claim_content_review',
       'system_begin_content_review_provider_dispatch',
       'system_release_content_review_attempt',
       'system_complete_content_review',
       'system_reconcile_background_leases'
     )
     and pg_get_functiondef(procedure.oid) like
       '%pg_advisory_xact_lock%'),
  5,
  'attempt lifecycle RPCs share one per-review advisory lock order'
);

insert into auth.users (
  id, instance_id, aud, role, email, encrypted_password,
  email_confirmed_at, raw_app_meta_data, raw_user_meta_data,
  created_at, updated_at
)
values (
  'a1000000-0000-4000-8000-000000000001',
  '00000000-0000-0000-0000-000000000000',
  'authenticated', 'authenticated', 'durable-review@example.test',
  extensions.crypt('test-only-password', extensions.gen_salt('bf')),
  now(), '{"provider":"email","providers":["email"]}'::jsonb,
  '{"display_name":"Durable Review Owner"}'::jsonb, now(), now()
);

insert into content_factory.organizations (id, name, slug, status)
values (
  'a1100000-0000-4000-8000-000000000001',
  'Durable Review Org', 'durable-review-org', 'active'
);
insert into content_factory.memberships (
  organization_id, profile_id, role, status
)
values (
  'a1100000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'owner', 'active'
);
insert into content_factory.media_objects (
  id, organization_id, owner_id, bucket_id, object_name,
  mime_type, size_bytes, sha256, status, metadata, idempotency_key
)
values
  (
    'a1200000-0000-4000-8000-000000000001',
    'a1100000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/durable/source.mp4',
    'video/mp4', 8192, repeat('a', 64), 'ready',
    '{"kind":"source_video","rights_confirmed":true}'::jsonb,
    'durable-review-video-media'
  ),
  (
    'a1200000-0000-4000-8000-000000000002',
    'a1100000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/durable/retry.webp',
    'image/webp', 2048, repeat('b', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'durable-review-image-media'
  ),
  (
    'a1200000-0000-4000-8000-000000000003',
    'a1100000-0000-4000-8000-000000000001',
    'a1000000-0000-4000-8000-000000000001',
    'contentengine-private',
    'a1100000-0000-4000-8000-000000000001/a1000000-0000-4000-8000-000000000001/durable/unknown.webp',
    'image/webp', 2048, repeat('c', 64), 'ready',
    '{"kind":"creator_reference","rights_confirmed":true}'::jsonb,
    'durable-review-unknown-media'
  );

select set_config('request.jwt.claim.role', 'authenticated', true);
select set_config(
  'request.jwt.claim.sub',
  'a1000000-0000-4000-8000-000000000001',
  true
);

select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', 'a1100000-0000-4000-8000-000000000001',
    'idempotency_key', 'durable-video-missing-evidence',
    'media_id', 'a1200000-0000-4000-8000-000000000001',
    'platform', 'vk',
    'product_category', 'other'
  ))$$,
  '22023',
  'content_review_video_evidence_required',
  'an MP4 cannot enter the queue without durable evidence'
);

create temporary table durable_review_context (
  prepare_result jsonb,
  commit_result jsonb,
  review_id uuid,
  claim_result jsonb,
  begin_result jsonb,
  completion_result jsonb
) on commit drop;

insert into durable_review_context (prepare_result)
select public.creator_prepare_content_review_evidence(jsonb_build_object(
  'organization_id', 'a1100000-0000-4000-8000-000000000001',
  'idempotency_key', 'durable-evidence-prepare-0001',
  'media_id', 'a1200000-0000-4000-8000-000000000001',
  'frame_count', 4
));

select is(
  (select prepare_result ->> 'status' from durable_review_context),
  'preparing',
  'prepare returns a durable preparing record'
);
select is(
  (select jsonb_array_length(prepare_result -> 'frame_object_names')
   from durable_review_context),
  4,
  'prepare returns the exact requested frame count'
);
select ok(
  (select bool_and(name like '%.jpg')
   from durable_review_context,
   lateral jsonb_array_elements_text(
     prepare_result -> 'frame_object_names'
   ) object_name(name)),
  'all prepared frame object names are JPEG paths'
);

insert into storage.objects (bucket_id, name, owner, metadata)
select
  'contentengine-private', object_name.name,
  'a1000000-0000-4000-8000-000000000001'::uuid,
  jsonb_build_object('size', 512, 'mimetype', 'image/jpeg')
from durable_review_context,
lateral jsonb_array_elements_text(
  prepare_result -> 'frame_object_names'
) with ordinality object_name(name, ordinal);

update durable_review_context
set commit_result = public.creator_commit_content_review_evidence(
  jsonb_build_object(
    'organization_id', 'a1100000-0000-4000-8000-000000000001',
    'idempotency_key', 'durable-evidence-commit-0001',
    'evidence_id', prepare_result ->> 'evidence_id',
    'technical_metrics', jsonb_build_object(
      'duration_seconds', 8, 'width', 1080, 'height', 1920
    ),
    'frames', (
      select jsonb_agg(jsonb_build_object(
        'object_name', object_name.name,
        'sha256', repeat(object_name.ordinal::text, 64),
        'size_bytes', 512,
        'timecode_seconds', object_name.ordinal - 1
      ) order by object_name.ordinal)
      from jsonb_array_elements_text(
        prepare_result -> 'frame_object_names'
      ) with ordinality object_name(name, ordinal)
    )
  )
);

select is(
  (select commit_result ->> 'status' from durable_review_context),
  'ready',
  'commit verifies storage metadata and makes evidence ready'
);
select is(
  (select count(*)::integer
   from content_factory.content_review_evidence_frames frame
   where frame.evidence_set_id = (
     select (prepare_result ->> 'evidence_id')::uuid
     from durable_review_context
   )),
  4,
  'the immutable evidence manifest stores all frames'
);
select throws_ok(
  $$update content_factory.content_review_evidence_frames
    set size_bytes = size_bytes + 1
    where evidence_set_id = (
      select (prepare_result ->> 'evidence_id')::uuid
      from durable_review_context
    )$$,
  '55000',
  'content_review_evidence_frame_immutable',
  'committed evidence frames cannot be rewritten'
);
select ok(
  not content_factory.storage_object_is_unregistered(
    'contentengine-private',
    (select commit_result #>> '{frames,0,object_name}'
     from durable_review_context)
  ),
  'storage cleanup cannot delete a committed evidence frame'
);
select throws_ok(
  $$select public.creator_start_content_review(jsonb_build_object(
    'organization_id', 'a1100000-0000-4000-8000-000000000001',
    'idempotency_key', 'durable-video-metrics-mismatch',
    'media_id', 'a1200000-0000-4000-8000-000000000001',
    'evidence_id', prepare_result ->> 'evidence_id',
    'platform', 'vk',
    'product_category', 'other',
    'technical_metrics', '{"duration_seconds":7}'::jsonb
  )) from durable_review_context$$,
  '22023',
  'content_review_evidence_metrics_mismatch',
  'start cannot detach provider inputs from committed technical metrics'
);

update content_factory.content_review_evidence_sets evidence
set status = 'consumed', consumed_at = now()
where evidence.id = (
  select (prepare_result ->> 'evidence_id')::uuid
  from durable_review_context
);

insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key, evidence_set_id
)
values (
  'a1300000-0000-4000-8000-000000000001',
  'a1100000-0000-4000-8000-000000000001',
  'a1200000-0000-4000-8000-000000000001',
  'a1000000-0000-4000-8000-000000000001',
  'queued', repeat('a', 64),
  '{"platform":"vk","product_category":"other"}'::jsonb,
  'ugc-rules-2026-07', repeat('d', 64),
  'durable-review-run-0001',
  (select (prepare_result ->> 'evidence_id')::uuid
   from durable_review_context)
);
update durable_review_context
set review_id = 'a1300000-0000-4000-8000-000000000001';

update durable_review_context
set claim_result = public.system_claim_content_review(jsonb_build_object(
  'review_id', review_id
));
select ok(
  (select (claim_result ->> 'claimed')::boolean
   from durable_review_context),
  'worker claims an evidence-backed MP4'
);
select is(
  (select claim_result -> 'evidence' ->> 'frame_count'
   from durable_review_context),
  '4',
  'claim returns the committed evidence manifest'
);
select ok(
  (select claim_result #>> '{attempt,lease_token}' is not null
   from durable_review_context),
  'claim returns a mandatory attempt lease'
);
select is(
  (select public.system_claim_content_review(jsonb_build_object(
    'review_id', review_id
  )) ->> 'claimed' from durable_review_context),
  'false',
  'a second worker observes the lease but cannot own the same claim'
);

update durable_review_context
set begin_result = public.system_begin_content_review_provider_dispatch(
  jsonb_build_object(
    'review_id', review_id,
    'attempt_id', claim_result #>> '{attempt,id}',
    'lease_token', claim_result #>> '{attempt,lease_token}'
  )
);
select is(
  (select begin_result ->> 'provider_dispatch_started'
   from durable_review_context),
  'true',
  'provider POST is preceded by a durable dispatch marker'
);
select is(
  (select public.system_begin_content_review_provider_dispatch(
    jsonb_build_object(
      'review_id', review_id,
      'attempt_id', claim_result #>> '{attempt,id}',
      'lease_token', claim_result #>> '{attempt,lease_token}'
    )
  ) ->> 'idempotent' from durable_review_context),
  'true',
  'dispatch marker replay is idempotent'
);
select throws_ok(
  $$select public.system_release_content_review_attempt(jsonb_build_object(
    'review_id', review_id,
    'attempt_id', claim_result #>> '{attempt,id}',
    'lease_token', claim_result #>> '{attempt,lease_token}',
    'error_code', 'network_retry',
    'error_message', 'Retry requested after provider dispatch.',
    'retryable', true
  )) from durable_review_context$$,
  '55000',
  'content_review_attempt_release_after_dispatch_forbidden',
  'a marked provider POST can never be released for duplicate dispatch'
);

update durable_review_context
set completion_result = public.system_complete_content_review(
  jsonb_build_object(
    'review_id', review_id,
    'attempt_id', claim_result #>> '{attempt,id}',
    'lease_token', claim_result #>> '{attempt,lease_token}',
    'provider_request_id', 'provider-request-durable-0001',
    'status', 'failed',
    'error_code', 'provider_rejected',
    'error_message', 'Provider returned a known terminal rejection.'
  )
);
select is(
  (select completion_result ->> 'attempt_status'
   from durable_review_context),
  'completed',
  'known provider failure completes the exact dispatch attempt'
);
select is(
  (select provider_request_id
   from content_factory.content_review_attempts
   where id = (
     select (claim_result #>> '{attempt,id}')::uuid
     from durable_review_context
   )),
  'provider-request-durable-0001',
  'provider request id is durably journaled'
);
select is(
  (select public.system_complete_content_review(jsonb_build_object(
    'review_id', review_id,
    'attempt_id', claim_result #>> '{attempt,id}',
    'lease_token', claim_result #>> '{attempt,lease_token}',
    'provider_request_id', 'provider-request-durable-0001',
    'status', 'failed',
    'error_code', 'provider_rejected',
    'error_message', 'Provider returned a known terminal rejection.'
  )) ->> 'idempotent' from durable_review_context),
  'true',
  'fenced completion replay is idempotent'
);

-- A pre-dispatch lease may retry, but a post-dispatch lease is unknown/dead.
insert into content_factory.content_review_runs (
  id, organization_id, media_object_id, requested_by, status,
  media_sha256_snapshot, input, ruleset_version, request_hash,
  idempotency_key, attempt_count, next_attempt_at,
  started_at, lease_expires_at
)
values
  (
    'a1300000-0000-4000-8000-000000000002',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000002',
    'a1000000-0000-4000-8000-000000000001',
    'queued', repeat('b', 64), '{"platform":"vk"}'::jsonb,
    'ugc-rules-2026-07', repeat('e', 64),
    'durable-review-retry-run', 1, now(), null, null
  ),
  (
    'a1300000-0000-4000-8000-000000000003',
    'a1100000-0000-4000-8000-000000000001',
    'a1200000-0000-4000-8000-000000000003',
    'a1000000-0000-4000-8000-000000000001',
    'processing', repeat('c', 64), '{"platform":"vk"}'::jsonb,
    'ugc-rules-2026-07', repeat('f', 64),
    'durable-review-unknown-run', 1, null,
    now() - interval '20 minutes', now() - interval '10 minutes'
  );

insert into content_factory.content_review_attempts (
  id, organization_id, review_id, attempt_no, status, lease_token,
  lease_expires_at, provider_idempotency_key,
  provider_dispatch_started_at
)
values
  (
    'a1400000-0000-4000-8000-000000000002',
    'a1100000-0000-4000-8000-000000000001',
    'a1300000-0000-4000-8000-000000000002', 1, 'claimed',
    'a1500000-0000-4000-8000-000000000002',
    now() - interval '10 minutes',
    'content-review:a1300000-0000-4000-8000-000000000002', null
  ),
  (
    'a1400000-0000-4000-8000-000000000003',
    'a1100000-0000-4000-8000-000000000001',
    'a1300000-0000-4000-8000-000000000003', 1, 'dispatching',
    'a1500000-0000-4000-8000-000000000003',
    now() - interval '10 minutes',
    'content-review:a1300000-0000-4000-8000-000000000003',
    now() - interval '15 minutes'
  );

select is(
  public.system_reconcile_background_leases(
    '{"limit":10}'::jsonb
  ) #>> '{review_attempts,retried}',
  '1',
  'expired pre-dispatch claim is retried safely'
);
select is(
  (select status
   from content_factory.content_review_attempts
   where id = 'a1400000-0000-4000-8000-000000000003'),
  'outcome_unknown',
  'expired post-dispatch attempt is outcome unknown'
);
select is(
  (select error_code
   from content_factory.content_review_runs
   where id = 'a1300000-0000-4000-8000-000000000003'),
  'provider_outcome_unknown',
  'unknown provider outcome is terminal and never requeued'
);
select ok(
  (select dead_lettered_at is not null
   from content_factory.content_review_runs
   where id = 'a1300000-0000-4000-8000-000000000003'),
  'unknown provider outcome is visibly dead-lettered'
);

select * from finish();
rollback;
