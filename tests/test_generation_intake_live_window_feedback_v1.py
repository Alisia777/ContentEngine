"""Выбор MP4 в живом окне виден там, где человек его сделал (23.08.2026).

Владелица в зеркале прода: «по-прежнему не загружает ролик». Зонд внутри
встроенного окна показал: файл выбирался, но строка состояния и кнопка
«Разобрать MP4» стояли на ~3800 px ниже зоны выбора — в конце длинной панели
«Дуэта» за семью полями механики. Человек видел ту же пустую рамку.

Контракт: зона выбора называет выбранный файл сама; у «Дуэта» состояние и
кнопки живут в липком подвале; товар, заведённый через «Копию», появляется в
списке «Дуэта» без перезагрузки.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web/app/generation-strategy-intake-v4.js"
CSS = ROOT / "web/app/generation-strategy-intake-v4.css"
DUET_PROBE = ROOT / "scripts/browser_duet_flow_probe.py"
COPY_PROBE = ROOT / "scripts/browser_copy_flow_probe.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_dropzone_names_the_chosen_file_and_its_state() -> None:
    source = text(INTAKE)
    assert 'summary.dataset.generationIntakeSourceFile = route;' in source
    assert "function setSourceFileSummary(panel, text, state" in source
    assert "function sourceFileLead(file)" in source
    # Сразу при выборе — имя и размер; после замера — длительность и следующий шаг.
    assert "`${sourceFileLead(input.files[0])} — проверяем длительность…`" in source
    assert "— выбран. Дальше: ${nextStep}`" in source
    # Отказы по длительности тоже видны в зоне выбора, а не только внизу.
    assert "— длиннее предела ${limit} с, файл не принят`" in source
    assert "— короче ${MIN_COPY_DURATION} с, файл не принят`" in source
    # Разбор и его провал отражаются там же.
    assert "`${sourceFileLead(file)} · ${measured} — разобран`" in source
    assert "— не принят, причина в строке состояния`" in source
    # Выбор ролика проекта снимает сводку загруженного файла.
    assert 'fileInput.value = "";\n        setSourceFileSummary(panel, "");' in source
    css = text(CSS)
    assert ".gi-drop__file {" in css
    assert '.gi-drop[data-has-file="true"] > strong::after' in css


def test_duet_status_and_buttons_live_in_a_sticky_footer() -> None:
    source = text(INTAKE)
    assert "function duetFooter(status, actions)" in source
    assert 'footer.dataset.generationIntakeFooter = "avatar_video";' in source
    assert "duetFooter(statusNode(), actions),\n  );" in source
    css = text(CSS)
    assert ".generation-intake-v4__footer {\n  position: sticky;\n  bottom: 0;" in css
    # В двухколоночной раскладке подвал занимает всю ширину, а не ячейку сетки.
    assert ".generation-intake-v4__actions,\n    .generation-intake-v4__footer\n  ) {\n    grid-column: 1 / -1;" in css


def test_duet_product_list_refreshes_after_copy_registration() -> None:
    source = text(INTAKE)
    assert "let registeredAny = false;" in source
    assert "registeredAny = true;" in source
    assert (
        "if (registeredAny) {\n"
        "      await window.ContentEngineGenerationGuidedV4?.refreshStrategyAssets?.(form);\n"
        "      renderDuetProducts(form, state);"
    ) in source


def test_flow_probes_can_run_inside_the_live_window() -> None:
    for probe in (DUET_PROBE, COPY_PROBE):
        source = text(probe)
        assert '"--in-window"' in source
        assert "window.__ceDoc = () =>" in source
        assert 'iframe[data-ce-v4-window-surface]' in source
        # Ни один селектор экрана не бьёт мимо окна: только логин и оболочка
        # остаются верхнеуровневыми.
        stray = [
            line for line in source.splitlines()
            if "document.querySelector" in line
            and not any(k in line for k in ("input[type=email]", "input[type=password]", "#main-content", "iframe[data-ce-v4-window-surface]"))
        ]
        assert stray == [], stray
    duet = text(DUET_PROBE)
    assert "dropzone does not name the chosen MP4" in duet
