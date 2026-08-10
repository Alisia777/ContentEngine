from __future__ import annotations

import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
DRAFT = APP / "exact-youtube-research-draft.js"
INTAKE = APP / "workspace-research-video-intake.js"
RECOVERY = APP / "workspace-research-failure-recovery.js"


def run_node(source: str) -> dict[str, object]:
    completed = subprocess.run(
        ["node", "--input-type=module", "-e", source],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def test_scope_bound_draft_round_trip_and_safe_hydration() -> None:
    media_a = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    media_b = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    script = f"""
      const mod = await import({json.dumps(DRAFT.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const scope = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      const requestedAt = '2026-08-10T15:00:00.000Z';
      const wrote = mod.writeExactYoutubeResearchDraft(storage, {{
        ...scope,
        requested_at: requestedAt,
        product_category: 'household',
        category_name: 'Аэрогрили и мультипечи',
        research_focus: 'Результат сначала, затем быстрый процесс и payoff',
        marketplace_url: 'https://www.wildberries.ru/catalog/518413561/detail.aspx',
        competitor_references: 'чужой ролик только как ориентир механики',
        objective: 'conversion',
        known_facts: '4 л; 1500 Вт; 10 программ; окно; гарантия 3 года',
        platforms: ['youtube', 'wildberries', 'youtube', 'invalid'],
        source_media_ids: [
          '{media_a}', '{media_a}', '{media_b}', 'not-a-uuid',
        ],
        paid_analysis_ack: true,
      }});
      const read = mod.readExactYoutubeResearchDraft(storage, scope, {{
        now: Date.parse(requestedAt) + 1_000,
      }});
      const hydration = mod.exactYoutubeResearchHydration(
        read.draft,
        ['{media_b}', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'],
        'Разобрать переносимую механику пяти контрольных кадров.',
      );
      const raw = JSON.parse(values.get(
        mod.EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY,
      ));
      const wrongUser = mod.readExactYoutubeResearchDraft(storage, {{
        ...scope,
        user_id: '66666666-6666-4666-8666-666666666666',
      }}, {{ now: Date.parse(requestedAt) + 1_000 }});
      const expired = mod.readExactYoutubeResearchDraft(storage, scope, {{
        now: Date.parse(requestedAt)
          + mod.EXACT_YOUTUBE_RESEARCH_DRAFT_MAX_AGE_MS + 1,
      }});
      process.stdout.write(JSON.stringify({{
        wrote,
        readOk: read.ok,
        category: hydration.productCategory,
        marketplace: hydration.marketplaceUrl,
        platforms: hydration.platforms,
        selectedPhoto: hydration.sourceMediaId,
        objectiveHasFacts: hydration.objective.includes('4 л; 1500 Вт'),
        objectiveHasFocus: hydration.objective.includes('Результат сначала'),
        objectiveBounded:
          hydration.objective.length >= 20 && hydration.objective.length <= 1200,
        acknowledgementsStored:
          Object.hasOwn(raw, 'paid_analysis_ack')
          || Object.hasOwn(raw, 'human_review_ack'),
        wrongUser: wrongUser.code,
        expired: expired.code,
      }}));
    """
    assert run_node(script) == {
        "wrote": True,
        "readOk": True,
        "category": "household",
        "marketplace": (
            "https://www.wildberries.ru/catalog/518413561/detail.aspx"
        ),
        "platforms": ["youtube", "wildberries"],
        "selectedPhoto": media_b,
        "objectiveHasFacts": True,
        "objectiveHasFocus": True,
        "objectiveBounded": True,
        "acknowledgementsStored": False,
        "wrongUser": "draft_scope_mismatch",
        "expired": "draft_expired",
    }


def test_invalid_values_fail_closed_without_cosmetics_fallback() -> None:
    script = f"""
      const mod = await import({json.dumps(DRAFT.as_uri())});
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
      }};
      const scope = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      mod.writeExactYoutubeResearchDraft(storage, {{
        ...scope,
        product_category: 'not-a-category',
        marketplace_url: 'http://unsafe.example/product',
        platforms: ['invalid'],
      }});
      const read = mod.readExactYoutubeResearchDraft(storage, scope);
      const hydration = mod.exactYoutubeResearchHydration(read.draft, []);
      const raw = JSON.parse(values.get(
        mod.EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY,
      ));
      values.set(
        mod.EXACT_YOUTUBE_RESEARCH_DRAFT_STORAGE_KEY,
        JSON.stringify({{ ...raw, version: 2 }}),
      );
      const unknownVersion = mod.readExactYoutubeResearchDraft(storage, scope);
      process.stdout.write(JSON.stringify({{ hydration, unknownVersion }}));
    """
    assert run_node(script) == {
        "hydration": {
            "productCategory": "",
            "marketplaceUrl": "",
            "platforms": [],
            "sourceMediaId": "",
            "objective": "",
        },
        "unknownVersion": {
            "ok": False,
            "code": "draft_payload_invalid",
        },
    }


def test_exact_form_hydrates_only_fresh_intersected_context_and_no_acks() -> None:
    photo = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    other_photo = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    script = f"""
      class FakeInput {{
        constructor(name, value = '', type = 'text') {{
          this.name = name; this.value = value; this.type = type;
          this.checked = false;
        }}
      }}
      class FakeTextArea extends FakeInput {{}}
      class FakeSelect {{
        constructor(name, options) {{
          this.name = name; this.options = options;
          this.value = options[0]?.value || '';
        }}
        querySelector(selector) {{
          return selector === 'option[value=""]'
            ? this.options.find((item) => item.value === '') || null
            : null;
        }}
        prepend(option) {{ this.options.unshift(option); }}
      }}
      class FakeForm {{
        constructor(controls, radios, platforms) {{
          this.dataset = {{}};
          this.controls = controls;
          this.radios = radios;
          this.platforms = platforms;
          this.elements = {{ namedItem: (name) => controls[name] || null }};
        }}
        querySelectorAll(selector) {{
          if (selector.includes('radio') && selector.includes('source_media_id')) return this.radios;
          if (selector.includes('checkbox') && selector.includes('platforms')) return this.platforms;
          return [];
        }}
      }}
      globalThis.HTMLInputElement = FakeInput;
      globalThis.HTMLTextAreaElement = FakeTextArea;
      globalThis.HTMLSelectElement = FakeSelect;
      globalThis.HTMLFormElement = FakeForm;
      globalThis.HTMLAnchorElement = class {{}};
      globalThis.HTMLElement = class {{}};
      const values = new Map();
      const storage = {{
        getItem: (key) => values.get(key) ?? null,
        setItem: (key, value) => values.set(key, value),
        removeItem: (key) => values.delete(key),
      }};
      const scope = {{
        organization_id: '11111111-1111-4111-8111-111111111111',
        user_id: '22222222-2222-4222-8222-222222222222',
        session_id: '33333333-3333-4333-8333-333333333333',
        project_id: '44444444-4444-4444-8444-444444444444',
        source_id: '55555555-5555-4555-8555-555555555555',
      }};
      const category = new FakeSelect('product_category', [
        {{ value: 'cosmetics' }}, {{ value: 'household' }},
      ]);
      const marketplace = new FakeInput('marketplace_url');
      const objective = new FakeTextArea(
        'objective',
        'Разобрать механику пяти контрольных кадров без копирования.',
      );
      const acknowledgements = [
        'media_matches_registered_source', 'external_ai_processing_ack',
        'paid_analysis_ack', 'human_review_ack',
      ].map((name) => {{ const input = new FakeInput(name, 'on', 'checkbox'); input.checked = true; return input; }});
      const controls = {{ product_category: category, marketplace_url: marketplace, objective }};
      for (const input of acknowledgements) controls[input.name] = input;
      const radios = [
        new FakeInput('source_media_id', '{other_photo}', 'radio'),
        new FakeInput('source_media_id', '{photo}', 'radio'),
      ];
      const platforms = ['youtube', 'instagram', 'wildberries'].map(
        (value) => {{ const input = new FakeInput('platforms', value, 'checkbox'); input.checked = true; return input; }},
      );
      const form = new FakeForm(controls, radios, platforms);
      globalThis.document = {{
        getElementById: (id) => id === 'exact-youtube-research-evidence-form' ? form : null,
        createElement: () => ({{ value: '', textContent: '', disabled: false }}),
        querySelectorAll: () => [],
      }};
      globalThis.window = {{
        location: {{ hash: '#/workspace/review?purpose=exact_youtube_research&project_id=' + scope.project_id + '&youtube_source=' + scope.source_id }},
        sessionStorage: storage,
        addEventListener: () => {{}},
        queueMicrotask: () => {{}},
        ContentEngineWorkspaceRuntime: {{
          getExactYoutubeHandoffContext: () => scope,
        }},
      }};
      const draft = await import({json.dumps(DRAFT.as_uri())});
      draft.writeExactYoutubeResearchDraft(storage, {{
        ...scope,
        product_category: 'household',
        marketplace_url: 'https://www.wildberries.ru/catalog/518413561/detail.aspx',
        research_focus: 'результат сначала',
        known_facts: '10 программ',
        platforms: ['youtube', 'wildberries'],
        source_media_ids: ['{photo}'],
      }});
      const recovery = await import({json.dumps(RECOVERY.as_uri())});
      const hydrated = recovery.hydrateExactYoutubeResearchDraft();
      process.stdout.write(JSON.stringify({{
        hydrated,
        category: category.value,
        placeholder: category.options[0].value,
        marketplace: marketplace.value,
        objectiveHasFocus: objective.value.includes('результат сначала'),
        objectiveHasFacts: objective.value.includes('10 программ'),
        selectedPhoto: radios.find((item) => item.checked)?.value || '',
        selectedPlatforms: platforms.filter((item) => item.checked).map((item) => item.value),
        acknowledgements: acknowledgements.map((item) => item.checked),
      }}));
    """
    assert run_node(script) == {
        "hydrated": True,
        "category": "household",
        "placeholder": "",
        "marketplace": (
            "https://www.wildberries.ru/catalog/518413561/detail.aspx"
        ),
        "objectiveHasFocus": True,
        "objectiveHasFacts": True,
        "selectedPhoto": photo,
        "selectedPlatforms": ["youtube", "wildberries"],
        "acknowledgements": [False, False, False, False],
    }


def test_runtime_wiring_preserves_context_but_never_acknowledgements() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    recovery = RECOVERY.read_text(encoding="utf-8")
    for marker in (
        "writeExactYoutubeResearchDraft",
        "exactYoutubeResearchDraftInput(form)",
        'product_category: fieldText(form, ["product_category"]',
        'source_media_ids: checkedFieldValues(form, "source_media_ids")',
        'platforms: checkedFieldValues(form, "platforms")',
    ):
        assert marker in intake
    for marker in (
        "readExactYoutubeResearchDraft",
        "exactYoutubeResearchHydration",
        "hydrateExactYoutubeResearchDraft",
        'option.textContent = "Выберите категорию"',
        'category.value = validCategory ? hydration.productCategory : ""',
        "selected.has(input.value)",
        "input.value === hydration.sourceMediaId",
        '"paid_analysis_ack"',
        '"human_review_ack"',
        "acknowledgement.checked = false",
        "clearCompletedExactResearchDraft",
    ):
        assert marker in recovery


def test_changed_browser_modules_parse() -> None:
    for path in (DRAFT, INTAKE, RECOVERY):
        subprocess.run(["node", "--check", str(path)], check=True, cwd=ROOT)
