begin;
-- 202608250002_admin_waiver_transition_v1
--
-- Пара к 202608250001: словарь granted_role пополнился admin, но матрица
-- допустимых переходов (role_transition_check) знала лишь пары
-- operator←viewer/trainee/operator и owner←owner. Добавляем ветку admin —
-- вейвер сохраняется при повышении сотрудника до admin из любой рабочей роли.

alter table content_factory.training_access_waivers
  drop constraint training_access_waivers_role_transition_check;

alter table content_factory.training_access_waivers
  add constraint training_access_waivers_role_transition_check
  check (
    (granted_role = 'operator'::text
      and previous_role = any (array['viewer'::text, 'trainee'::text, 'operator'::text]))
    or (granted_role = 'owner'::text and previous_role = 'owner'::text)
    or (granted_role = 'admin'::text
      and previous_role = any (array['viewer'::text, 'trainee'::text, 'operator'::text, 'admin'::text]))
  );

commit;
