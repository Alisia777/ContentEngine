from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.ui import templates

router = APIRouter(tags=["altea-motion"])


def _dashboard_context() -> dict:
    return {
        "kpis": [
            {"label": "Выручка", "value": "12 480 000 ₽", "delta": "+18,6%", "icon": "chart"},
            {"label": "Заказы", "value": "1 248", "delta": "+14,2%", "icon": "bag"},
            {"label": "Средний чек", "value": "9 984 ₽", "delta": "+8,7%", "icon": "wallet"},
            {"label": "Конверсия", "value": "2,68%", "delta": "+0,43 п.п.", "icon": "target"},
        ],
        "chart_points": "18,124 88,78 156,68 226,60 294,86 362,72 430,38",
        "tasks": [
            {"title": "Подготовить весеннюю кампанию", "date": "20 мая", "status": "В процессе"},
            {"title": "Обновить карточки товаров", "date": "22 мая", "status": "К выполнению"},
            {"title": "Согласовать контент-план", "date": "23 мая", "status": "На проверке"},
            {"title": "Анализ рекламных кампаний", "date": "25 мая", "status": "К выполнению"},
        ],
        "calendar": [
            {"day": "19", "month": "май", "title": "Запуск новой коллекции", "channel": "Публикация в Instagram и VK", "status": "Запланировано"},
            {"day": "21", "month": "май", "title": "История бренда", "channel": "Публикация в блоге", "status": "Запланировано"},
            {"day": "23", "month": "май", "title": "Обзор новинок", "channel": "Email-рассылка", "status": "Черновик"},
        ],
        "activity": [
            {"title": "Новый заказ №12543", "detail": "Сумма: 12 450 ₽", "time": "10 мин назад"},
            {"title": "Обновлена карточка товара", "detail": "Сыворотка для лица Luxe Elixir", "time": "35 мин назад"},
            {"title": "Опубликован пост в Instagram", "detail": "Весенняя коллекция", "time": "1 ч назад"},
            {"title": "Выгружен отчёт по продажам", "detail": "Отчёт за 12-18 мая", "time": "2 ч назад"},
        ],
        "products": [
            {"name": "Сыворотка Luxe Elixir", "sku": "ALT-001", "revenue": "3 456 000 ₽", "sold": "346", "conversion": "3,12%"},
            {"name": "Крем для лица Velvet Cream", "sku": "ALT-002", "revenue": "2 780 000 ₽", "sold": "278", "conversion": "2,85%"},
            {"name": "Масло для тела Radiance Oil", "sku": "ALT-003", "revenue": "2 145 000 ₽", "sold": "215", "conversion": "2,45%"},
            {"name": "Тоник Balance & Glow", "sku": "ALT-004", "revenue": "1 890 000 ₽", "sold": "189", "conversion": "2,18%"},
        ],
    }


@router.get("/altea-motion")
def altea_motion_home() -> RedirectResponse:
    return RedirectResponse("/altea-motion/splash", status_code=302)


@router.get("/altea-motion/splash", response_class=HTMLResponse)
def altea_motion_splash(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "altea_motion/splash.html",
        {"request": request, "page_title": "ALTEA Motion Splash"},
    )


@router.get("/altea-motion/login", response_class=HTMLResponse)
def altea_motion_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "altea_motion/login.html",
        {"request": request, "page_title": "ALTEA Login"},
    )


@router.get("/altea-motion/auth-loading", response_class=HTMLResponse)
def altea_motion_auth_loading(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "altea_motion/auth_loading.html",
        {"request": request, "page_title": "ALTEA Access Check"},
    )


@router.get("/altea-motion/dashboard-loading", response_class=HTMLResponse)
def altea_motion_dashboard_loading(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "altea_motion/dashboard_loading.html",
        {"request": request, "page_title": "ALTEA Dashboard Loading"},
    )


@router.get("/altea-motion/dashboard", response_class=HTMLResponse)
def altea_motion_dashboard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "altea_motion/dashboard.html",
        {"request": request, "page_title": "ALTEA Dashboard", **_dashboard_context()},
    )
