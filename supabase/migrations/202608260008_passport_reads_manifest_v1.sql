begin;
-- 202608260008_passport_reads_manifest_v1
--
-- Паспорт читает манифест происхождения (202608260007): секция manifest в
-- ответе, а provenance_manifest уходит из missing_sections только когда
-- манифест реально существует. Патч действующего определения по точным
-- якорям (прецедент — 202608170001): каждый якорь проверяется, отсутствие —
-- отказ миграции, а не тихий no-op.

do $mig$
declare
  src text;
begin
  src := pg_get_functiondef(
    'public.creator_content_result_passport(jsonb)'::regprocedure
  );

  if strpos(src, 'manifest_row') > 0 then
    raise exception 'passport_manifest_patch_already_applied';
  end if;

  if strpos(src, 'spec_row content_factory.generation_spec_versions%rowtype;') = 0
     or strpos(src, 'if job_row.generation_spec_id is not null then') = 0
     or strpos(src, 'missing_value jsonb := ''["hypothesis", "provenance_manifest"]''::jsonb;') = 0
     or strpos(src, '''hypothesis'', null,') = 0 then
    raise exception 'passport_manifest_patch_anchor_missing';
  end if;

  src := replace(src,
    'spec_row content_factory.generation_spec_versions%rowtype;',
    'spec_row content_factory.generation_spec_versions%rowtype;
  manifest_row content_factory.generation_provenance_manifests%rowtype;');

  src := replace(src,
    'missing_value jsonb := ''["hypothesis", "provenance_manifest"]''::jsonb;',
    'missing_value jsonb := ''["hypothesis"]''::jsonb;');

  src := replace(src,
    'if job_row.generation_spec_id is not null then',
    'select manifest.* into manifest_row
  from content_factory.generation_provenance_manifests manifest
  where manifest.organization_id = organization_id
    and manifest.generation_job_id = job_row.id;
  if manifest_row.id is null then
    missing_value := missing_value
      || to_jsonb(''provenance_manifest''::text);
  end if;

  if job_row.generation_spec_id is not null then');

  src := replace(src,
    '''hypothesis'', null,',
    '''hypothesis'', null,
    ''manifest'', case
      when manifest_row.id is null then null
      else jsonb_build_object(
        ''manifest_hash'', manifest_row.manifest_hash,
        ''version'', ''generation-provenance-v1'',
        ''created_at'', manifest_row.created_at
      )
    end,');

  execute src;
end
$mig$;

commit;
