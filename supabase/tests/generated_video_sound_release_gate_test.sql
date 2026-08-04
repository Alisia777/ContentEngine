begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(41);

select has_table(
  'content_factory', 'content_review_sound_assessments',
  'generated-video sound assessments are persisted'
);

select has_column(
  'content_factory', 'content_review_sound_assessments', 'assessment_hash',
  'each assessment has a bounded server-owned hash'
);

select has_column(
  'content_factory', 'content_review_sound_assessments',
  'source_assessment_id',
  'context copies retain explicit assessment lineage'
);

select ok(
  (
    select table_row.relrowsecurity
    from pg_class table_row
    where table_row.oid =
      'content_factory.content_review_sound_assessments'::regclass
  ),
  'sound assessments keep RLS enabled'
);

select is(
  (
    select count(*)::integer
    from (values
      ('select'), ('insert'), ('update'), ('delete')
    ) privilege_name(name)
    where has_table_privilege(
      'authenticated',
      'content_factory.content_review_sound_assessments',
      privilege_name.name
    )
  ),
  0,
  'authenticated users cannot bypass the assessment RPCs'
);

select ok(
  exists (
    select 1
    from pg_trigger trigger_row
    where trigger_row.tgrelid =
          'content_factory.content_review_sound_assessments'::regclass
      and trigger_row.tgname =
          'reject_content_review_sound_assessment_mutation'
      and not trigger_row.tgisinternal
  ),
  'sound assessment rows are append-only'
);

select ok(
  exists (
    select 1
    from pg_index index_row
    join pg_attribute attribute_row
      on attribute_row.attrelid = index_row.indrelid
     and attribute_row.attnum = any(index_row.indkey)
    where index_row.indrelid =
          'content_factory.content_review_sound_assessments'::regclass
      and index_row.indisunique
      and attribute_row.attname = 'review_id'
  ),
  'one immutable assessment is allowed per exact review'
);

select is(
  content_factory_private.content_review_sound_issue_codes_valid(
    jsonb_build_array(
      'slurred_words', 'wrong_words', 'foreign_accent',
      'numbers_units', 'wrong_voice_tone', 'lip_sync',
      'noise_clipping', 'silence_dropout', 'unexpected_audio', 'other'
    )
  ),
  true,
  'the complete fixed issue-code vocabulary is accepted'
);

select is(
  content_factory_private.content_review_sound_issue_codes_valid(
    '["invented_issue"]'::jsonb
  ),
  false,
  'unknown sound issue codes are rejected'
);

select is(
  content_factory_private.content_review_sound_issue_codes_valid(
    '["wrong_words","wrong_words"]'::jsonb
  ),
  false,
  'duplicate sound issue codes are rejected'
);

select is(
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb_build_object(
      'audio', true,
      'status', 'clear',
      'issue_codes', jsonb_build_array(),
      'spoken_script_heard_exactly_confirmed', true,
      'diction_clear_confirmed', true,
      'voice_style_confirmed', true,
      'audio_sync_confirmed', true,
      'silence_expected_confirmed', false,
      'note', 'Every spoken word and ending was checked.'
    ),
    'approved'
  ) ->> 'status',
  'clear',
  'audible approval accepts only a clear assessment'
);

select is(
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb_build_object(
      'audio', false,
      'status', 'silent_expected',
      'issue_codes', jsonb_build_array(),
      'spoken_script_heard_exactly_confirmed', false,
      'diction_clear_confirmed', false,
      'voice_style_confirmed', false,
      'audio_sync_confirmed', false,
      'silence_expected_confirmed', true,
      'note', 'This visual was intentionally generated without sound.'
    ),
    'approved'
  ) ->> 'status',
  'silent_expected',
  'intentional silence is an explicit approvable state'
);

select is(
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb_build_object(
      'audio', true,
      'status', 'issues_found',
      'issue_codes', jsonb_build_array(
        'wrong_words', 'noise_clipping'
      ),
      'spoken_script_heard_exactly_confirmed', false,
      'diction_clear_confirmed', false,
      'voice_style_confirmed', true,
      'audio_sync_confirmed', true,
      'silence_expected_confirmed', false,
      'note', 'The first word is wrong and the ending clips.'
    ),
    'needs_changes'
  ) -> 'issue_codes',
  '["noise_clipping","wrong_words"]'::jsonb,
  'issue codes are normalized deterministically for hashing'
);

select is(
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb_build_object(
      'audio', false,
      'status', 'issues_found',
      'issue_codes', jsonb_build_array('unexpected_audio'),
      'spoken_script_heard_exactly_confirmed', false,
      'diction_clear_confirmed', false,
      'voice_style_confirmed', false,
      'audio_sync_confirmed', false,
      'silence_expected_confirmed', false,
      'note', 'Unexpected speech is audible in the silent render.'
    ),
    'needs_changes'
  ) ->> 'status',
  'issues_found',
  'unexpected audio in a server-silent job can be returned for repair'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', false,
          'status', 'issues_found',
          'issue_codes', jsonb_build_array('wrong_words'),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', false,
          'audio_sync_confirmed', false,
          'silence_expected_confirmed', false,
          'note', 'Unexpected speech is audible.'
        ),
        'needs_changes'
      )
  $$,
  '22023',
  'content_review_sound_issues_invalid',
  'audio=false issues require the dedicated unexpected_audio code'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'issues_found',
          'issue_codes', jsonb_build_array('slurred_words'),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false,
          'note', 'Words are swallowed.'
        ),
        'approved'
      )
  $$,
  '55000',
  'content_review_sound_issues_block_approval',
  'issues_found cannot be approved'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'clear',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', true,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_clear_invalid',
  'approval fails when the exact spoken script was not confirmed'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'clear',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', true,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_clear_invalid',
  'approval fails when diction is not clear'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'clear',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', true,
          'diction_clear_confirmed', true,
          'voice_style_confirmed', false,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_clear_invalid',
  'approval fails when the requested voice style was not confirmed'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'clear',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', true,
          'diction_clear_confirmed', true,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', false,
          'silence_expected_confirmed', false
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_clear_invalid',
  'approval fails when audio synchronization was not confirmed'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', false,
          'status', 'silent_expected',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', false,
          'audio_sync_confirmed', false,
          'silence_expected_confirmed', false
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_silence_invalid',
  'silent approval requires an explicit expected-silence confirmation'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'issues_found',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', false,
          'audio_sync_confirmed', false,
          'silence_expected_confirmed', false
        ),
        'needs_changes'
      )
  $$,
  '22023',
  'content_review_sound_issues_invalid',
  'issues_found requires at least one fixed issue code'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'issues_found',
          'issue_codes', jsonb_build_array('wrong_words'),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false,
          'note', 'bad'
        ),
        'needs_changes'
      )
  $$,
  '22023',
  'content_review_sound_issues_note_required',
  'issues_found requires a useful bounded note'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'clear',
          'issue_codes', jsonb_build_array(),
          'spoken_script_heard_exactly_confirmed', true,
          'diction_clear_confirmed', true,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false,
          'note', repeat('x', 1001)
        ),
        'approved'
      )
  $$,
  '22023',
  'content_review_sound_assessment_value_invalid',
  'assessment notes are bounded'
);

select is(
  content_factory_private.normalize_content_review_sound_assessment(
    jsonb_build_object(
      'audio', true,
      'status', 'issues_found',
      'issue_codes', jsonb_build_array('wrong_words'),
      'spoken_script_heard_exactly_confirmed', false,
      'diction_clear_confirmed', false,
      'voice_style_confirmed', true,
      'audio_sync_confirmed', true,
      'silence_expected_confirmed', false,
      'note', E'First line.\r\nSecond line.'
    ),
    'needs_changes'
  ) ->> 'note',
  E'First line.\nSecond line.',
  'textarea CRLF is normalized to bounded LF text'
);

select throws_ok(
  $$
    select content_factory_private
      .normalize_content_review_sound_assessment(
        jsonb_build_object(
          'audio', true,
          'status', 'issues_found',
          'issue_codes', jsonb_build_array('wrong_words'),
          'spoken_script_heard_exactly_confirmed', false,
          'diction_clear_confirmed', false,
          'voice_style_confirmed', true,
          'audio_sync_confirmed', true,
          'silence_expected_confirmed', false,
          'note', 'bad' || chr(1) || 'control'
        ),
        'needs_changes'
      )
  $$,
  '22023',
  'content_review_sound_assessment_value_invalid',
  'non-whitespace control characters remain forbidden'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_decide_content_review_without_sound_release_gate(jsonb)'
  ) is not null,
  'the prior decision chain remains private and callable by its wrapper'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'
  ) is not null,
  'the prior context-approval chain remains private'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_content_review_status_without_sound_release_gate(jsonb)'
  ) is not null,
  'the prior status chain remains private'
);

select ok(
  to_regprocedure(
    'content_factory_private.creator_content_review_catalog_without_sound_release_gate(jsonb)'
  ) is not null,
  'the prior catalog chain remains private'
);

select is(
  (
    select count(*)::integer
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname in (
        'creator_decide_content_review',
        'creator_approve_generated_video_review_with_context',
        'creator_content_review_status',
        'creator_content_review_catalog'
      )
      and function_row.prosecdef
  ),
  4,
  'all four browser wrappers remain SECURITY DEFINER'
);

select is(
  (
    select count(*)::integer
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname in (
        'creator_decide_content_review',
        'creator_approve_generated_video_review_with_context',
        'creator_content_review_status',
        'creator_content_review_catalog'
      )
      and has_function_privilege(
        'authenticated', function_row.oid, 'execute'
      )
  ),
  4,
  'authenticated members retain access to the wrapped RPCs'
);

select is(
  (
    select count(*)::integer
    from pg_proc function_row
    join pg_namespace namespace_row
      on namespace_row.oid = function_row.pronamespace
    where namespace_row.nspname = 'public'
      and function_row.proname in (
        'creator_decide_content_review',
        'creator_approve_generated_video_review_with_context',
        'creator_content_review_status',
        'creator_content_review_catalog'
      )
      and has_function_privilege('anon', function_row.oid, 'execute')
  ),
  0,
  'anonymous callers cannot use the wrapped RPCs'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%content_review_sound_assessment_required%'
  and pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%record_content_review_sound_assessment%'
  and pg_get_functiondef(
    'content_factory_private.creator_decide_content_review_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%context_copy%',
  'preserved decision wrapper requires, stores, and lineage-copies sound assessment'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_with_context_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%''context_source''%'
  and pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_with_context_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%''context_copy''%'
  and pg_get_functiondef(
    'content_factory_private.creator_approve_generated_video_review_pre_sound_gate_v1(jsonb)'
      ::regprocedure
  ) like '%public.creator_decide_content_review%',
  'context approval stores source assessment and delegates child copy'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.creator_content_review_status_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%sound_assessment_history%'
  and pg_get_functiondef(
    'content_factory_private.creator_content_review_catalog_pre_project_v47(jsonb)'
      ::regprocedure
  ) like '%sound_assessment_history%',
  'preserved status and catalog expose bounded assessment history'
);

select ok(
  not has_function_privilege(
    'authenticated',
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)',
    'execute'
  ),
  'browser sessions cannot call the assessment writer directly'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%content_review_sound_assessment_conflict%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%context_amendment,source_completion_hash%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%assessment_hash_value%',
  'writer is idempotent and binds copies to exact completion lineage'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%when ''seedance2_fast'' then true%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%when ''gen4_turbo'' then false%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%content_review_sound_audio_mismatch%',
  'client audio is checked against immutable media and job model truth'
);

select ok(
  pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%generated_video_spoken_script%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%spoken_script_source%generation_job_prompt_v1%'
  and pg_get_functiondef(
    'content_factory_private.record_content_review_sound_assessment(uuid,uuid,uuid,uuid,jsonb,text,uuid)'
      ::regprocedure
  ) like '%content_review_sound_spoken_script_provenance_invalid%',
  'audible Seedance release requires the exact immutable prompt script binding'
);

select ok(
  (
    select count(*) = 3
    from pg_constraint constraint_row
    where constraint_row.conrelid =
          'content_factory.content_review_sound_assessments'::regclass
      and constraint_row.contype = 'f'
      and pg_get_constraintdef(constraint_row.oid) like
          '%content_review_%'
  ),
  'assessment rows bind reviews, decisions, and source lineage by foreign key'
);

select * from finish();
rollback;
