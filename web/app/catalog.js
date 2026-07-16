/**
 * Stable navigation identifiers only.
 *
 * Course copy, lessons, exam prompts and answer options are deliberately not
 * bundled into the browser. Supabase is the sole source of the learning
 * catalog, and the SPA fails closed when that catalog is incomplete.
 */

export const FINAL_EXAM_CODE = "operator_final_exam";

export const REQUIRED_MODULE_CODES = Object.freeze([
  "factory_basics",
  "video_quality",
  "publishing_funnel",
  "security_wb",
]);

export const NAVIGATION_MODE_STORAGE_KEY = "contentengine.navigation-mode.v1";

export const NAVIGATION_MODES = Object.freeze([
  Object.freeze({
    id: "simple",
    label: "Простой",
    description: "Основной производственный путь без служебных разделов",
  }),
  Object.freeze({
    id: "all",
    label: "Все инструменты",
    description: "Весь доступный набор рабочих и управленческих разделов",
  }),
]);

export const SIMPLE_WORKSPACE_TAB_KEYS = Object.freeze([
  "home",
  "work",
  "media",
  "generation",
  "review",
  "tasks",
  "placement",
  "stats",
  "payouts",
]);

export const WORKSPACE_TABS = Object.freeze([
  ["media", "Материалы", "▧"],
  ["generation", "Создание видео", "✦"],
  ["review", "Проверка контента", "◈"],
  ["tasks", "Задачи", "✓"],
  ["placement", "Публикации", "↗"],
  ["stats", "Результаты", "◫"],
  ["payouts", "Выплаты", "₽"],
  ["work", "Моя работа", "●"],
  ["board", "Рабочий стол", "▦"],
  ["research", "Разбор товара", "⌕"],
  ["feedback", "Помощь и идеи", "+"],
  ["team", "Команда", "◎"],
]);
