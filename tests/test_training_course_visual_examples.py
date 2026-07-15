from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web/app/app.js").read_text(encoding="utf-8")
STYLES = (ROOT / "web/app/styles.css").read_text(encoding="utf-8")

COURSE_CODES = (
    "factory_basics",
    "video_quality",
    "publishing_funnel",
    "security_wb",
)


def _function_source(name: str) -> str:
    start = APP.index(f"function {name}(")
    next_function = APP.find("\nfunction ", start + 1)
    return APP[start : next_function if next_function >= 0 else len(APP)]


def _examples_catalog_source() -> str:
    start = APP.index("const COURSE_VISUAL_EXAMPLES")
    end = APP.index("function courseVisualExamplesMarkup", start)
    return APP[start:end]


def _examples_renderer_source() -> str:
    start = APP.index("function courseVisualExamplesMarkup(")
    end = APP.index("\nfunction lessonMarkup(", start)
    return APP[start:end]


def _course_examples_source(catalog: str, code: str) -> str:
    starts: list[tuple[int, str]] = []
    for candidate in COURSE_CODES:
        match = re.search(
            rf"(?m)^\s*[\"']?{re.escape(candidate)}[\"']?\s*:",
            catalog,
        )
        assert match, f"missing visual examples for {candidate}"
        starts.append((match.start(), candidate))
    starts.sort()
    index = next(i for i, (_, candidate) in enumerate(starts) if candidate == code)
    start = starts[index][0]
    end = starts[index + 1][0] if index + 1 < len(starts) else len(catalog)
    return catalog[start:end]


def _media_blocks(css: str) -> list[str]:
    blocks: list[str] = []
    for match in re.finditer(r"@media\s*\([^)]*\)\s*\{", css):
        depth = 1
        cursor = match.end()
        while cursor < len(css) and depth:
            if css[cursor] == "{":
                depth += 1
            elif css[cursor] == "}":
                depth -= 1
            cursor += 1
        assert depth == 0, "unterminated @media block"
        blocks.append(css[match.start() : cursor])
    return blocks


def test_visual_example_catalog_covers_all_four_courses_and_beginner_scenarios() -> None:
    catalog = _examples_catalog_source()
    course_sources = {
        code: _course_examples_source(catalog, code).casefold()
        for code in COURSE_CODES
    }

    assert all(term in course_sources["factory_basics"] for term in ("портал", "материал"))
    assert all(term in course_sources["video_quality"] for term in ("съ", "9:16", "свет"))
    assert all(
        term in course_sources["publishing_funnel"]
        for term in ("instagram", "youtube", "vk", "прогрев", "реклам")
    )
    assert all(
        term in course_sources["security_wb"]
        for term in ("wildberries", "подмен", "выплат")
    )


def test_course_page_renders_the_course_specific_visual_example_gallery() -> None:
    render_course = _function_source("renderCourse")
    renderer = _examples_renderer_source()

    assert "${courseVisualExamplesMarkup(course.code)}" in render_course
    assert re.search(r"COURSE_VISUAL_EXAMPLES\[(?:safeCode|courseCode)\]", renderer)
    assert "course-example-gallery" in renderer
    assert 'class="course-example-card' in renderer
    assert "map(" in renderer
    assert ".join(\"\")" in renderer or ".join('')" in renderer


def test_visual_example_renderer_escapes_all_authored_copy() -> None:
    renderer = _examples_renderer_source()

    assert renderer.count("escapeHtml(") >= 12
    assert "innerHTML" not in renderer
    assert "outerHTML" not in renderer
    assert 'replace(/[^a-z0-9_-]/g, "")' in renderer
    assert 'new Set(["portal", "shooting", "social", "payout"])' in renderer

    raw_authored_interpolations = re.findall(
        r"\$\{\s*(?:(?:example|item|point|row)\??\.[^}]+|"
        r"(?:step|eyebrow|title|caption|result|visualLabel|platform))\s*\}",
        renderer,
    )
    assert raw_authored_interpolations == []


def test_visual_example_gallery_has_a_single_column_mobile_layout() -> None:
    assert ".course-example-gallery" in STYLES
    assert ".course-example-card" in STYLES

    responsive_blocks = [
        block
        for block in _media_blocks(STYLES)
        if "max-width" in block
        and ".course-example-grid" in block
        and ".course-example-card" in block
    ]
    assert responsive_blocks, "visual examples must have an explicit mobile layout"
    assert any(
        re.search(
            r"\.course-example-grid\s*\{[^}]*grid-template-columns\s*:\s*1fr\s*;",
            block,
            flags=re.DOTALL,
        )
        for block in responsive_blocks
    )
