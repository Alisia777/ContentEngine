begin;
-- 202608250001_admin_training_waiver_v1
--
-- Владелец поднимает партнёра до admin («прямо макс доступ, чтобы всё видел»,
-- 25.08.2026), сохраняя ему выданный 12.08 вейвер «без обучения». Словарь
-- granted_role вейверов предусматривал только operator/owner — admin не мог
-- существовать без курсов: производственные разделы (каталог проверки, запуск
-- генерации) зовут membership_role с учебным гейтом для любой роли, и смена
-- роли молча отключала бы действующий вейвер (join по membership.role =
-- waiver.granted_role). Расширяем словарь на admin; сам механизм выдачи и
-- отзыва не меняется.

alter table content_factory.training_access_waivers
  drop constraint training_access_waivers_granted_role_check;

alter table content_factory.training_access_waivers
  add constraint training_access_waivers_granted_role_check
  check (granted_role = any (array['operator'::text, 'owner'::text, 'admin'::text]));

commit;
