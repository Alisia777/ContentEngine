"""Библиотека ведущих проекта для формата «Дуэт».

Формат живёт узнаваемостью: один и тот же человек комментирует все ролики
проекта. Личность закреплена у провайдера идентификатором `avatar_id`, и это
единственное, что связывает наши ролики с одной и той же внешностью — потеряв
его, того же человека не восстановить, новая генерация даст похожего, но
другого.

Отсюда два требования, которые здесь и проверяются:

1. `avatar_id` не приходит из формы. Оператор выбирает ведущего из списка по
   НАШЕМУ идентификатору; подставить в оплачиваемый запрос произвольную
   личность он не может ни ошибкой, ни намеренно. Тот же принцип, по которому
   область замены у «Копии» выводится из проверенной сервером категории.
2. Идентификаторы провайдера не покидают сервер. Витрина списка их не отдаёт,
   таблица закрыта, а функция, которая их читает, недоступна роли браузера.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "supabase" / "migrations"
PRESENTERS = MIGRATIONS / "202608220008_generation_duet_presenters_v1.sql"


def _sql() -> str:
    return PRESENTERS.read_text(encoding="utf-8")


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def test_presenter_table_is_closed_and_has_no_policies() -> None:
    sql = _sql()

    assert "enable row level security" in sql
    assert "force row level security" in sql
    # Доступ только через функции — тот же приём, что у остальных таблиц
    # контура генерации. Любая политика здесь означала бы прямой доступ
    # браузера к идентификаторам провайдера.
    assert "create policy" not in sql.lower()
    assert (
        "revoke all on content_factory.generation_duet_presenters "
        "from anon, authenticated" in sql
    )
    # Проверка стоит и в самой миграции: она упадёт, если политику добавят позже.
    assert "duet_presenters_policy_present" in sql


def test_listing_never_returns_provider_identifiers() -> None:
    """Витрина отдаёт наш id ведущего, но не его личность у провайдера."""

    sql = _sql()
    listing = _between(
        sql,
        "create or replace function public.creator_list_duet_presenters(",
        "create or replace function public.creator_register_duet_presenter(",
    )

    # Наш идентификатор и человеческое имя — да.
    assert "'id', presenter.id" in listing
    assert "'display_name', presenter.display_name" in listing
    # Личность у провайдера — нет. Браузеру она не нужна: он выбирает ведущего
    # по нашему id, а сервер сам подставит avatar_id в платный запрос.
    assert "provider_avatar_id" not in listing
    assert "provider_voice_id" not in listing
    # И миграция стережёт это сама.
    assert "duet_presenters_leak_avatar_id" in sql
    assert "duet_presenters_leak_voice_id" in sql


def test_identity_reader_is_server_only() -> None:
    sql = _sql()

    # Единственная функция, читающая личность, живёт в приватной схеме и явно
    # отобрана у ролей браузера.
    assert (
        "create or replace function content_factory_private.duet_presenter_identity("
        in sql
    )
    assert (
        "revoke all on function content_factory_private.duet_presenter_identity"
        in sql
    )
    assert "from public, anon, authenticated" in sql
    assert "duet_presenter_identity_reachable_by_browser" in sql

    identity = _between(
        sql,
        "create or replace function content_factory_private.duet_presenter_identity(",
        "revoke all on function content_factory_private.duet_presenter_identity",
    )
    # Личность отдаётся в той же форме, которую ждёт адаптер HeyGen.
    for field in ("'avatarId'", "'voiceId'", "'aspectRatio'"):
        assert field in identity
    # И только для своего проекта своей организации: чужого ведущего в платный
    # запрос не подставить даже серверным кодом.
    assert "presenter.organization_id = p_organization_id" in identity
    assert "presenter.project_id = p_project_id" in identity
    assert "presenter.status = 'active'" in identity


def test_project_has_exactly_one_default_presenter() -> None:
    """Постоянный ведущий проекта — один, и смена не требует отказа человеку."""

    sql = _sql()

    assert "generation_duet_presenters_default_key" in sql
    assert "where is_default and status = 'active'" in sql
    # Прежний ведущий уступает место в той же транзакции. Без этого частичный
    # уникальный индекс отверг бы вставку, и человек увидел бы отказ вместо
    # смены ведущего.
    register = _between(
        sql,
        "create or replace function public.creator_register_duet_presenter(",
        "revoke all on function public.creator_list_duet_presenters",
    )
    assert "set is_default = false" in register
    assert register.index("set is_default = false") < register.index(
        "insert into content_factory.generation_duet_presenters"
    )


LIKENESS = MIGRATIONS / "202608220009_duet_presenter_likeness_and_access_v1.sql"


def _likeness_sql() -> str:
    return LIKENESS.read_text(encoding="utf-8")


def test_operator_may_register_a_presenter() -> None:
    """Уточнение владельца 22.08.2026: команда справится.

    Я закрыл регистрацию тремя ролями, рассудив, что ведущий определяет лицо
    всех роликов. Это была предосторожность, а не требование безопасности:
    денег регистрация не тратит, а запуск по-прежнему требует отдельного
    подтверждения суммы.
    """

    sql = _likeness_sql()
    register = _between(
        sql,
        "create or replace function public.creator_register_duet_presenter(",
        "-- Витрина показывает вид ведущего",
    )
    roles = _between(register, "membership_role(", ");")
    assert "'operator'" in roles
    assert "operator_cannot_register_presenter" in sql


def test_a_real_person_cannot_become_a_presenter_without_recorded_consent() -> None:
    """Согласие принадлежит ЧЕЛОВЕКУ, а не ролику.

    В 99% случаев ведущий — живой человек, нанятая модель. Раньше согласие на
    внешность было галочкой на КАЖДОМ запуске: оператор подтверждал его снова и
    снова, глядя на одну и ту же фотографию. Так подтверждение превращается в
    ритуал, который перестают читать.

    Теперь оно записывается один раз, вместе с ведущим, и обязано называть, кто
    подтвердил и когда. Галочка на запуске при этом остаётся: запись говорит
    «право есть», галочка — «применяю его здесь».

    Выдуманный персонаж согласия не требует: требовать его от несуществующего
    человека было бы бессмыслицей.
    """

    sql = _likeness_sql()

    assert "likeness_kind = any (array['real_person', 'synthetic'])" in sql
    # Живой человек не может быть ДЕЙСТВУЮЩИМ ведущим без согласия.
    consent = _between(
        sql,
        "generation_duet_presenters_likeness_consent_check",
        "end if;",
    )
    assert "likeness_kind <> 'real_person'" in consent
    assert "likeness_consent_confirmed" in consent
    assert "likeness_consent_confirmed_by is not null" in consent
    assert "likeness_consent_confirmed_at is not null" in consent

    # И согласие без имени подтвердившего невозможно в принципе — даже у
    # синтетического персонажа и даже в архиве. Согласие без источника это не
    # согласие, а утверждение.
    evidence = _between(
        sql,
        "generation_duet_presenters_consent_evidence_check",
        "end if;",
    )
    assert "not likeness_consent_confirmed" in evidence
    assert "likeness_consent_confirmed_by is not null" in evidence

    # Отказ называет причину прямо, а не сохраняет ведущего неактивным: молча
    # сохранённая строка заставила бы человека думать, что ведущий готов.
    assert "duet_presenter_likeness_consent_required" in sql


def test_identity_reader_refuses_a_person_without_consent() -> None:
    """Последняя преграда перед платным запросом.

    Даже если строка каким-то образом оказалась действующей, запрос ею не
    соберётся: личность живого человека без согласия просто не отдаётся.
    """

    sql = _likeness_sql()
    identity = _between(
        sql,
        "create or replace function content_factory_private.duet_presenter_identity(",
        "revoke all on function content_factory_private.duet_presenter_identity",
    )

    assert "presenter.likeness_kind <> 'real_person'" in identity
    assert "presenter.likeness_consent_confirmed" in identity
    assert "identity_ignores_likeness_consent" in sql
    # Идентификаторы провайдера по-прежнему не покидают сервер.
    assert "duet_presenters_leak_avatar_id" in sql


def test_provider_identifiers_are_bounded_not_guessed() -> None:
    """Идентификаторы провайдера непрозрачны: проверяются границы, а не смысл."""

    sql = _sql()

    assert "provider_avatar_id ~ '^[A-Za-z0-9_-]{8,128}$'" in sql
    assert "provider_voice_id ~ '^[A-Za-z0-9_-]{4,128}$'" in sql
    # Пробелы по краям отбиваются отдельно: незаметный хвост увёл бы платный
    # запрос к несуществующей личности.
    assert "btrim(provider_avatar_id) = provider_avatar_id" in sql
    assert "btrim(provider_voice_id) = provider_voice_id" in sql
    # Рамка ведущего ограничена набором: значение уезжает в оплачиваемый запрос.
    assert "aspect_ratio = any (array['16:9', '9:16', '1:1'])" in sql


def test_migration_does_not_create_or_pay_for_anything_at_the_provider() -> None:
    """Миграция заводит место для ведущего, но не создаёт его у провайдера."""

    sql = _sql()

    # Ни одного обращения наружу: создание аватара стоит $1.00 и живёт отдельно.
    for forbidden in ("http://", "https://", "pg_net", "net.http_post"):
        assert forbidden not in sql


SYNTHETIC = MIGRATIONS / "202608220010_duet_presenter_synthetic_by_default_v1.sql"


def test_a_talking_head_needs_no_consent_at_all() -> None:
    """Ведущий по умолчанию — говорящая голова, а не живой человек.

    Я прочитал фразу владельца «99% это будет живой человек (модель)» как
    «нанятая модель, чьё лицо мы используем», и поставил умолчанием
    `real_person` с обязательным согласием на внешность. Владелец уточнил:
    имелась в виду ИИ-МОДЕЛЬ В ОБЛИКЕ ЧЕЛОВЕКА — говорящая голова. Живого
    человека за ней нет.

    Умолчание оказалось обратным правде, и оно дорого стоило бы: каждое
    заведение ведущего требовало бы подтверждать согласие несуществующего
    человека. Подтверждение, которое нельзя не поставить, перестаёт что-либо
    значить — и обесценивает те случаи, где согласие действительно нужно.
    """

    sql = SYNTHETIC.read_text(encoding="utf-8")

    assert "alter column likeness_kind set default 'synthetic'" in sql
    assert "likeness_kind_value text := 'synthetic'" in sql
    # Проверка стоит в самой миграции: она упадёт, если умолчание вернут.
    assert "likeness_kind_default_not_synthetic" in sql
    assert "register_default_not_synthetic" in sql


def test_a_real_person_still_cannot_slip_through_without_consent() -> None:
    """Редкий случай не значит незащищённый.

    Настоящий человек в роли ведущего возможен: сотрудник, приглашённый
    эксперт, сам владелец. Именно потому, что случай редкий, проверка должна
    быть машинной — на память заводившего тут положиться нельзя.
    """

    sql = SYNTHETIC.read_text(encoding="utf-8")

    assert "likeness_kind_value = 'real_person' and not consent_value" in sql
    assert "duet_presenter_likeness_consent_required" in sql
    # И миграция стережёт, что ограничение не потерялось при перезаписи функции.
    assert "real_person_consent_guard_lost" in sql
    assert "likeness_consent_constraint_lost" in sql
