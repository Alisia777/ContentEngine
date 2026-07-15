from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GUIDES = (ROOT / "web" / "app" / "account-launch-guides.js").read_text(encoding="utf-8")


def test_each_required_platform_has_a_beginner_launch_guide():
    for slug, name, format_name in (
        ("instagram", "Instagram", "Reels"),
        ("youtube", "YouTube", "Shorts"),
        ("vk", "VK", "VK Клипы"),
    ):
        assert f'{slug}: Object.freeze({{' in GUIDES
        assert f'slug: "{slug}"' in GUIDES
        assert f'name: "{name}"' in GUIDES
        assert f'format: "{format_name}"' in GUIDES


def test_guides_cover_the_full_zero_to_first_publication_route():
    required_sections = (
        "registration: Object.freeze([",
        "profile: Object.freeze([",
        "ramp: SHARED_RAMP",
        "allowed: Object.freeze([",
        "stop: Object.freeze([",
        "publish: Object.freeze([",
        "sources: Object.freeze([",
    )
    for section in required_sections:
        assert GUIDES.count(section) == 3


def test_warmup_guidance_avoids_fake_safe_quotas_and_automation():
    assert "избегает придуманных дневных лимитов" not in GUIDES
    assert "avoids invented daily quotas" in GUIDES
    for prohibited_pattern in ("подписок в день", "лайков в день", "комментариев в день"):
        assert prohibited_pattern not in GUIDES.lower()
    for risk in ("ботами", "Массовые подписки", "покупка лайков", "искусственное вовлечение"):
        assert risk.lower() in GUIDES.lower()


def test_advertising_gate_never_teaches_label_evasion():
    assert "ADVERTISING_DECISION_STEPS" in GUIDES
    assert "Остановитесь и передайте публикацию руководителю" in GUIDES
    assert "Не пытайтесь убрать признаки рекламы формулировками" in GUIDES
    assert "Попытка замаскировать рекламный характер публикации" in GUIDES


def test_only_official_https_sources_are_embedded():
    allowed_hosts = (
        "https://www.facebook.com/help/instagram/",
        "https://support.google.com/youtube/",
        "https://vk.com/",
        "https://ads.vk.com/help",
    )
    source_lines = [line.strip() for line in GUIDES.splitlines() if "url:" in line]
    assert len(source_lines) >= 12
    for line in source_lines:
        assert any(host in line for host in allowed_hosts), line


def test_youtube_guide_covers_paid_and_synthetic_disclosures():
    assert "paid promotion" in GUIDES.lower()
    assert "Использование ИИ / изменённый или синтетический контент" in GUIDES
    assert "AI use / altered or synthetic content" in GUIDES
    assert "answer/154235" in GUIDES
    assert "answer/14328491" in GUIDES
