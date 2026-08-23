from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web" / "app" / "generation-strategy-intake-v4.js"
APP = ROOT / "web" / "app" / "app.js"
AUTOPILOT = ROOT / "web" / "app" / "generation-autopilot.js"
GUIDED = ROOT / "web" / "app" / "workspace-os-v4-generation-guided.js"
SOURCE_PICKER = ROOT / "web" / "app" / "generation-strategy-source-picker.js"


def _between(source: str, start: str, end: str) -> str:
    return source.split(start, 1)[1].split(end, 1)[0]


def _express_helpers(intake: str) -> str:
    """Маршрутные помощники экспресс-пути (23.08.2026): «Копия» и «Дуэт»
    ведут мастер одной машиной, и извлечённые функции ссылаются на них."""
    return "const EXPRESS_ROUTES" + _between(
        intake,
        "const EXPRESS_ROUTES",
        "function priceButtonFor",
    )


def _run_node(source: str, *, timeout: int = 20) -> dict[str, object]:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI regressions"
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_registered_compact_mp4_materializes_real_picker_and_survives_catalog_failure() -> None:
    guided = GUIDED.read_text(encoding="utf-8")
    source_candidates = "function strategySourceCandidates" + _between(
        guided,
        "function strategySourceCandidates",
        "function registeredSourceCandidate",
    )
    registered_candidate = "function registeredSourceCandidate" + _between(
        guided,
        "function registeredSourceCandidate",
        "function materializeRegisteredStrategySource",
    )
    materialize = "function materializeRegisteredStrategySource" + _between(
        guided,
        "function materializeRegisteredStrategySource",
        "function confirmRegisteredStrategySourceProbe",
    )
    confirm_probe = "function confirmRegisteredStrategySourceProbe" + _between(
        guided,
        "function confirmRegisteredStrategySourceProbe",
        "function syncStrategySourcePickerState",
    )
    payload = _run_node(
        f"""
const {{
  GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS,
  createGenerationStrategySourcePicker,
  generationStrategySourcePickerProjection,
  reduceGenerationStrategySourcePicker,
}} = await import({json.dumps(SOURCE_PICKER.as_uri())});
const STRATEGY_REPEAT_MEDIA_ID_PATTERN =
  /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu;
const projectId = "11111111-1111-4111-8111-111111111111";
const mediaId = "22222222-2222-4222-8222-222222222222";
const runtime = {{
  strategyAssetPage: null,
  strategyRegisteredSourceProjectId: "",
  strategyRegisteredSources: new Map(),
}};
const generationStrategyProjectId = () => projectId;
let syncCalls = 0;
const syncStrategyAssetCandidates = () => {{ syncCalls += 1; }};
{source_candidates}
{registered_candidate}
{materialize}
{confirm_probe}

const form = {{ isConnected: true }};
const materialized = materializeRegisteredStrategySource(form, {{
  media_id: mediaId,
  filename: "ContentEngine_GRILL_SWAP_SOURCE_12s_9x16.mp4",
  duration_seconds: null,
}});
let picker = createGenerationStrategySourcePicker(
  "viral_product_swap",
  strategySourceCandidates(),
);
picker = reduceGenerationStrategySourcePicker(picker, {{
  type: GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.toggle,
  source_media_id: mediaId,
}});
const before = generationStrategySourcePickerProjection(picker);

const confirmed = confirmRegisteredStrategySourceProbe(form, {{
  media_id: mediaId,
  duration_seconds: 12.04,
}});
// A later handoff replay still carries null; it must not erase the successful
// server probe while the broader catalog is stale or unavailable.
const replayed = materializeRegisteredStrategySource(form, {{
  media_id: mediaId,
  duration_seconds: null,
}});
picker = reduceGenerationStrategySourcePicker(picker, {{
  type: GENERATION_STRATEGY_SOURCE_PICKER_ACTIONS.replaceCandidates,
  strategy_id: "viral_product_swap",
  candidates: strategySourceCandidates(),
}});
const after = generationStrategySourcePickerProjection(picker);

process.stdout.write(JSON.stringify({{
  materialized,
  confirmed,
  replayed,
  syncCalls,
  before: {{
    selectedCount: before.selected_count,
    probeIds: before.probe_required_source_ids,
    allReady: before.all_selected_ready,
  }},
  after: {{
    selectedCount: after.selected_count,
    probeIds: after.probe_required_source_ids,
    allReady: after.all_selected_ready,
    duration: after.selected[0]?.duration_seconds,
  }},
}}));
"""
    )

    assert payload == {
        "materialized": True,
        "confirmed": True,
        "replayed": True,
        "syncCalls": 3,
        "before": {
            "selectedCount": 1,
            "probeIds": ["22222222-2222-4222-8222-222222222222"],
            "allReady": False,
        },
        "after": {
            "selectedCount": 1,
            "probeIds": [],
            "allReady": True,
            "duration": 12.04,
        },
    }


def test_hidden_handoff_rehydrates_exact_mp4_after_form_remount() -> None:
    guided = GUIDED.read_text(encoding="utf-8")
    source_candidates = "function strategySourceCandidates" + _between(
        guided,
        "function strategySourceCandidates",
        "function registeredSourceCandidate",
    )
    registered_candidate = "function registeredSourceCandidate" + _between(
        guided,
        "function registeredSourceCandidate",
        "function materializeRegisteredStrategySource",
    )
    normalize_handoff = "function normalizeIntakeHandoff" + _between(
        guided,
        "function normalizeIntakeHandoff",
        "function intakeHandoffFromHiddenFields",
    )
    hidden_handoff = "function intakeHandoffFromHiddenFields" + _between(
        guided,
        "function intakeHandoffFromHiddenFields",
        "function intakeHandoffFromSession",
    )
    media_id = "22222222-2222-4222-8222-222222222222"
    payload = _run_node(
        f"""
const STRATEGY_REPEAT_MEDIA_ID_PATTERN =
  /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu;
const projectId = "11111111-1111-4111-8111-111111111111";
const runtime = {{
  strategyAssetPage: null,
  strategyRegisteredSourceProjectId: "",
  strategyRegisteredSources: new Map(),
}};
const generationStrategyProjectId = () => projectId;
const generationStrategyAssetEligibility = (asset) => ({{
  eligible: asset?.catalogEligible === true,
}});
{source_candidates}
{registered_candidate}
{normalize_handoff}
{hidden_handoff}

const values = {{
  generation_intake_version: "generation-intake-mp4-v4",
  generation_intake_route: "copy_video",
  generation_intake_source_media_id: {json.dumps(media_id)},
  generation_intake_source_duration_seconds: "12",
  generation_intake_source_url: "",
  generation_intake_description: "",
  generation_intake_recommendation_source: "empty",
  generation_intake_model: "fal-ai:kling-video-o3-pro",
  generation_strategy_prefill_assets: JSON.stringify([{{
    role: "source_video",
    media_id: {json.dumps(media_id)},
    duration_seconds: 12,
  }}]),
}};
const form = {{
  elements: Object.fromEntries(
    Object.entries(values).map(([name, value]) => [name, {{ value }}]),
  ),
}};
const handoff = intakeHandoffFromHiddenFields(form);
const source = registeredSourceFromHiddenHandoff(form);
const hydrated = hydrateRegisteredSourceFromHiddenHandoff(form);
const restored = runtime.strategyRegisteredSources.get({json.dumps(media_id)});
const candidates = strategySourceCandidates();
const partialCatalogSource = {{
  id: {json.dumps(media_id)},
  kind: "source_video",
  mime_type: "video/mp4",
  status: "ready",
  rights_confirmed: true,
  exact_youtube_attached: false,
  direct_mp4_attached: false,
  duration_seconds: 12,
  catalogEligible: false,
}};
runtime.strategyAssetPage = {{ assets: [partialCatalogSource] }};
runtime.strategyRegisteredSources.clear();
const partialCatalogHydrated = hydrateRegisteredSourceFromHiddenHandoff(form);
const partialCatalogRetained = runtime.strategyRegisteredSources.has(
  {json.dumps(media_id)},
);
runtime.strategyAssetPage = {{
  assets: [{{
    ...partialCatalogSource,
    direct_mp4_attached: true,
    catalogEligible: true,
  }}],
}};
const completeCatalogHydrated = hydrateRegisteredSourceFromHiddenHandoff(form);
const completeCatalogWon = !runtime.strategyRegisteredSources.has(
  {json.dumps(media_id)},
);
runtime.strategyAssetPage = null;
runtime.strategyRegisteredSources.clear();
runtime.intakeHandoff = handoff;
form.elements.generation_intake_version.value = "";
const sessionHydrated = hydrateRegisteredSourceFromHiddenHandoff(form);
const sessionRestored = runtime.strategyRegisteredSources.get({json.dumps(media_id)});
form.elements.generation_intake_version.value = "generation-intake-mp4-v4";
form.elements.generation_intake_route.value = "avatar_video";
const nonCopyRejected = registeredSourceFromHiddenHandoff(form) === null;
form.elements.generation_intake_route.value = "copy_video";
form.elements.generation_strategy_prefill_assets.value = "not-json";
const malformedRejected = registeredSourceFromHiddenHandoff(form) === null;
form.elements.generation_strategy_prefill_assets.value = JSON.stringify([{{
  role: "source_video",
  media_id: "33333333-3333-4333-8333-333333333333",
  duration_seconds: 12,
}}]);
const mismatchedRejected = registeredSourceFromHiddenHandoff(form) === null;
form.elements.generation_strategy_prefill_assets.value = JSON.stringify([
  {{ role: "source_video", media_id: {json.dumps(media_id)}, duration_seconds: 12 }},
  {{ role: "source_video", media_id: {json.dumps(media_id)}, duration_seconds: 12 }},
]);
const duplicateRejected = registeredSourceFromHiddenHandoff(form) === null;
form.elements.generation_strategy_prefill_assets.value = JSON.stringify([{{
  role: "source_video",
  media_id: {json.dumps(media_id)},
  duration_seconds: 8,
}}]);
const durationMismatch = registeredSourceFromHiddenHandoff(form)?.duration_seconds ?? null;
process.stdout.write(JSON.stringify({{
  sourceMediaId: handoff?.source_media_id || "",
  sourceDuration: handoff?.source_duration_seconds ?? null,
  assetCount: handoff?.assets?.length || 0,
  hydrated,
  restoredId: restored?.id || "",
  restoredDuration: restored?.duration_seconds ?? null,
  ready: restored?.eligible === true,
  candidates: candidates.map((candidate) => candidate.id),
  partialCatalogHydrated,
  partialCatalogRetained,
  completeCatalogHydrated,
  completeCatalogWon,
  sessionHydrated,
  sessionRestoredId: sessionRestored?.id || "",
  nonCopyRejected,
  malformedRejected,
  mismatchedRejected,
  duplicateRejected,
  durationMismatch,
}}));
"""
    )

    assert payload == {
        "sourceMediaId": media_id,
        "sourceDuration": 12,
        "assetCount": 1,
        "hydrated": True,
        "restoredId": media_id,
        "restoredDuration": 12,
        "ready": True,
        "candidates": [media_id],
        "partialCatalogHydrated": True,
        "partialCatalogRetained": True,
        "completeCatalogHydrated": True,
        "completeCatalogWon": True,
        "sessionHydrated": True,
        "sessionRestoredId": media_id,
        "nonCopyRejected": True,
        "malformedRejected": True,
        "mismatchedRejected": True,
        "duplicateRejected": True,
        "durationMismatch": None,
    }
    sync_contract = _between(
        guided,
        "function syncStrategyAssetCandidates",
        "async function loadGenerationStrategyAssets",
    )
    assert "hydrateRegisteredSourceFromHiddenHandoff(form)" in sync_contract
    setup_contract = _between(guided, "function setupForm", "function normalizeIntakeHandoff")
    assert setup_contract.index(
        "hydrateRegisteredSourceFromHiddenHandoff(form);"
    ) < setup_contract.index("if (!initialSync)")
    mount_contract = _between(
        guided,
        "function mount()",
        "window.ContentEngineDesktopV4.registerAdapter",
    )
    form_changed = _between(
        mount_contract,
        "if (formChanged)",
        "runtime.form = form",
    )
    assert "runtime.intakeHandoff = null" not in form_changed
    assert "runtime.intakeHandoffProjectId !== mountedProjectId" in mount_contract


def test_compact_handoff_reapplies_server_duration_and_primary_on_native_nodes() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        subject = Path(temporary_directory) / "subject.mjs"
        shutil.copyfile(INTAKE, subject)
        payload = _run_node(
            f"""
globalThis.window = {{
  location: {{ hash: "#/outside" }},
  addEventListener() {{}},
}};
globalThis.document = {{ documentElement: {{}} }};
globalThis.MutationObserver = class {{ observe() {{}} }};
globalThis.Event = class {{
  constructor(type) {{ this.type = type; }}
}};
globalThis.HTMLInputElement = class {{
  constructor(value = "") {{
    this.value = value;
    this.name = "";
    this.checked = false;
    this.disabled = false;
    this.min = "";
    this.max = "";
    this.dataset = {{}};
    this.events = [];
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
  closest() {{ return null; }}
}};

const subject = await import({json.dumps(subject.as_uri())});
const ids = {{
  seven: "70000000-0000-4000-8000-000000000007",
  six: "60000000-0000-4000-8000-000000000006",
  four: "40000000-0000-4000-8000-000000000004",
  eight: "80000000-0000-4000-8000-000000000008",
}};
const clickOrder = [ids.seven, ids.six, ids.four, ids.eight];
const domOrder = [ids.eight, ids.six, ids.four, ids.seven];
const orderById = new Map(clickOrder.map((id, index) => [id, index + 1]));
const products = domOrder.map((id) => {{
  const input = new HTMLInputElement(id);
  input.name = "media_id";
  input.checked = true;
  input.dataset.generationIntakeSelectionOrder = String(orderById.get(id));
  return input;
}});
const radios = domOrder.map((id) => {{
  const input = new HTMLInputElement(id);
  input.name = "primary_media_id";
  return input;
}});
const duration = new HTMLInputElement("10");
duration.name = "generation_strategy_duration_seconds";
duration.min = "4";
duration.max = "15";
const emptyCompactSlot = {{ querySelectorAll() {{ return []; }} }};
const form = {{
  dataset: {{}},
  elements: {{ generation_strategy_duration_seconds: duration }},
  querySelector(selector) {{
    return selector === ".generation-intake-v4__product-items"
      ? emptyCompactSlot
      : null;
  }},
  querySelectorAll(selector) {{
    if (selector === 'input[name="media_id"]:checked') return products;
    if (selector === 'input[name="primary_media_id"]') return radios;
    return [];
  }},
}};
const sourceId = "123f0000-0000-4000-8000-000000000005";
const handoff = {{
  source_media_id: sourceId,
  source_duration_seconds: 5,
  product_media_ids: clickOrder,
  assets: [
    {{ role: "source_video", media_id: sourceId, duration_seconds: 5 }},
    ...clickOrder.map((media_id) => ({{ role: "new_product_image", media_id }})),
  ],
}};

const selectedAfterMove = subject.selectedProductMediaIds(form);
const durationApplied = subject.applyHandoffSourceDuration(form, handoff);
const primaryApplied = subject.bindHandoffPrimaryProduct(form, handoff);
const primary = radios.find((radio) => radio.checked)?.value || "";
duration.value = "10";
const rejectedMismatch = subject.applyHandoffSourceDuration(form, {{
  ...handoff,
  source_duration_seconds: 6,
}});

process.stdout.write(JSON.stringify({{
  selectedAfterMove,
  durationApplied,
  durationAfterApply: duration.events.length === 2 ? "5" : "event-missing",
  primaryApplied,
  primary,
  rejectedMismatch,
  durationAfterMismatch: duration.value,
}}));
"""
        )

    assert payload == {
        "selectedAfterMove": [
            "70000000-0000-4000-8000-000000000007",
            "60000000-0000-4000-8000-000000000006",
            "40000000-0000-4000-8000-000000000004",
            "80000000-0000-4000-8000-000000000008",
        ],
        "durationApplied": True,
        "durationAfterApply": "5",
        "primaryApplied": True,
        "primary": "70000000-0000-4000-8000-000000000007",
        "rejectedMismatch": False,
        "durationAfterMismatch": "10",
    }


def test_fresh_uploaded_synthetic_products_have_exact_first_primary_fail_closed() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        subject = Path(temporary_directory) / "subject.mjs"
        shutil.copyfile(INTAKE, subject)
        payload = _run_node(
            f"""
class Element {{
  constructor(tagName = "div") {{
    this.tagName = String(tagName).toUpperCase();
    this.className = "";
    this.textContent = "";
    this.hidden = false;
    this.dataset = {{}};
    this.children = [];
    this.parentElement = null;
  }}
  append(...nodes) {{
    nodes.forEach((node) => {{
      if (!(node instanceof Element)) return;
      if (node.parentElement) {{
        node.parentElement.children = node.parentElement.children.filter(
          (candidate) => candidate !== node,
        );
      }}
      node.parentElement = this;
      this.children.push(node);
    }});
  }}
  matches(selector) {{
    if (selector.startsWith(".")) {{
      const className = selector.slice(1);
      return this.className.split(/\\s+/u).includes(className);
    }}
    if (selector === "[data-generation-intake-synthetic]") {{
      return this.dataset.generationIntakeSynthetic !== undefined;
    }}
    const input = selector.match(
      /^input\\[name="([^"]+)"\\](?:\\[value="([^"]*)"\\])?$/u,
    );
    return Boolean(
      input
      && this instanceof HTMLInputElement
      && this.name === input[1]
      && (input[2] === undefined || this.value === input[2]),
    );
  }}
  querySelectorAll(selector) {{
    const found = [];
    const visit = (node) => {{
      node.children.forEach((child) => {{
        if (child.matches(selector)) found.push(child);
        visit(child);
      }});
    }};
    visit(this);
    return found;
  }}
  querySelector(selector) {{ return this.querySelectorAll(selector)[0] || null; }}
  closest(selector) {{
    let current = this;
    while (current) {{
      if (current.matches(selector)) return current;
      current = current.parentElement;
    }}
    return null;
  }}
}}
globalThis.HTMLElement = Element;
globalThis.HTMLInputElement = class extends Element {{
  constructor() {{
    super("input");
    this.type = "";
    this.name = "";
    this.value = "";
    this.checked = false;
    this.disabled = false;
    this.events = [];
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
}};
globalThis.HTMLSelectElement = class extends Element {{}};
globalThis.HTMLOptionElement = class extends Element {{}};
globalThis.HTMLButtonElement = class extends Element {{}};
globalThis.HTMLTextAreaElement = class extends Element {{}};
globalThis.Event = class {{
  constructor(type) {{ this.type = type; }}
}};
globalThis.CSS = {{ escape(value) {{ return String(value); }} }};
const root = new Element("html");
const head = new Element("head");
globalThis.document = {{
  documentElement: root,
  head,
  styleSheets: [],
  createElement(tagName) {{
    return String(tagName).toLowerCase() === "input"
      ? new HTMLInputElement()
      : new Element(tagName);
  }},
  querySelector(selector) {{ return root.querySelector(selector); }},
  querySelectorAll(selector) {{ return root.querySelectorAll(selector); }},
}};
globalThis.window = {{
  location: {{ hash: "#/outside" }},
  addEventListener() {{}},
}};
globalThis.MutationObserver = class {{ observe() {{}} }};

const subject = await import({json.dumps(subject.as_uri())});
const ids = [
  "70000000-0000-4000-8000-000000000007",
  "60000000-0000-4000-8000-000000000006",
  "40000000-0000-4000-8000-000000000004",
  "80000000-0000-4000-8000-000000000008",
];
const form = new Element("form");
const slot = new Element("div");
slot.className = "generation-intake-v4__product-items";
form.append(slot);
const state = {{ shell: form }};
const identity = {{ sku: "ROASTER-1", product_name: "ROASTER grill" }};
ids.forEach((id, index) => {{
  subject.ensureProductCheckbox(form, state, id, identity, `photo-${{index + 1}}.webp`);
}});
// Catalog/DOM order is not click order. The handoff array remains authoritative.
slot.children.reverse();
const before = form.querySelectorAll('input[name="primary_media_id"]');
const bound = subject.bindHandoffPrimaryProduct(form, {{ product_media_ids: ids }});
const checked = form.querySelectorAll('input[name="primary_media_id"]')
  .filter((radio) => radio.checked)
  .map((radio) => radio.value);
const chosen = before.find((radio) => radio.value === ids[0]);

const invalidForm = new Element("form");
const invalidSlot = new Element("div");
invalidSlot.className = "generation-intake-v4__product-items";
invalidForm.append(invalidSlot);
subject.ensureProductCheckbox(
  invalidForm,
  {{ shell: invalidForm }},
  "50000000-0000-4000-8000-000000000005",
  null,
  "unidentified.webp",
);
const invalidRadios = invalidForm.querySelectorAll('input[name="primary_media_id"]');
const invalidBound = subject.bindHandoffPrimaryProduct(invalidForm, {{
  product_media_ids: ["50000000-0000-4000-8000-000000000005"],
}});

process.stdout.write(JSON.stringify({{
  radioCount: before.length,
  allRadiosHiddenInitially: before.every((radio) => radio.parentElement.hidden),
  bound,
  checked,
  chosenEvents: chosen?.events || [],
  invalidRadioCount: invalidRadios.length,
  invalidBound,
}}));
"""
        )

    assert payload == {
        "radioCount": 4,
        "allRadiosHiddenInitially": True,
        "bound": True,
        "checked": ["70000000-0000-4000-8000-000000000007"],
        "chosenEvents": ["input", "change"],
        "invalidRadioCount": 0,
        "invalidBound": False,
    }


def test_product_move_keeps_checkbox_primary_pair_and_prune_transfers_order() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    move_contract = "function collectProductNodes" + _between(
        intake,
        "function collectProductNodes",
        "function mediaIdFromNode",
    )
    prune_contract = "function pruneSyntheticProductOptions" + _between(
        intake,
        "function pruneSyntheticProductOptions",
        "function bindRoleAsset",
    )
    payload = _run_node(
        f"""
class Element {{
  constructor(tagName = "div") {{
    this.tagName = String(tagName).toLowerCase();
    this.className = "";
    this.textContent = "";
    this.dataset = {{}};
    this.children = [];
    this.parentElement = null;
    this.events = [];
  }}
  append(...nodes) {{
    nodes.forEach((node) => {{
      if (!(node instanceof Element)) return;
      node.remove();
      node.parentElement = this;
      this.children.push(node);
    }});
  }}
  before(node) {{
    const parent = this.parentElement;
    if (!parent) return;
    node.remove();
    const index = parent.children.indexOf(this);
    node.parentElement = parent;
    parent.children.splice(index, 0, node);
  }}
  after(node) {{
    const parent = this.parentElement;
    if (!parent) return;
    node.remove();
    const index = parent.children.indexOf(this);
    node.parentElement = parent;
    parent.children.splice(index + 1, 0, node);
  }}
  remove() {{
    if (!this.parentElement) return;
    this.parentElement.children = this.parentElement.children.filter(
      (candidate) => candidate !== this,
    );
    this.parentElement = null;
  }}
  get isConnected() {{ return this.parentElement !== null; }}
  get previousSibling() {{
    if (!this.parentElement) return null;
    const index = this.parentElement.children.indexOf(this);
    return index > 0 ? this.parentElement.children[index - 1] : null;
  }}
  getAttribute() {{ return null; }}
  matches(selector) {{
    if (selector.includes(",")) {{
      return selector.split(",").some((part) => this.matches(part.trim()));
    }}
    if (selector.startsWith(".")) {{
      return this.className.split(/\\s+/u).includes(selector.slice(1));
    }}
    if (selector === "[data-generation-intake-synthetic]") {{
      return this.dataset.generationIntakeSynthetic !== undefined;
    }}
    if (selector === "[data-media-card]") return false;
    if (["label", "article", "li"].includes(selector)) {{
      return this.tagName === selector;
    }}
    const input = selector.match(
      /^input\\[name="([^"]+)"\\](?:\\[value="([^"]*)"\\])?$/u,
    );
    return Boolean(
      input
      && this instanceof HTMLInputElement
      && this.name === input[1]
      && (input[2] === undefined || this.value === input[2]),
    );
  }}
  querySelectorAll(selector) {{
    const parts = selector.split(/\\s+/u);
    const leaf = parts.at(-1);
    const ancestor = parts.length > 1 ? parts.slice(0, -1).join(" ") : "";
    const found = [];
    const visit = (node) => {{
      node.children.forEach((child) => {{
        if (child.matches(leaf)) {{
          if (!ancestor || child.closest(ancestor)) found.push(child);
        }}
        visit(child);
      }});
    }};
    visit(this);
    return found;
  }}
  querySelector(selector) {{ return this.querySelectorAll(selector)[0] || null; }}
  closest(selector) {{
    let current = this;
    while (current) {{
      if (current.matches(selector)) return current;
      current = current.parentElement;
    }}
    return null;
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
}}
globalThis.HTMLElement = Element;
globalThis.HTMLInputElement = class extends Element {{
  constructor(name, value) {{
    super("input");
    this.name = name;
    this.value = value;
    this.checked = false;
    this.disabled = false;
  }}
}};
globalThis.Event = class {{ constructor(type) {{ this.type = type; }} }};
globalThis.CSS = {{ escape(value) {{ return String(value); }} }};
globalThis.document = {{
  createComment() {{ return new Element("comment"); }},
}};
const q = (selector, root) => root?.querySelector?.(selector) || null;
const qa = (selector, root) => [...(root?.querySelectorAll?.(selector) || [])];
const cleanText = (value) => String(value || "").trim();
const el = (tagName, className = "", text = "") => {{
  const node = new Element(tagName);
  node.className = className;
  node.textContent = text;
  return node;
}};
const productSelectionOrder = (input) => {{
  const order = Number(input?.dataset?.generationIntakeSelectionOrder);
  return Number.isSafeInteger(order) && order > 0 ? order : null;
}};
const setProductSelectionOrder = (input, order) => {{
  if (Number.isSafeInteger(order) && order > 0) {{
    input.dataset.generationIntakeSelectionOrder = String(order);
  }} else {{
    delete input.dataset.generationIntakeSelectionOrder;
  }}
}};
{move_contract}
{prune_contract}

const mediaId = "70000000-0000-4000-8000-000000000007";
const form = new Element("form");
const nativeHost = new Element("div");
const shell = new Element("section");
const slot = new Element("div");
slot.className = "generation-intake-v4__product-items";
shell.append(slot);
form.append(nativeHost, shell);

const synthetic = new Element("div");
synthetic.className = "option generation-media-option";
synthetic.dataset.generationIntakeSynthetic = "true";
const selectLabel = new Element("label");
const checkbox = new HTMLInputElement("media_id", mediaId);
checkbox.checked = true;
checkbox.dataset.generationIntakeSelectionOrder = "1";
selectLabel.append(checkbox);
const primaryLabel = new Element("label");
primaryLabel.className = "generation-media-option__primary";
const primary = new HTMLInputElement("primary_media_id", mediaId);
primary.checked = true;
primaryLabel.append(primary);
synthetic.append(selectLabel, primaryLabel);
nativeHost.append(synthetic);

const state = {{ shell, productNodes: [] }};
const collectedBefore = collectProductNodes(form);
moveProductNodes(form, state, true);
const pairMovedTogether = slot.children.includes(synthetic)
  && synthetic.querySelector('input[name="media_id"]') === checkbox
  && synthetic.querySelector('input[name="primary_media_id"]') === primary;

const real = new Element("div");
real.className = "option generation-media-option";
const realCheckbox = new HTMLInputElement("media_id", mediaId);
const realPrimary = new HTMLInputElement("primary_media_id", mediaId);
real.append(realCheckbox, realPrimary);
nativeHost.append(real);
pruneSyntheticProductOptions(form);

process.stdout.write(JSON.stringify({{
  collectedExactOption: collectedBefore.length === 1 && collectedBefore[0] === synthetic,
  trackedExactOption: state.productNodes.length === 1
    && state.productNodes[0].node === synthetic,
  pairMovedTogether,
  syntheticRemoved: synthetic.parentElement === null,
  realChecked: realCheckbox.checked,
  transferredOrder: realCheckbox.dataset.generationIntakeSelectionOrder || "",
  realChangeEvents: realCheckbox.events,
  realPrimaryUntouched: realPrimary.checked === false,
  mediaCheckboxCountAfterPrune: form.querySelectorAll('input[name="media_id"]').length,
  primaryRadioCountAfterPrune: form.querySelectorAll('input[name="primary_media_id"]').length,
}}));
"""
    )

    assert payload == {
        "collectedExactOption": True,
        "trackedExactOption": True,
        "pairMovedTogether": True,
        "syntheticRemoved": True,
        "realChecked": True,
        "transferredOrder": "1",
        "realChangeEvents": ["change"],
        # The next exact bind, not prune/DOM order, chooses the handoff primary.
        "realPrimaryUntouched": True,
        "mediaCheckboxCountAfterPrune": 1,
        "primaryRadioCountAfterPrune": 1,
    }


def test_mock_legacy_mode_with_strategy_keeps_explicit_paid_primary() -> None:
    app = APP.read_text(encoding="utf-8")
    media_contract = "function generationUsesPaidMedia" + _between(
        app,
        "function generationUsesPaidMedia",
        "function generationLearningKey",
    )
    payload = _run_node(
        f"""
import {{ resolveGenerationMediaSelection }} from {json.dumps(AUTOPILOT.as_uri())};
const MAX_REAL_GENERATION_REFERENCES = 5;
const isRealGenerationMode = () => false;
const toast = () => {{}};
{media_contract}

const ids = [
  "80000000-0000-4000-8000-000000000008",
  "60000000-0000-4000-8000-000000000006",
  "40000000-0000-4000-8000-000000000004",
  "70000000-0000-4000-8000-000000000007",
];
const media = ids.map((value) => ({{
  value,
  name: "media_id",
  checked: true,
  disabled: false,
  dataset: {{
    mediaIdentityVerified: "true",
    mediaRightsConfirmed: "true",
    mediaProductId: "90000000-0000-4000-8000-000000000009",
    mediaSku: "BOOTS-1",
    mediaProductName: "Black boots",
  }},
}}));
const radios = ids.map((value) => ({{
  value,
  name: "primary_media_id",
  checked: value.endsWith("0007"),
  disabled: false,
  closest(selector) {{
    if (selector === ".generation-media-option") {{
      return {{ dataset: {{ paidReady: "true" }} }};
    }}
    if (selector === ".generation-media-option__primary") {{
      return {{ toggleAttribute() {{}} }};
    }}
    return null;
  }},
}}));
const form = {{
  dataset: {{}},
  elements: {{
    generation_mode: {{ value: "mock", disabled: true }},
    generation_strategy_id: {{ value: "viral_product_swap" }},
  }},
  querySelector(selector) {{
    if (selector === 'input[name="primary_media_id"]:checked') {{
      return radios.find((radio) => radio.checked) || null;
    }}
    return null;
  }},
  querySelectorAll(selector) {{
    if (selector === 'input[name="media_id"]') return media;
    if (selector === 'input[name="primary_media_id"]') return radios;
    return [];
  }},
}};

const before = generationMediaSelectionFromForm(form);
const synced = syncGenerationMediaSelection(form, {{ notify: false }});
process.stdout.write(JSON.stringify({{
  paid: generationUsesPaidMedia(form),
  rebuildUsesGenericPaidMedia: generationUsesPaidMedia({{
    elements: {{
      generation_mode: {{ value: "mock" }},
      generation_strategy_id: {{ value: "viral_rebuild" }},
    }},
  }}),
  mockUsesPaidMedia: generationUsesPaidMedia({{
    elements: {{
      generation_mode: {{ value: "mock" }},
      generation_strategy_id: {{ value: "" }},
    }},
  }}),
  beforePrimary: before.primaryMediaId,
  syncedPrimary: synced.primaryMediaId,
  mediaIds: synced.mediaIds,
  checkedPrimary: radios.find((radio) => radio.checked)?.value || "",
}}));
"""
    )

    assert payload == {
        "paid": True,
        "rebuildUsesGenericPaidMedia": False,
        "mockUsesPaidMedia": False,
        "beforePrimary": "70000000-0000-4000-8000-000000000007",
        "syncedPrimary": "70000000-0000-4000-8000-000000000007",
        "mediaIds": [
            "70000000-0000-4000-8000-000000000007",
            "80000000-0000-4000-8000-000000000008",
            "60000000-0000-4000-8000-000000000006",
            "40000000-0000-4000-8000-000000000004",
        ],
        "checkedPrimary": "70000000-0000-4000-8000-000000000007",
    }


def test_strategy_payload_uses_exact_compact_click_order_after_dom_reorder() -> None:
    app = APP.read_text(encoding="utf-8")
    order_contract = "function generationIntakeProductMediaOrder" + _between(
        app,
        "function generationIntakeProductMediaOrder",
        "function generationStrategySourceProjectionForForm",
    )
    payload = _run_node(
        f"""
const MAX_REAL_GENERATION_REFERENCES = 5;
const contentReviewUuid = (value) => /^[0-9a-f]{{8}}-[0-9a-f]{{4}}-[1-8][0-9a-f]{{3}}-[89ab][0-9a-f]{{3}}-[0-9a-f]{{12}}$/iu.test(String(value));
function generationStrategySourceProjectionForForm() {{
  return {{ required_count: 1 }};
}}
{order_contract}

const ids = {{
  seven: "70000000-0000-4000-8000-000000000007",
  six: "60000000-0000-4000-8000-000000000006",
  four: "40000000-0000-4000-8000-000000000004",
  eight: "80000000-0000-4000-8000-000000000008",
}};
const clickOrder = [ids.seven, ids.six, ids.four, ids.eight];
const domOrder = [ids.eight, ids.six, ids.four, ids.seven];
const source = {{ role: "source_video", media_id: "123f0000-0000-4000-8000-000000000005" }};
const original = {{ role: "original_product_image", media_id: "11000000-0000-4000-8000-000000000001" }};
const entry = Object.freeze({{
  source_media_id: source.media_id,
  selection: Object.freeze({{
    assets: Object.freeze([
      source,
      original,
      ...domOrder.map((media_id) => Object.freeze({{ role: "new_product_image", media_id }})),
    ]),
  }}),
}});
globalThis.ContentEngineGenerationGuidedV4 = {{
  getStrategySelections() {{ return [entry]; }},
}};
const hiddenForm = {{
  elements: {{
    generation_intake_product_media_ids: {{ value: JSON.stringify(clickOrder) }},
  }},
  querySelectorAll() {{ return []; }},
}};
const ordered = generationStrategySelectionsForForm(hiddenForm)[0].selection.assets
  .filter((asset) => asset.role === "new_product_image")
  .map((asset) => asset.media_id);

const rank = new Map(clickOrder.map((id, index) => [id, index + 1]));
const patchedForm = {{
  elements: {{}},
  querySelectorAll(selector) {{
    return selector === 'input[name="media_id"]:checked'
      ? domOrder.map((value) => ({{
          value,
          dataset: {{ generationIntakeSelectionOrder: String(rank.get(value)) }},
        }}))
      : [];
  }},
}};
const afterPatch = generationStrategySelectionsForForm(patchedForm)[0].selection.assets
  .filter((asset) => asset.role === "new_product_image")
  .map((asset) => asset.media_id);

const staleForm = {{
  elements: {{
    generation_intake_product_media_ids: {{ value: JSON.stringify(clickOrder.slice(0, 3)) }},
  }},
  querySelectorAll() {{ return []; }},
}};
const stale = generationStrategySelectionsForForm(staleForm)[0].selection.assets
  .filter((asset) => asset.role === "new_product_image")
  .map((asset) => asset.media_id);

process.stdout.write(JSON.stringify({{ ordered, afterPatch, stale }}));
"""
    )

    click_order = [
        "70000000-0000-4000-8000-000000000007",
        "60000000-0000-4000-8000-000000000006",
        "40000000-0000-4000-8000-000000000004",
        "80000000-0000-4000-8000-000000000008",
    ]
    assert payload["ordered"] == click_order
    assert payload["afterPatch"] == click_order
    # A partial/malformed handoff cannot drop or reorder live native assets.
    assert payload["stale"] == [
        "80000000-0000-4000-8000-000000000008",
        "60000000-0000-4000-8000-000000000006",
        "40000000-0000-4000-8000-000000000004",
        "70000000-0000-4000-8000-000000000007",
    ]


def test_async_native_handoff_reacquires_live_state_panel_and_price_target() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    context_contract = "function liveCopyLaunchContext" + _between(
        intake,
        "function liveCopyLaunchContext",
        "function preflightSignature",
    )
    price_contract = "function setExpressPricePhase" + _between(
        intake,
        "function setExpressPricePhase",
        "function resetExpressPrice",
    )
    payload = _run_node(
        f"""
const oldForm = {{ id: "old" }};
const liveForm = {{ id: "live" }};
const oldPanel = {{ id: "old-panel" }};
const livePanel = {{ id: "live-panel" }};
const oldState = {{ busy: true, panel: oldPanel, express: {{ phase: "idle" }} }};
const liveState = {{ busy: false, panel: livePanel, express: {{ phase: "idle" }} }};
const formStates = new WeakMap([
  [oldForm, oldState],
  [liveForm, liveState],
]);
let currentForm = oldForm;
const liveGenerationForm = () => currentForm;
const mount = (form) => {{
  if (!formStates.has(form)) formStates.set(form, {{ busy: false, panel: livePanel }});
}};
const panelFor = (state) => state.panel;
const adoptRouteBusy = (state) => {{ state.busy = true; }};
const syncExpressPriceButton = (state) => {{ state.synced = true; }};
{_express_helpers(intake)}
{context_contract}
{price_contract}

const before = liveCopyLaunchContext(oldForm, oldState, oldPanel, {{ busy: true }});
currentForm = liveForm;
const adopted = liveCopyLaunchContext(oldForm, oldState, oldPanel, {{ busy: true }});
setExpressPricePhase(adopted.state, "$0.50", "signed-token");
process.stdout.write(JSON.stringify({{
  beforeForm: before.form.id,
  adoptedForm: adopted.form.id,
  adoptedPanel: adopted.panel.id,
  oldPrice: oldState.express.price || "",
  livePrice: liveState.express.price,
  liveToken: liveState.express.spend_confirmation,
  liveBusy: liveState.busy,
  liveButtonSynced: liveState.synced === true,
}}));
"""
    )
    assert payload == {
        "beforeForm": "old",
        "adoptedForm": "live",
        "adoptedPanel": "live-panel",
        "oldPrice": "",
        "livePrice": "$0.50",
        "liveToken": "signed-token",
        "liveBusy": True,
        "liveButtonSynced": True,
    }

    launch = "async function openNativeLaunch" + _between(
        intake,
        "async function openNativeLaunch",
        "function frameAsFile",
    )
    assert "liveGenerationForm(form)" in launch
    assert "let state = activate(form, { persist: true });" in launch
    assert "missing = handoff.assets.filter" in launch
    assert "bindHandoffPrimaryProduct(form, handoff)" in launch
    assert "missingRoles: missing.map" in launch
    assert "panel: context.panel" in launch
    assert launch.index("bindHandoffPrimaryProduct(form, handoff)") > launch.index(
        "await refreshAssets(form)"
    )

    prepare = "async function prepareCopy" + _between(
        intake,
        "async function prepareCopy",
        "async function prepareAvatar",
    )
    assert "const launch = await openNativeLaunch(activeForm, handoff);" in prepare
    assert "activeState = launch.state;" in prepare
    assert "activePanel = launch.panel;" in prepare
    assert "const price = await driveStrategyPreflight(activeForm, activePanel);" in prepare
    assert "setExpressPricePhase(" in prepare
    assert "campaignId," in prepare
    assert "finishRouteBusy(finalContext.state);" in prepare

    app = APP.read_text(encoding="utf-8")
    assert app.count("const real = generationUsesPaidMedia(form);") == 3
    assert "generationIntakeSelectionOrder" in app


def test_final_handoff_replacement_rebinds_returned_live_form() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    launch_contract = "async function openNativeLaunch" + _between(
        intake,
        "async function openNativeLaunch",
        "function frameAsFile",
    )
    payload = _run_node(
        f"""
const formA = {{ id: "A", dataset: {{}} }};
const formB = {{ id: "B", dataset: {{}} }};
const records = {{
  bound: {{ A: [], B: [] }},
  duration: [],
  primary: [],
  persisted: [],
  refreshed: [],
}};
const formStates = new WeakMap();
const mount = (form) => formStates.set(form, {{
  phase: "edit",
  busy: false,
  panel: {{ id: `${{form.id}}-panel` }},
}});
const copyViewActive = () => true;
const ensureContractFields = () => {{}};
const moveProductNodes = () => {{}};
const moveSharedBrief = () => {{}};
const adoptRouteBusy = (state) => {{ state.busy = true; }};
const captureBriefDraft = () => {{}};
const restoreBriefDraft = () => {{}};
{_express_helpers(intake)}
const persistHandoff = (form) => records.persisted.push(form.id);
const selectStrategy = () => {{}};
const applyCompactPreferences = () => {{}};
const ensureSourceOption = () => true;
const ensureOriginalProductOption = () => true;
const bindHandoffAsset = (form, _handoff, asset) => {{
  records.bound[form.id].push(asset.role);
  return true;
}};
const applyHandoffSourceDuration = (form) => {{ records.duration.push(form.id); return true; }};
const refreshProductSelectionCount = () => {{}};
const bindHandoffPrimaryProduct = (form) => {{ records.primary.push(form.id); return true; }};
const q = () => null;
let currentForm = formA;
let switched = false;
const liveGenerationForm = () => currentForm;
const waitMs = async (milliseconds) => {{
  if (milliseconds === 0 && !switched) {{
    switched = true;
    currentForm = formB;
  }}
}};
const liveCopyLaunchContext = (form, state) => ({{
  form: currentForm,
  state: formStates.get(currentForm) || state,
  panel: formStates.get(currentForm)?.panel || null,
}});
globalThis.window = {{
  ContentEngineGenerationGuidedV4: {{
    async refreshStrategyAssets(form) {{ records.refreshed.push(form.id); }},
    materializeRegisteredSource() {{ return true; }},
    getStrategySourcePickerProjection() {{
      return {{
        selected_count: 1,
        selected: [{{
          source_media_id: "123f0000-0000-4000-8000-000000000005",
        }}],
      }};
    }},
  }},
}};
{launch_contract}

const handoff = {{
  route: "copy_video",
  strategy_id: "viral_product_swap",
  product_media_ids: ["70000000-0000-4000-8000-000000000007"],
  assets: [
    {{ role: "source_video", media_id: "123f0000-0000-4000-8000-000000000005", duration_seconds: 5 }},
    {{ role: "original_product_image", media_id: "11000000-0000-4000-8000-000000000001" }},
    {{ role: "new_product_image", media_id: "70000000-0000-4000-8000-000000000007" }},
  ],
}};
const result = await openNativeLaunch(formA, handoff);
process.stdout.write(JSON.stringify({{
  returnedForm: result.form.id,
  returnedPanel: result.panel.id,
  returnedBusy: result.state.busy,
  missingRoles: result.missingRoles,
  boundA: records.bound.A,
  boundB: records.bound.B,
  duration: records.duration,
  primary: records.primary,
  persisted: records.persisted,
  refreshed: records.refreshed,
}}));
"""
    )
    assert payload == {
        "returnedForm": "B",
        "returnedPanel": "B-panel",
        "returnedBusy": True,
        "missingRoles": [],
        "boundA": [
            "source_video",
            "original_product_image",
            "new_product_image",
        ],
        "boundB": [
            "source_video",
            "original_product_image",
            "new_product_image",
        ],
        "duration": ["A", "B"],
        "primary": ["A", "B"],
        "persisted": ["A", "B"],
        "refreshed": ["A", "B"],
    }


def test_paid_click_reacquires_live_form_and_rejects_stale_price_token_pair() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    context_contract = "function liveCopyLaunchContext" + _between(
        intake,
        "function liveCopyLaunchContext",
        "function preflightSignature",
    )
    launch_contract = "async function startExpressLaunch" + _between(
        intake,
        "async function startExpressLaunch",
        "async function prepareCopy",
    )
    payload = _run_node(
        f"""
globalThis.HTMLInputElement = class {{}};
globalThis.HTMLButtonElement = class {{}};
globalThis.HTMLSelectElement = class {{}};
const status = [];
const formStates = new WeakMap();
let currentForm = null;
const liveGenerationForm = () => currentForm;
const mount = () => {{}};
const panelFor = (state) => state.panel;
const prepareCopy = () => {{ throw new Error("unexpected_prepare"); }};
const autoSelectCampaign = () => "90000000-0000-4000-8000-000000000009";
const expressCampaignMatchesPrice = (form, express, campaignId) => (
  form.elements.campaign_id instanceof HTMLSelectElement
  && form.elements.campaign_id.disabled !== true
  && form.elements.campaign_id.value === campaignId
  && express.campaign_id === campaignId
);
const serverPriceLabel = (form) => form.price;
const waitMs = () => Promise.resolve();
const cleanText = (value) => String(value || "");
const q = (selector, form) => selector === "#generation-submit" ? form.submit : null;
const setStatus = (panel, text, state) => status.push({{ panel: panel?.id || "", text, state }});
const setExpressPricePhase = (state, price, token) => {{
  state.express = {{ phase: price ? "priced" : "idle", price, spend_confirmation: token }};
}};
const adoptRouteBusy = (state) => {{ state.busy = true; }};
const beginRouteBusy = (state) => {{ state.busy = true; return true; }};
const finishRouteBusy = (state) => {{ if (state) state.busy = false; }};
const reportRouteBusy = () => false;
const prepareAvatar = () => {{ throw new Error("unexpected_prepare_avatar"); }};
{_express_helpers(intake)}
{context_contract}
{launch_contract}

function makeInput(value, onClick = null) {{
  const input = new HTMLInputElement();
  input.value = value;
  input.checked = false;
  input.disabled = false;
  input.click = () => {{ input.checked = true; onClick?.(); }};
  return input;
}}
function makeButton(form) {{
  const button = new HTMLButtonElement();
  button.disabled = false;
  button.dataset = {{}};
  button.clicks = 0;
  button.click = () => {{ button.clicks += 1; form.dataset.busy = "true"; }};
  return button;
}}
function makeCampaign() {{
  const campaign = new HTMLSelectElement();
  campaign.value = "90000000-0000-4000-8000-000000000009";
  campaign.disabled = false;
  return campaign;
}}

const oldForm = {{
  dataset: {{ generationStrategyConfirmationReady: "true" }},
  elements: {{}},
  price: "$0.50",
}};
const liveForm = {{
  dataset: {{ generationStrategyConfirmationReady: "true" }},
  elements: {{}},
  price: "$0.50",
}};
oldForm.elements.real_spend_confirmation = makeInput("signed-token", () => {{
  liveForm.elements.real_spend_confirmation.checked = true;
  currentForm = liveForm;
}});
liveForm.elements.real_spend_confirmation = makeInput("signed-token");
oldForm.elements.campaign_id = makeCampaign();
liveForm.elements.campaign_id = makeCampaign();
oldForm.submit = makeButton(oldForm);
liveForm.submit = makeButton(liveForm);
const oldState = {{
  busy: false,
  panel: {{ id: "old-panel" }},
  express: {{
    phase: "priced",
    price: "$0.50",
    spend_confirmation: "signed-token",
    campaign_id: "90000000-0000-4000-8000-000000000009",
  }},
}};
const liveState = {{
  busy: false,
  panel: {{ id: "live-panel" }},
  express: {{ phase: "idle", price: "", spend_confirmation: "" }},
}};
formStates.set(oldForm, oldState);
formStates.set(liveForm, liveState);
currentForm = oldForm;
await startExpressLaunch(oldForm);

const staleForm = {{
  dataset: {{ generationStrategyConfirmationReady: "true" }},
  elements: {{}},
  price: "$0.60",
}};
staleForm.elements.real_spend_confirmation = makeInput("different-token");
staleForm.elements.campaign_id = makeCampaign();
staleForm.submit = makeButton(staleForm);
const staleState = {{
  busy: false,
  panel: {{ id: "stale-panel" }},
  express: {{
    phase: "priced",
    price: "$0.50",
    spend_confirmation: "signed-token",
    campaign_id: "90000000-0000-4000-8000-000000000009",
  }},
}};
formStates.set(staleForm, staleState);
currentForm = staleForm;
await startExpressLaunch(staleForm);

process.stdout.write(JSON.stringify({{
  oldSubmitClicks: oldForm.submit.clicks,
  liveSubmitClicks: liveForm.submit.clicks,
  liveNativeBusy: liveForm.dataset.busy,
  oldCompactBusy: oldState.busy,
  liveCompactBusy: liveState.busy,
  staleSubmitClicks: staleForm.submit.clicks,
  staleConfirmationChecked: staleForm.elements.real_spend_confirmation.checked,
  stalePhase: staleState.express.phase,
  statusPanels: status.map((entry) => entry.panel),
}}));
"""
    )
    assert payload == {
        "oldSubmitClicks": 0,
        "liveSubmitClicks": 1,
        "liveNativeBusy": "true",
        "oldCompactBusy": False,
        "liveCompactBusy": False,
        "staleSubmitClicks": 0,
        "staleConfirmationChecked": False,
        "stalePhase": "idle",
        "statusPanels": ["live-panel", "stale-panel"],
    }


def test_fresh_local_mp4_probe_replaces_catalog_default_before_price() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    preflight_contract = "async function driveStrategyPreflight" + _between(
        intake,
        "async function driveStrategyPreflight",
        "function priceButtonFor",
    )
    payload = _run_node(
        f"""
globalThis.HTMLButtonElement = class {{}};
const EXPRESS_PREFLIGHT_TIMEOUT_MS = 10000;
const EXPRESS_POLL_INTERVAL_MS = 1;
const EXPRESS_BLOCKED_POLL_LIMIT = 3;
const EXPRESS_ATTESTATION_RENDER_POLL_LIMIT = 3;
const EXPRESS_STALLED_POLL_LIMIT = 3;
const EXPRESS_FREE_SUBMIT_PHASES = ["strategy_product_swap_prepare"];
const COPY_AUTHORITY_STRATEGY = "viral_product_swap";
const panel = {{ id: "live-panel" }};
let serverDuration = null;
let activeForm = null;
let waitCount = 0;
const statuses = [];
const liveCopyLaunchContext = () => ({{
  form: activeForm,
  state: {{ busy: true }},
  panel,
}});
const verifiedSourceDurationSeconds = () => serverDuration;
const wizardDurationControl = (form) => form.duration;
const wizardDurationWindow = () => ({{ min: 4, max: 15 }});
const applyCopyDuration = (form, seconds) => {{
  form.duration.value = String(seconds);
  form.durationChanges.push(seconds);
  if (form.replacement) activeForm = form.replacement;
  return true;
}};
const setStatus = (_panel, text, state) => statuses.push({{ text, state }});
const waitMs = async () => {{
  waitCount += 1;
  if (activeForm.duration.value === "5") {{
    delete activeForm.dataset.busy;
    activeForm.dataset.generationStrategyConfirmationReady = "true";
  }}
}};
const serverPriceLabel = () => "$0.25";
const preflightSignature = () => `signature-${{waitCount}}`;
const applyConsolidatedRights = () => [];
const selectStrategy = () => {{}};
const approvePendingSpecVersions = () => {{}};
const applyAutoOutputDefaults = () => {{}};
const cleanText = (value) => String(value || "");
const q = (selector, form) => selector === "#generation-submit"
  ? form.submit
  : selector === '[data-action="probe-generation-strategy-media"]'
  ? form.probe
  : null;
{preflight_contract}

function button() {{
  const value = new HTMLButtonElement();
  value.hidden = false;
  value.disabled = false;
  value.dataset = {{ launchPhase: "strategy_product_swap_prepare", launchBlocker: "" }};
  value.textContent = "Бесплатно проверить MP4";
  value.clicks = 0;
  return value;
}}

const fresh = {{
  dataset: {{ generationStrategyConfirmationReady: "false" }},
  duration: {{ value: "10", disabled: false }},
  durationChanges: [],
  submit: button(),
  probe: button(),
}};
fresh.probe.click = () => {{
  fresh.probe.clicks += 1;
  fresh.probe.hidden = true;
  serverDuration = 5;
}};
fresh.submit.click = () => {{ fresh.submit.clicks += 1; }};
activeForm = fresh;
const freshPrice = await driveStrategyPreflight(fresh, panel);

serverDuration = 5;
waitCount = 0;
const existing = {{
  dataset: {{ generationStrategyConfirmationReady: "true" }},
  duration: {{ value: "10", disabled: false }},
  durationChanges: [],
  submit: button(),
  probe: button(),
}};
existing.probe.hidden = true;
activeForm = existing;
const existingPrice = await driveStrategyPreflight(existing, panel);

// Live .4 regression: applying 5 to A dispatches input/change, app.js replaces
// it with B, and B is temporarily disabled by native setFormBusy. Exact 5 on B
// is already accepted state and must not become source_duration_unavailable.
serverDuration = 5;
waitCount = 0;
const replacement = {{
  dataset: {{ generationStrategyConfirmationReady: "true", busy: "true" }},
  duration: {{ value: "5", disabled: true }},
  durationChanges: [],
  submit: button(),
  probe: button(),
}};
replacement.probe.hidden = true;
const detached = {{
  dataset: {{ generationStrategyConfirmationReady: "false" }},
  duration: {{ value: "10", disabled: false }},
  durationChanges: [],
  submit: button(),
  probe: button(),
  replacement,
}};
detached.probe.hidden = true;
activeForm = detached;
const replacedPrice = await driveStrategyPreflight(detached, panel);

serverDuration = null;
const stale = {{
  dataset: {{ generationStrategyConfirmationReady: "true" }},
  duration: {{ value: "10", disabled: false }},
  durationChanges: [],
  submit: button(),
  probe: button(),
}};
activeForm = stale;
let staleError = "";
try {{
  await driveStrategyPreflight(stale, panel);
}} catch (error) {{
  staleError = error.message;
}}

process.stdout.write(JSON.stringify({{
  freshPrice,
  freshProbeClicks: fresh.probe.clicks,
  freshDuration: fresh.duration.value,
  freshDurationChanges: fresh.durationChanges,
  freshSubmitClicks: fresh.submit.clicks,
  existingPrice,
  existingDuration: existing.duration.value,
  existingDurationChanges: existing.durationChanges,
  replacedPrice,
  detachedDuration: detached.duration.value,
  returnedDuration: replacement.duration.value,
  returnedDurationDisabled: replacement.duration.disabled,
  staleError,
  durationStatusSeen: statuses.some((entry) => entry.text.includes("5 с")),
}}));
"""
    )
    assert payload == {
        "freshPrice": "$0.25",
        "freshProbeClicks": 1,
        "freshDuration": "5",
        "freshDurationChanges": [5],
        "freshSubmitClicks": 0,
        "existingPrice": "$0.25",
        "existingDuration": "5",
        "existingDurationChanges": [5],
        "replacedPrice": "$0.25",
        "detachedDuration": "5",
        "returnedDuration": "5",
        "returnedDurationDisabled": True,
        "staleError": "express_source_duration_unverified",
        "durationStatusSeen": True,
    }


def test_product_swap_media_gate_reads_moved_form_wide_product_nodes_only() -> None:
    guided = GUIDED.read_text(encoding="utf-8")
    media_contract = "function mediaSelectionValid" + _between(
        guided,
        "function mediaSelectionValid",
        "function requiredTextControl",
    )
    validity_contract = "function panelValidity" + _between(
        guided,
        "function panelValidity",
        "function firstInvalidStepBefore",
    )
    clear_contract = "function clearPanelError" + _between(
        guided,
        "function clearPanelError",
        "function showPanelError",
    )
    completion_contract = "function syncCompletion" + _between(
        guided,
        "function syncCompletion",
        "function scheduleSync",
    )
    payload = _run_node(
        f"""
const runtime = {{ strategyState: {{ selected_strategy_id: "viral_product_swap" }} }};
const STEPS = [{{ key: "media" }}, {{ key: "launch" }}];
const errorNode = {{ hidden: false, textContent: "" }};
const panel = {{
  querySelectorAll() {{ return []; }},
}};
const movedProduct = {{
  checked: true,
  disabled: false,
  dataset: {{ wasDisabled: "false" }},
}};
const form = {{
  dataset: {{}},
  elements: {{}},
  panel,
  strategySelection: {{ strategy_id: "viral_product_swap" }},
  querySelectorAll(selector) {{
    return selector === 'input[name="media_id"]' ? [movedProduct] : [];
  }},
}};
const buttons = Object.fromEntries(STEPS.map((step) => [step.key, {{
  classList: {{ toggle() {{}}, remove() {{}} }},
}}]));
const qa = (selector, root) => [...(root?.querySelectorAll?.(selector) || [])];
const q = (selector, root = null) => {{
  if (root === panel && selector === "[data-ce-v4-generation-error]") return errorNode;
  if (selector === "#generation-strategy-assets") return {{ id: "strategy-assets" }};
  if (selector === "#generation-submit") return {{ disabled: false }};
  const target = selector.match(/^\\[data-ce-v4-generation-target="(.+)"\\]$/u);
  return target ? buttons[target[1]] || null : null;
}};
const panelFor = (_form, key) => key === "media" ? panel : null;
const requiredTextControl = () => null;
const firstInvalidControl = () => null;
const modeIsReal = () => false;
const controlLabel = () => "field";
const generationStrategySelection = (candidate) => candidate.strategySelection;
const stepIndex = () => 0;
{media_contract}
{clear_contract}
{validity_contract}
{completion_contract}

const validSwap = panelValidity(form, 0);

form.strategySelection = null;
const incompleteSwap = panelValidity(form, 0);

runtime.strategyState.selected_strategy_id = "viral_rebuild";
form.strategySelection = {{ strategy_id: "viral_rebuild" }};
const rebuild = panelValidity(form, 0);

runtime.strategyState.selected_strategy_id = null;
form.strategySelection = null;
const legacy = panelValidity(form, 0);

runtime.strategyState.selected_strategy_id = "viral_product_swap";
form.strategySelection = {{ strategy_id: "viral_product_swap" }};
form.dataset.busy = "true";
movedProduct.disabled = true;
const busySwap = panelValidity(form, 0);

// A generic error rendered during the former panel-only race is historical
// once exact Product Swap becomes valid, so syncCompletion must remove it.
errorNode.hidden = false;
errorNode.textContent = "old generic media error";
syncCompletion(form);
const staleCleared = errorNode.hidden && errorNode.textContent === "";

// An authoritative strategy error is current truth and must remain visible.
form.strategySelection = null;
errorNode.hidden = false;
errorNode.textContent = "strategy-specific missing roles";
syncCompletion(form);
const specificRetained = !errorNode.hidden
  && errorNode.textContent === "strategy-specific missing roles";

process.stdout.write(JSON.stringify({{
  validSwap: validSwap.valid,
  incompleteSwap: {{ valid: incompleteSwap.valid, message: incompleteSwap.message }},
  rebuild: {{ valid: rebuild.valid, message: rebuild.message }},
  legacy: {{ valid: legacy.valid, message: legacy.message }},
  busySwap: busySwap.valid,
  staleCleared,
  specificRetained,
}}));
"""
    )
    generic = (
        "Выберите хотя бы один точный исходник товара. Без него нельзя создать "
        "ни dry-run задачу, ни платный результат."
    )
    assert payload == {
        "validSwap": True,
        "incompleteSwap": {
            "valid": False,
            "message": (
                "Для выбранной стратегии укажите все обязательные исходники, "
                "параметры результата и подтверждения прав."
            ),
        },
        "rebuild": {"valid": False, "message": generic},
        "legacy": {"valid": False, "message": generic},
        "busySwap": True,
        "staleCleared": True,
        "specificRetained": True,
    }


def test_rights_engine_and_campaign_commit_on_input_before_form_replacement() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    capture_contract = "function captureExpressCommittedInput" + _between(
        intake,
        "function captureExpressCommittedInput",
        "function applyExpressDefaults",
    )
    apply_contract = "function applyExpressDefaults" + _between(
        intake,
        "function applyExpressDefaults",
        "function persistHandoff",
    )
    # Программная запись платного контекста идёт через общий помощник: он молчит
    # при восстановлении того же значения и шлёт input/change при настоящей
    # смене. Без него подтверждение траты осталось бы от прежней конфигурации.
    assign_contract = "function assignPaidContextValue" + _between(
        intake,
        "function assignPaidContextValue",
        "// Длительность живёт там же",
    )
    payload = _run_node(
        f"""
globalThis.HTMLInputElement = class {{}};
globalThis.HTMLSelectElement = class {{}};
{assign_contract}
const expressDefaultsMemory = new Map();
const projectId = () => "project-1";
const panelFor = (state) => state.panel;
const identityInput = () => null;
const syncIdentityToForm = () => {{}};
const q = (selector, panel) => {{
  if (selector === '[data-generation-intake-rights="copy_video"]') return panel.rights;
  if (selector === '[data-generation-intake-field="audio"]') return panel.audio;
  return null;
}};
{capture_contract}
{apply_contract}

function input(value = "") {{
  const control = new HTMLInputElement();
  control.value = value;
  control.checked = false;
  control.disabled = false;
  control.closest = () => null;
  control.events = [];
  control.dispatchEvent = (event) => {{ control.events.push(event.type); return true; }};
  return control;
}}
function select(value = "", options = []) {{
  const control = new HTMLSelectElement();
  control.value = value;
  control.options = options;
  control.disabled = false;
  control.closest = () => null;
  control.events = [];
  control.dispatchEvent = (event) => {{ control.events.push(event.type); return true; }};
  return control;
}}

const oldRights = input();
oldRights.checked = true;
oldRights.closest = (selector) => selector.includes("generation-intake-rights")
  ? oldRights
  : null;
const oldState = {{
  panel: {{ rights: oldRights, audio: select("false") }},
  copyEngine: {{ modelId: "fal-ai:pika-v2.2", qualityCode: "standard" }},
}};
const oldCampaign = select("90000000-0000-4000-8000-000000000009");
const oldForm = {{ elements: {{ campaign_id: oldCampaign }} }};
const runway = input("runway:gen4_aleph");
runway.checked = true;
runway.closest = (selector) => selector.includes('choice-block="model"')
  ? runway
  : null;

const rightsCaptured = captureExpressCommittedInput(oldForm, oldState, oldRights);
const engineCaptured = captureExpressCommittedInput(oldForm, oldState, runway);
const campaignCaptured = captureExpressCommittedInput(oldForm, oldState, oldCampaign);

const newRights = input();
const engineField = input();
const campaignOption = {{
  value: "90000000-0000-4000-8000-000000000009",
  disabled: false,
}};
const newCampaign = select("", [campaignOption]);
const newState = {{
  panel: {{ rights: newRights, audio: select("false") }},
  copyEngine: {{ modelId: "fal-ai:pika-v2.2", qualityCode: "" }},
}};
const newForm = {{
  elements: {{
    generation_intake_engine: engineField,
    campaign_id: newCampaign,
  }},
}};
applyExpressDefaults(newForm, newState);

oldRights.checked = false;
captureExpressCommittedInput(oldForm, oldState, oldRights);
const uncheckedRights = input();
applyExpressDefaults({{ elements: {{}} }}, {{
  panel: {{ rights: uncheckedRights, audio: select("false") }},
  copyEngine: {{}},
}});

// Повторное восстановление того же выбора изменением не является и событий
// давать не должно: панель слушает собственные мутации, и безусловная запись
// увела бы наблюдатель в цикл, а цену сбрасывала бы на ровном месте.
const engineEventsAfterChange = engineField.events.join(",");
const campaignEventsAfterChange = newCampaign.events.join(",");
engineField.events = [];
newCampaign.events = [];
applyExpressDefaults(newForm, newState);

process.stdout.write(JSON.stringify({{
  rightsCaptured,
  engineCaptured,
  campaignCaptured,
  restoredRights: newRights.checked,
  restoredEngineState: newState.copyEngine.modelId,
  restoredEngineField: engineField.value,
  restoredCampaign: newCampaign.value,
  uncheckedStayedFalse: uncheckedRights.checked === false,
  engineEventsAfterChange,
  campaignEventsAfterChange,
  engineSilentOnRestore: engineField.events.length === 0,
  campaignSilentOnRestore: newCampaign.events.length === 0,
}}));
"""
    )
    assert payload == {
        "rightsCaptured": True,
        "engineCaptured": True,
        "campaignCaptured": True,
        "restoredRights": True,
        "restoredEngineState": "runway:gen4_aleph",
        "restoredEngineField": "runway:gen4_aleph",
        "restoredCampaign": "90000000-0000-4000-8000-000000000009",
        "uncheckedStayedFalse": True,
        # Настоящая смена платного контекста обязана дойти до пути инвалидации
        # в app.js — он слушает именно input/change по имени поля.
        "engineEventsAfterChange": "input,change",
        "campaignEventsAfterChange": "input,change",
        # А восстановление того же значения — молчит.
        "engineSilentOnRestore": True,
        "campaignSilentOnRestore": True,
    }

    input_handler = _between(
        intake,
        'state.shell.addEventListener("input", (event) => {',
        'form.addEventListener("input", (event) => {',
    )
    assert input_handler.index(
        "captureExpressCommittedInput(form, state, event.target);"
    ) < input_handler.index(
        "const productCheckbox = event.target.closest?.('input[name=\"media_id\"]');"
    )


def test_paid_phase_is_invalidated_before_engine_context_can_rerender() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    status_contract = "function setStatus" + _between(
        intake,
        "function setStatus",
        "function routeButton",
    )
    confirmation_contract = "function clearSpendConfirmation" + _between(
        intake,
        "function clearSpendConfirmation",
        "function applyCompactPreferences",
    )
    invalidation_contract = "function priceButtonFor" + _between(
        intake,
        "function priceButtonFor",
        "function rememberExpressDefaults",
    )
    capture_contract = "function captureExpressCommittedInput" + _between(
        intake,
        "function captureExpressCommittedInput",
        "function applyExpressDefaults",
    )
    payload = _run_node(
        f"""
globalThis.HTMLButtonElement = class {{
  constructor() {{
    this.dataset = {{}};
    this.textContent = "";
  }}
}};
globalThis.Event = class {{
  constructor(type) {{ this.type = type; }}
}};
globalThis.HTMLInputElement = class {{
  constructor(value = "") {{
    this.value = value;
    this.checked = true;
    this.events = [];
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
}};
const q = (selector, panel) => {{
  if (selector.includes("generation-intake-prepare-copy")) return panel.button;
  if (selector === "[data-generation-intake-status]") return panel.status;
  return null;
}};
// Кнопка цены синхронизируется у обеих экспресс-панелей; у стенда есть только
// панель «Копии», панель «Дуэта» отсутствует — как в форме без этого маршрута.
const panelFor = (state, route = "copy_video") => (
  route === "copy_video" ? state.panel : null
);
const setNodeText = (node, text) => {{ node.textContent = text; }};
const expressDefaultsMemory = new Map();
const projectId = () => "project-1";
{status_contract}
{confirmation_contract}
{_express_helpers(intake)}
{invalidation_contract}
{capture_contract}

function target(name, value, insidePanel = false) {{
  return {{
    name,
    value,
    checked: true,
    insidePanel,
    matches(selector) {{ return selector === "input, select, textarea"; }},
  }};
}}

function pricedState() {{
  const button = new HTMLButtonElement();
  const panel = {{
    button,
    dataset: {{}},
    status: {{ dataset: {{}}, textContent: "" }},
    contains(control) {{ return control.insidePanel === true; }},
  }};
  const state = {{
    panel,
    express: {{
      phase: "priced",
      price: "$2.48",
      spend_confirmation: "runway-price-token",
    }},
  }};
  syncExpressPriceButton(state);
  setStatus(
    panel,
    "Точная цена: $2.48. Деньги не списаны.",
    "success",
    {{ expressPriceResult: "priced" }},
  );
  return state;
}}
function pricedForm() {{
  return {{
    elements: {{
      real_spend_confirmation: new HTMLInputElement("runway-price-token"),
    }},
  }};
}}

const pika = new HTMLInputElement("fal-ai:pika-v2.2");
pika.name = "generation_intake_generator";
pika.insidePanel = false;
pika.matches = (selector) => selector === "input, select, textarea";
pika.closest = (selector) => selector.includes('choice-block="model"')
  ? pika
  : null;
const pikaState = pricedState();
pikaState.copyEngine = {{ modelId: "runway:gen4_aleph", qualityCode: "hd" }};
const pikaForm = pricedForm();
const before = {{ value: pika.value, checked: pika.checked }};
expressDefaultsMemory.set("project-1", {{
  engine: "runway:gen4_aleph",
  quality: "hd",
}});
const pikaCaptured = captureExpressCommittedInput(pikaForm, pikaState, pika);
const pikaInvalidated = invalidateExpressPriceForCommittedInput(pikaForm, pikaState, pika);

const contextNames = [
  "generation_intake_quality",
  "generation_intake_duration",
  "campaign_id",
  "media_id",
  "primary_media_id",
  "brief",
  "generation_strategy_material",
];
const contextResults = contextNames.map((name) => {{
  const state = pricedState();
  const form = pricedForm();
  const control = target(name, `${{name}}-value`);
  const invalidated = invalidateExpressPriceForCommittedInput(form, state, control);
  return {{
    name,
    invalidated,
    phase: state.express.phase,
    price: state.express.price,
    token: state.express.spend_confirmation,
    nativeToken: form.elements.real_spend_confirmation.value,
    nativeChecked: form.elements.real_spend_confirmation.checked,
    value: control.value,
  }};
}});

const confirmation = target("real_spend_confirmation", "runway-price-token", true);
const confirmationState = pricedState();
const confirmationForm = pricedForm();
const confirmationInvalidated = invalidateExpressPriceForCommittedInput(
  confirmationForm,
  confirmationState,
  confirmation,
);

const validationErrorState = pricedState();
const validationErrorForm = pricedForm();
setStatus(
  validationErrorState.panel,
  "Длительность исходника не прошла серверную проверку.",
  "error",
);
const validationErrorInvalidated = invalidateExpressPriceForCommittedInput(
  validationErrorForm,
  validationErrorState,
  target("generation_intake_duration", "6"),
);

const campaignWarningState = pricedState();
const campaignWarningForm = pricedForm();
setStatus(
  campaignWarningState.panel,
  "Точная цена: $2.48. Для запуска нужна активная кампания.",
  "warning",
  {{ expressPriceResult: "campaign_missing" }},
);
const campaignWarningInvalidated = invalidateExpressPriceForCommittedInput(
  campaignWarningForm,
  campaignWarningState,
  target("generation_intake_generator", "fal-ai:kling-video-o3-pro"),
);

const campaignResolvedState = pricedState();
const campaignResolvedForm = pricedForm();
campaignResolvedForm.elements.campaign_id = {{
  value: "90000000-0000-4000-8000-000000000009",
}};
setStatus(
  campaignResolvedState.panel,
  "Точная цена: $2.48. Для запуска нужна активная кампания.",
  "warning",
  {{ expressPriceResult: "campaign_missing" }},
);
const campaignResolvedInvalidated = invalidateExpressPriceForCommittedInput(
  campaignResolvedForm,
  campaignResolvedState,
  target("campaign_id", "90000000-0000-4000-8000-000000000009"),
);

process.stdout.write(JSON.stringify({{
  pikaInvalidated,
  pikaCaptured,
  pikaInputPreserved: before.value === pika.value && before.checked === pika.checked,
  rememberedEngine: expressDefaultsMemory.get("project-1")?.engine || "",
  rememberedQuality: expressDefaultsMemory.get("project-1")?.quality ?? "missing",
  liveQuality: pikaState.copyEngine.qualityCode,
  pikaPhase: pikaState.express.phase,
  pikaPrice: pikaState.express.price,
  pikaToken: pikaState.express.spend_confirmation,
  pikaButtonPhase: pikaState.panel.button.dataset.expressPhase,
  pikaButtonText: pikaState.panel.button.textContent,
  pikaNativeToken: pikaForm.elements.real_spend_confirmation.value,
  pikaNativeChecked: pikaForm.elements.real_spend_confirmation.checked,
  pikaNestedConfirmationEvents:
    pikaForm.elements.real_spend_confirmation.events,
  pikaStatusState: pikaState.panel.status.dataset.state,
  pikaStatusText: pikaState.panel.status.textContent,
  pikaStatusMarker: pikaState.panel.status.dataset.expressPriceResult || "",
  contextResults,
  confirmationInvalidated,
  confirmationPhase: confirmationState.express.phase,
  confirmationPrice: confirmationState.express.price,
  confirmationToken: confirmationState.express.spend_confirmation,
  confirmationNativeToken: confirmationForm.elements.real_spend_confirmation.value,
  confirmationNativeChecked: confirmationForm.elements.real_spend_confirmation.checked,
  confirmationStatusText: confirmationState.panel.status.textContent,
  validationErrorInvalidated,
  validationErrorPhase: validationErrorState.express.phase,
  validationErrorState: validationErrorState.panel.status.dataset.state,
  validationErrorText: validationErrorState.panel.status.textContent,
  validationErrorMarker:
    validationErrorState.panel.status.dataset.expressPriceResult || "",
  campaignWarningInvalidated,
  campaignWarningState: campaignWarningState.panel.status.dataset.state,
  campaignWarningText: campaignWarningState.panel.status.textContent,
  campaignWarningMarker:
    campaignWarningState.panel.status.dataset.expressPriceResult || "",
  campaignResolvedInvalidated,
  campaignResolvedState: campaignResolvedState.panel.status.dataset.state,
  campaignResolvedText: campaignResolvedState.panel.status.textContent,
}}));
"""
    )

    assert payload == {
        "pikaInvalidated": True,
        "pikaCaptured": True,
        "pikaInputPreserved": True,
        "rememberedEngine": "fal-ai:pika-v2.2",
        "rememberedQuality": "",
        "liveQuality": "",
        "pikaPhase": "idle",
        "pikaPrice": "",
        "pikaToken": "",
        "pikaButtonPhase": "idle",
        "pikaButtonText": "Подготовить ролик",
        "pikaNativeToken": "",
        "pikaNativeChecked": False,
        "pikaNestedConfirmationEvents": [],
        "pikaStatusState": "neutral",
        "pikaStatusText": (
            "Параметры изменились, поэтому предыдущая цена больше не действует. "
            "Нажмите «Подготовить ролик», чтобы бесплатно получить новую точную "
            "цену."
        ),
        "pikaStatusMarker": "",
        "contextResults": [
            {
                "name": name,
                "invalidated": True,
                "phase": "idle",
                "price": "",
                "token": "",
                "nativeToken": "",
                "nativeChecked": False,
                "value": f"{name}-value",
            }
            for name in [
                "generation_intake_quality",
                "generation_intake_duration",
                "campaign_id",
                "media_id",
                "primary_media_id",
                "brief",
                "generation_strategy_material",
            ]
        ],
        "confirmationInvalidated": False,
        "confirmationPhase": "priced",
        "confirmationPrice": "$2.48",
        "confirmationToken": "runway-price-token",
        "confirmationNativeToken": "runway-price-token",
        "confirmationNativeChecked": True,
        "confirmationStatusText": "Точная цена: $2.48. Деньги не списаны.",
        "validationErrorInvalidated": True,
        "validationErrorPhase": "idle",
        "validationErrorState": "error",
        "validationErrorText": (
            "Длительность исходника не прошла серверную проверку."
        ),
        "validationErrorMarker": "",
        "campaignWarningInvalidated": True,
        "campaignWarningState": "warning",
        "campaignWarningText": (
            "Параметры изменились, поэтому предыдущая цена больше не действует. "
            "Нажмите «Подготовить ролик» для новой бесплатной проверки. Для "
            "запуска по-прежнему нужна активная кампания."
        ),
        "campaignWarningMarker": "",
        "campaignResolvedInvalidated": True,
        "campaignResolvedState": "neutral",
        "campaignResolvedText": (
            "Параметры изменились, поэтому предыдущая цена больше не действует. "
            "Нажмите «Подготовить ролик», чтобы бесплатно получить новую точную "
            "цену."
        ),
    }

    input_handler = _between(
        intake,
        'state.shell.addEventListener("input", (event) => {',
        'form.addEventListener("input", (event) => {',
    )
    assert input_handler.index(
        "captureExpressCommittedInput(form, state, event.target);"
    ) < input_handler.index(
        "invalidateExpressPriceForCommittedInput(form, state, event.target);"
    )
    change_handler = _between(
        intake,
        'state.shell.addEventListener("change", (event) => {',
        'state.shell.addEventListener("input", (event) => {',
    )
    assert change_handler.index(
        "invalidateExpressPriceForCommittedInput(form, state, event.target);"
    ) < change_handler.index(
        "const input = event.target.closest?."
    )
    form_input_handler = _between(
        intake,
        'form.addEventListener("input", (event) => {',
        'form.addEventListener("change", (event) => {',
    )
    assert form_input_handler.index(
        "captureExpressCommittedInput(form, state, event.target);"
    ) < form_input_handler.index(
        "invalidateExpressPriceForCommittedInput(form, state, event.target);"
    )
    form_change_handler = _between(
        intake,
        'form.addEventListener("change", (event) => {',
        "\n  });\n}\n\nfunction mount(form)",
    )
    assert form_change_handler.index(
        "captureExpressCommittedInput(form, state, event.target);"
    ) < form_change_handler.index(
        "invalidateExpressPriceForCommittedInput(form, state, event.target);"
    )
