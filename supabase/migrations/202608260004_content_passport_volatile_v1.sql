begin;
-- 202608260004_content_passport_volatile_v1
--
-- Боевой отказ 26.08 21:09: «Паспорта не загрузились», в postgres_logs —
-- «cannot execute INSERT in a read-only transaction». Оба RPC паспорта были
-- объявлены stable, а content_factory_private.current_profile_id() при
-- каждом вызове обновляет профиль (insert ... on conflict do update):
-- PostgREST исполняет не-volatile функции в read-only транзакции, и запись
-- падает. Действующий образец creator_generation_archive объявлен volatile
-- по той же причине. Данные RPC по-прежнему ничего не меняют сами.

alter function public.creator_content_passport_registry(jsonb) volatile;
alter function public.creator_content_result_passport(jsonb) volatile;

notify pgrst, 'reload schema';

commit;
