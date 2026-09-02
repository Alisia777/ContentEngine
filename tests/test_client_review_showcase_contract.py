"""Витрина согласования (ступень 1): контракт схемы и RPC.

Пины: таблицы под FORCE RLS без грантов (доступ только через RPC), токен
генерируется в БД и показывается один раз (в строке — только sha256),
replay по idempotency_key не возвращает токен, анти-энумерация (единый
not_found), идемпотентность решений по client_request_id, append-only
решения, комментарий проходит sensitive-фильтр, уведомление команде.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = (
    ROOT / "supabase/migrations/202609030008_client_review_showcase_v1.sql"
).read_text(encoding="utf-8")
LINK_RPCS = (
    ROOT / "supabase/migrations/202609030009_client_review_link_rpcs_v1.sql"
).read_text(encoding="utf-8")
PUBLIC_RPCS = (
    ROOT / "supabase/migrations/202609030010_client_review_public_rpcs_v1.sql"
).read_text(encoding="utf-8")


def test_schema_is_server_only_and_append_only() -> None:
    assert "force row level security" in SCHEMA
    assert "from public, anon, authenticated, service_role" in SCHEMA
    assert "token_hash ~ '^[0-9a-f]{64}$'" in SCHEMA
    assert "client_review_decision_append_only" in SCHEMA
    # Журнал доступа без FK — живёт и для несуществующих токенов.
    assert "НИКАКИХ FK" in SCHEMA
    # Поля контракта ступени 2 заведены сразу.
    assert "intake_enabled" in SCHEMA
    assert "intake_owner_profile_id" in SCHEMA
    assert "check (decision <> 'returned' or comment is not null)" in SCHEMA


def test_issue_link_token_lifecycle() -> None:
    # Токен: 256 бит из БД, наружу один раз; в строку — только sha256.
    assert "gen_random_bytes(32)" in LINK_RPCS
    assert "'crv1_'" in LINK_RPCS
    assert "digest(token_value, 'sha256')" in LINK_RPCS
    # Replay без токена: восстановить нельзя, только отозвать и выдать.
    replay_block = LINK_RPCS.split("'replayed', true", 1)[1].split(
        "end if;", 1
    )[0]
    assert "token" not in replay_block
    # QA-гейт: approved ИЛИ явная кураторская аттестация.
    assert "client_review_media_not_accepted" in LINK_RPCS
    assert "curator_attested" in LINK_RPCS
    # Роли канона и запрет anon.
    assert "array['owner', 'admin', 'producer', 'operator']" in LINK_RPCS
    assert "client_review_anon_leak_" in LINK_RPCS


def test_public_rpcs_are_anti_enumeration() -> None:
    # Единый ответ на несуществующую/отозванную/истёкшую ссылку.
    assert PUBLIC_RPCS.count("'client_review_not_found'") >= 3
    # Rate-limit по журналу отвечает ДО раскрытия судьбы токена.
    assert "client_review_rate_limited" in PUBLIC_RPCS
    assert "retry_after_seconds" in PUBLIC_RPCS
    # Идемпотентность решения и отсутствие дублей уведомлений.
    assert "client_request_id" in PUBLIC_RPCS
    assert "'replayed', true" in PUBLIC_RPCS
    # Комментарий клиента проходит sensitive-фильтр v491.
    assert "notification_payload_sensitive_v491" in PUBLIC_RPCS
    # Уведомление команде с дедупом.
    assert "'client_review_decision'" in PUBLIC_RPCS
    assert "on conflict (organization_id, recipient_id, dedupe_key)" in (
        PUBLIC_RPCS
    )
    # Системные RPC — только service_role.
    assert "grant execute on function public.system_client_review_view(jsonb)" in PUBLIC_RPCS
    assert "to service_role" in PUBLIC_RPCS
    # Верификация поведением на фейковом токене.
    assert "client_review_view_enumeration_leak" in PUBLIC_RPCS


EDGE = (
    ROOT / "supabase/functions/client-review/index.ts"
).read_text(encoding="utf-8")
PAGE = (ROOT / "web/app/review.html").read_text(encoding="utf-8")
PAGE_JS = (ROOT / "web/app/review.js").read_text(encoding="utf-8")
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
API = (ROOT / "web/app/supabase-api.js").read_text(encoding="utf-8")
SPEND_VIEW = (
    ROOT / "web/app/generation-spend-view.js"
).read_text(encoding="utf-8")


def test_edge_boundary_contract() -> None:
    # Паттерн-чек токена ДО похода в БД; origin переезжает через env.
    assert "REVIEW_TOKEN_PATTERN" in EDGE
    assert 'Deno.env.get("PUBLIC_APP_URL")' in EDGE
    assert "hardliver1.github.io" in EDGE
    assert "SIGNED_URL_TTL_SECONDS = 900" in EDGE
    assert "createSignedUrls" in EDGE
    # HMAC-ключ клиента, а не сырой IP.
    assert "clientKeyHash" in EDGE
    assert "readBoundedStream" in EDGE


def test_review_page_is_light_and_hash_tokened() -> None:
    # Токен в hash, не в query; страница без SPA-бутстрапа.
    assert "#t=" in PAGE_JS or "[#&]t=" in PAGE_JS
    assert "location.hash" in PAGE_JS
    assert "workspace-os" not in PAGE
    assert "app.js" not in PAGE
    assert "config.js" in PAGE
    # CSP: скрипты только свои, медиа — supabase.
    assert "script-src 'self'" in PAGE
    assert "media-src https://*.supabase.co" in PAGE
    # Идемпотентность решения на каждый клик.
    assert "crypto.randomUUID()" in PAGE_JS
    # DOM строится безопасно: чужие строки не идут в innerHTML
    # (в комментарии слово допустимо, присваивание — нет).
    assert ".innerHTML =" not in PAGE_JS
    assert ".innerHTML=" not in PAGE_JS
    # Гейт публичного артефакта: никаких localhost-литералов.
    assert "127.0.0.1" not in PAGE and "localhost" not in PAGE
    assert "127.0.0.1" not in PAGE_JS and "localhost" not in PAGE_JS


def test_spa_issue_dialog_and_api_methods() -> None:
    for rpc in (
        'issueClientReviewLink: "creator_issue_client_review_link"',
        'revokeClientReviewLink: "creator_revoke_client_review_link"',
        'listClientReviewLinks: "creator_list_client_review_links"',
        'listCampaignReviewCandidates:'
        ' "creator_list_campaign_review_candidates"',
    ):
        assert rpc in API, rpc
    assert 'data.version !== "client-review-links-v1"' in API
    # Кнопки на карточке кампании; диалоги и ветки кликов.
    assert 'data-action="open-client-review-issue"' in SPEND_VIEW
    assert 'data-action="open-client-review-links"' in SPEND_VIEW
    assert "function openClientReviewIssueDialog(" in APP
    assert "function openClientReviewLinksDialog(" in APP
    assert 'action === "revoke-client-review-link"' in APP
    # Ссылка показывается один раз, с честным текстом.
    assert "Повторно показать её нельзя" in APP
    assert "review.html#t=" in APP


def test_stage2_client_intake_contract() -> None:
    intake = (
        ROOT / "supabase/migrations/202609030014_client_intake_v1.sql"
    ).read_text(encoding="utf-8")
    intake_rpcs = (
        ROOT
        / "supabase/migrations/202609030015_client_intake_public_rpcs_v1.sql"
    ).read_text(encoding="utf-8")
    # Схема: FORCE RLS, поля брифа только с префиксом brief_, права
    # обязательны на уровне CHECK, лимит файла 50 МБ.
    assert "force row level security" in intake
    assert "rights_confirmed boolean not null default false check (rights_confirmed)" in intake
    assert "size_bytes between 1 and 52428800" in intake
    assert "brief_product" in intake and "brief_audience" in intake
    assert '"name"' not in intake and "'name'" not in intake.replace(
        "policyname", ""
    ).replace("proname", "").replace("relname", "").replace("nspname", "")
    # Системные RPC: суточные лимиты, whitelist типов, анти-энумерация,
    # файл идёт мимо edge по подписанному upload-URL.
    assert "uploads_today >= 20" in intake_rpcs
    assert "briefs_today >= 5" in intake_rpcs
    assert "'image/jpeg', 'image/png', 'image/webp', 'video/mp4'" in intake_rpcs
    assert intake_rpcs.count("client_review_not_found") >= 3
    assert "client_intake_rights_required" in intake_rpcs
    assert "client-intake/" in intake_rpcs
    assert "notification_payload_sensitive_v491" in intake_rpcs
    assert "'client_intake_brief'" in intake_rpcs
    # Edge: intake-действия + подписанный upload-URL.
    assert '"intake_upload_init"' in EDGE.replace("'", '"')
    assert "createSignedUploadUrl" in EDGE
    assert "payload.rights_confirmed !== true" in EDGE
    # Клиентская страница: вкладка, чекбокс прав, прямой PUT в storage.
    assert "Материалы и бриф" in PAGE
    assert "intake_upload_init" in PAGE_JS
    assert '"PUT"' in PAGE_JS
    assert "rightsBox.checked" in PAGE_JS
    # SPA: тумблер ввода и решения по брифу.
    assert 'data-action="toggle-client-intake"' in APP
    assert 'data-action="decide-client-intake-brief"' in APP
    assert 'configureClientReviewIntake: "creator_configure_client_review_intake"' in API


def test_operator_regulations_live_in_academy() -> None:
    # Решение владельца 03.09: регламент оператора — курс академии,
    # а не отдельный док. Сид идемпотентен, аттестация из трёх вопросов.
    course = (
        ROOT
        / "supabase/migrations/202609030013_training_client_review_course.sql"
    ).read_text(encoding="utf-8")
    assert "'client_review_showcase'" in course
    assert "on conflict (code) do update" in course
    for lesson in (
        "issue_link", "curator_responsibility", "token_safety",
        "react_to_decisions", "revoke_and_hygiene",
    ):
        assert f'"{lesson}"' in course, lesson
    # Ключевые правила регламента закреплены текстом уроков.
    assert "РОВНО один раз" in course
    assert "полного просмотра" in course
    assert "Немедленно отозвать" in course
    assert "оператор вручную по правовому чек-листу" in course
    assert "client_review_course_shape_invalid" in course
