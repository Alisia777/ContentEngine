begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions, pg_temp, pg_catalog;

select plan(9);

-- «Дуэт» после 202608230022: маршрут HeyGen включён, ведёт на v2 (сборка у
-- провайдера), рубильник знает провайдера, ведущий несёт вид личности.

insert into content_factory.organizations (id, name, slug, status)
values (
  '00000000-0000-4000-8000-000000000222'::uuid,
  'Duet v2 fixture',
  'duet-v2-fixture',
  'active'
);

select is(
  (select provider_path from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_avatar_ugc' and provider = 'heygen'),
  '/v2/video/generate',
  'the duet route submits to the v2 video endpoint with a background video'
);

select ok(
  (select enabled and recommended
   from content_factory.generation_strategy_provider_routes
   where strategy_id = 'viral_avatar_ugc' and provider = 'heygen'),
  'the duet route is enabled and is the default engine of its strategy'
);

select ok(
  content_factory_private.generation_strategy_executable_route_exists('viral_avatar_ugc'),
  'the executable-route lock opens for the duet'
);

select ok(
  content_factory_private.generation_provider_launch_enabled(
    '00000000-0000-4000-8000-000000000222', 'heygen', 'avatar_v3'
  ),
  'the launch gate accepts heygen:avatar_v3 for an active organization'
);

select ok(
  content_factory_private.generation_strategy_provider_route_allowed(
    'viral_avatar_ugc', 'heygen', 'avatar_v3', '/v2/video/generate',
    'heygen_video', 'heygen-usd-per-second-2026-08-22.v1'
  )
  and not content_factory_private.generation_strategy_provider_route_allowed(
    'viral_avatar_ugc', 'heygen', 'avatar_v3', '/v3/videos',
    'heygen_video', 'heygen-usd-per-second-2026-08-22.v1'
  ),
  'the executable pair names the v2 path and no longer the v3 one'
);

select is(
  content_factory_private.generation_strategy_recipe_price(
    'viral_avatar_ugc', 10, '720p', 'source', false
  ) ->> 'spend_confirmation',
  'HEYGEN_PRODUCT_UGC_10S_720P_SILENT_USD_0.50',
  'ten seconds of duet cost fifty cents under the HeyGen confirmation prefix'
);

select has_column(
  'content_factory', 'generation_duet_presenters', 'provider_avatar_kind',
  'presenters carry the provider identity kind (talking_photo | avatar)'
);

select throws_ok(
  $$insert into content_factory.generation_duet_presenters
      (organization_id, project_id, display_name, provider_avatar_id,
       provider_voice_id, created_by, provider_avatar_kind)
    values ('00000000-0000-4000-8000-000000000222', gen_random_uuid(), 'x',
            'a', 'v', gen_random_uuid(), 'hologram')$$,
  '23514',
  null,
  'an unknown avatar kind is rejected'
);

select ok(
  position('avatarKind' in pg_get_functiondef(
    'content_factory_private.duet_presenter_identity(uuid,uuid,uuid)'::regprocedure
  )) > 0,
  'the presenter identity read by dispatch carries the avatar kind'
);

select * from finish();
rollback;
