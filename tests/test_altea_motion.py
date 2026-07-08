from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_altea_motion_splash_page_renders():
    response = client.get("/altea-motion/splash")
    assert response.status_code == 200
    assert "ALTEA" in response.text
    assert "Инициализация" in response.text
    assert "Загрузка данных" in response.text


def test_altea_motion_login_page_renders():
    response = client.get("/altea-motion/login")
    assert response.status_code == 200
    assert "Введите логин" in response.text
    assert "Введите пароль" in response.text
    assert "Войти" in response.text


def test_altea_motion_auth_loading_page_renders():
    response = client.get("/altea-motion/auth-loading")
    assert response.status_code == 200
    assert "Проверка доступа" in response.text
    assert "Загрузка профиля" in response.text
    assert "ALTEA Beauty" in response.text


def test_altea_motion_dashboard_loading_page_renders():
    response = client.get("/altea-motion/dashboard-loading")
    assert response.status_code == 200
    assert "Загружаем данные" in response.text
    assert "altea-skeleton" in response.text


def test_altea_motion_dashboard_page_renders():
    response = client.get("/altea-motion/dashboard")
    assert response.status_code == 200
    assert "Панель управления" in response.text
    assert "Динамика выручки" in response.text
    assert "Топ товаров" in response.text


def test_altea_motion_static_css_and_js_exist():
    static_root = Path("app/static/altea_motion")
    assert (static_root / "altea_motion.css").exists()
    assert (static_root / "altea_motion.js").exists()
    assert (static_root / "assets/logo_mark.svg").exists()
    assert (static_root / "assets/altea_flower.svg").exists()


def test_altea_motion_pages_use_local_assets_not_external_cdns():
    pages = [
        "/altea-motion/splash",
        "/altea-motion/login",
        "/altea-motion/auth-loading",
        "/altea-motion/dashboard-loading",
        "/altea-motion/dashboard",
    ]
    for path in pages:
        response = client.get(path)
        assert "https://cdn" not in response.text.lower()
        assert "unpkg.com" not in response.text.lower()
        assert "cdnjs" not in response.text.lower()
        assert "/static/altea_motion/" in response.text


def test_altea_motion_has_reduced_motion_css():
    css = Path("app/static/altea_motion/altea_motion.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in css
    assert "petalDrift" in css
    assert "chartDraw" in css


def test_altea_motion_dashboard_contains_required_russian_labels():
    response = client.get("/altea-motion/dashboard")
    for label in [
        "Главная",
        "Показатели",
        "Заказы",
        "Клиенты",
        "Каталог",
        "Контент",
        "Маркетинг",
        "Отчёты",
        "Интеграции",
        "Настройки",
        "Экспорт отчёта",
    ]:
        assert label in response.text


def test_altea_motion_login_contains_login_password_and_enter_button():
    response = client.get("/altea-motion/login")
    assert "Логин" in response.text
    assert "Пароль" in response.text
    assert "Войти" in response.text
    assert "Восстановить доступ" in response.text
