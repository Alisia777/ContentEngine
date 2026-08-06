begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;
select no_plan();

select is(
  content_factory_private.research_youtube_video_id(
    'https://www.youtube.com/shorts/GW-NfEVlPGc'
  ),
  'GW-NfEVlPGc',
  'the supplied air-fryer Shorts URL resolves to the exact YouTube identity'
);
select is(
  content_factory_private.research_youtube_video_id(
    'https://www.youtube.com/watch?v=GW-NfEVlPGc&utm_source=test'
  ),
  'GW-NfEVlPGc',
  'watch aliases resolve to the same YouTube identity'
);
select is(
  content_factory_private.research_youtube_video_id(
    'https://youtu.be/GW-NfEVlPGc?si=example'
  ),
  'GW-NfEVlPGc',
  'youtu.be aliases resolve to the same YouTube identity'
);
select is(
  content_factory_private.research_youtube_video_id(
    'https://www.youtube.com/embed/GW-NfEVlPGc'
  ),
  'GW-NfEVlPGc',
  'embed aliases resolve to the same YouTube identity'
);
select is(
  content_factory_private.research_youtube_video_id(
    'https://www.youtube.com/live/GW-NfEVlPGc?feature=share'
  ),
  'GW-NfEVlPGc',
  'live aliases resolve to the same YouTube identity'
);
select is(
  content_factory_private.research_youtube_video_id(
    'http://www.youtube.com/shorts/GW-NfEVlPGc'
  ),
  null,
  'non-HTTPS YouTube examples are rejected'
);
select is(
  content_factory_private.research_youtube_video_id(
    'https://example.com/shorts/GW-NfEVlPGc'
  ),
  null,
  'non-YouTube hosts are rejected'
);

select has_function(
  'public',
  'creator_register_research_training_example',
  array['jsonb'],
  'authenticated research example RPC exists'
);
select has_function(
  'public',
  'system_register_research_training_example',
  array['jsonb'],
  'service-only research example RPC exists'
);

select ok(
  has_function_privilege(
    'authenticated',
    'public.creator_register_research_training_example(jsonb)',
    'execute'
  ),
  'authenticated members can call the narrow creator RPC'
);
select ok(
  not has_function_privilege(
    'anon',
    'public.creator_register_research_training_example(jsonb)',
    'execute'
  ),
  'anonymous users cannot register research examples'
);
select ok(
  has_function_privilege(
    'service_role',
    'public.system_register_research_training_example(jsonb)',
    'execute'
  ),
  'service role can perform the protected one-time repair'
);
select ok(
  not has_function_privilege(
    'authenticated',
    'public.system_register_research_training_example(jsonb)',
    'execute'
  ),
  'browser sessions cannot call the service repair wrapper'
);

select * from finish();
rollback;
