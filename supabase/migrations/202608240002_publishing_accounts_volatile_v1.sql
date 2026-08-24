begin;
-- 202608240002_publishing_accounts_volatile_v1
--
-- creator_publishing_accounts (202608240001) была объявлена STABLE, но
-- приватные помощники контура (current_profile_id / resolve_organization)
-- дозаписывают строки при первом обращении. PostgREST исполняет stable-функции
-- в read-only транзакции, поэтому форма «Разместить» падала с 25006
-- «cannot execute INSERT in a read-only transaction», а браузеру уходил 405.
-- Все creator_* RPC контура — volatile; выравниваем и эту.

alter function public.creator_publishing_accounts(jsonb) volatile;

commit;
