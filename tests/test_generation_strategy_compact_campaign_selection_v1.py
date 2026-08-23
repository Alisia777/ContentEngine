from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
INTAKE = ROOT / "web" / "app" / "generation-strategy-intake-v4.js"
APP = ROOT / "web" / "app" / "app.js"


def _run_node(source: str) -> dict[str, object]:
    node = shutil.which("node")
    assert node is not None, "Node.js is required for executable UI regressions"
    result = subprocess.run(
        [node, "--input-type=module", "--eval", source],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_compact_campaign_is_visible_before_price_and_exactly_bound_to_cta() -> None:
    source = INTAKE.read_text(encoding="utf-8")
    copy_panel = source.split("function copyPanel()", 1)[1].split(
        "function avatarPanel()", 1
    )[0]
    launch = source.split("async function startExpressLaunch", 1)[1].split(
        "async function prepareCopy", 1
    )[0]

    assert "function compactCampaignChoice()" in source
    assert 'select.dataset.generationIntakeCampaignSelect = ""' in source
    assert 'select.setAttribute("aria-label", "Кампания и её бюджет")' in source
    # Кампания выбирается ДО каскада движка: она задаёт бюджет, в котором цена
    # движка имеет смысл. Карточка каскада переименована в engineCascadeCard —
    # её рисует не только «Копия», но и «Аватар».
    assert copy_panel.index("compactCampaignChoice()") < copy_panel.index(
        "engineCascadeCard()"
    )
    # The mirror must never become a second submitted campaign_id control.
    compact_choice = source.split("function compactCampaignChoice()", 1)[1].split(
        "function recommendationSlot", 1
    )[0]
    assert 'name = "campaign_id"' not in compact_choice
    assert "form?.elements?.campaign_id" in source

    assert "campaign_id:" in source.split(
        "function setExpressPricePhase", 1
    )[1].split("function resetExpressPrice", 1)[0]
    assert launch.count("expressCampaignMatchesPrice(") == 2
    assert "liveCampaignId !== express.campaign_id" in launch
    assert "submitButton.click()" in launch
    assert launch.index("expressCampaignMatchesPrice(") < launch.index(
        "submitButton.click()"
    )

    priced_handoff = source.rsplit(
        "const campaignId = autoSelectCampaign(", 1
    )[1].split("} catch (error)", 1)[0]
    missing_campaign = priced_handoff.split(
        "} else if (!campaignId) {", 1
    )[1].split("} else {", 1)[0]
    bound_campaign = priced_handoff.split("} else {", 1)[1]
    assert 'setExpressPricePhase(activeState, "", "")' in missing_campaign
    assert "clearSpendConfirmation(activeForm, { notify: false })" in missing_campaign
    assert "spendConfirmation" in bound_campaign
    assert "campaignId" in bound_campaign


def test_campaign_selection_survives_render_and_invalid_choice_fails_closed() -> None:
    with tempfile.TemporaryDirectory() as temporary_directory:
        subject = Path(temporary_directory) / "subject.mjs"
        shutil.copyfile(INTAKE, subject)
        payload = _run_node(
            f"""
class HTMLElement {{}}
class HTMLSelectElement extends HTMLElement {{
  constructor(options = [], value = "") {{
    super();
    this.options = options;
    this.value = value;
    this.disabled = false;
    this.dataset = {{}};
    this.events = [];
    this.replaceCount = 0;
  }}
  replaceChildren(...options) {{
    this.replaceCount += 1;
    this.options = options;
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
  matches(selector) {{ return selector === "input, select, textarea"; }}
  closest(selector) {{
    return selector === "[data-generation-intake-campaign-select]"
      && this.dataset.generationIntakeCampaignSelect !== undefined
      ? this
      : null;
  }}
}}
class HTMLInputElement extends HTMLElement {{
  constructor(value = "") {{
    super();
    this.value = value;
    this.checked = false;
    this.disabled = false;
    this.events = [];
  }}
  dispatchEvent(event) {{ this.events.push(event.type); return true; }}
}}
class HTMLButtonElement extends HTMLElement {{
  constructor() {{
    super();
    this.dataset = {{}};
    this.disabled = false;
    this.textContent = "";
    this.title = "";
  }}
}}
class Option {{
  constructor(text, value) {{
    this.text = text;
    this.textContent = text;
    this.value = value;
    this.disabled = false;
  }}
}}
class Event {{
  constructor(type, init = {{}}) {{
    this.type = type;
    this.bubbles = init.bubbles === true;
  }}
}}
globalThis.HTMLElement = HTMLElement;
globalThis.HTMLSelectElement = HTMLSelectElement;
globalThis.HTMLInputElement = HTMLInputElement;
globalThis.HTMLButtonElement = HTMLButtonElement;
globalThis.Option = Option;
globalThis.Event = Event;
globalThis.CSS = {{ escape(value) {{ return String(value); }} }};
globalThis.window = {{
  location: {{ hash: "#/outside" }},
  addEventListener() {{}},
}};
globalThis.document = {{
  documentElement: {{}},
  querySelector() {{ return null; }},
  querySelectorAll() {{ return []; }},
}};
globalThis.MutationObserver = class {{ observe() {{}} }};

const subject = await import({json.dumps(subject.as_uri())});
const main = "11111111-1111-4111-8111-111111111111";
const boots = "22222222-2222-4222-8222-222222222222";
const projects = [
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3",
  "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4",
];
const option = (text, value, disabled = false) =>
  Object.assign(new Option(text, value), {{ disabled }});
const setProject = (id) => {{
  window.location.hash = `#/outside?project_id=${{id}}`;
}};

function makeUi({{
  options,
  value = "",
  engine = "runway:gen4_aleph",
  express = {{
    phase: "idle",
    price: "",
    spend_confirmation: "",
    campaign_id: "",
  }},
}}) {{
  const native = new HTMLSelectElement(options, value);
  const mirror = new HTMLSelectElement();
  mirror.dataset.generationIntakeCampaignSelect = "";
  const hint = {{ textContent: "" }};
  const note = Object.assign(new HTMLElement(), {{ hidden: true }});
  const message = {{ textContent: "" }};
  const button = new HTMLButtonElement();
  const status = {{ dataset: {{}}, textContent: "" }};
  const confirmation = new HTMLInputElement(express.spend_confirmation || "");
  confirmation.checked = Boolean(express.spend_confirmation);
  const nativeSubmit = new HTMLButtonElement();
  nativeSubmit.dataset.launchPhase = "strategy_product_swap_paid_review";
  const panel = {{
    dataset: {{ generationIntakePanel: "copy_video" }},
    contains(node) {{ return node === mirror; }},
    querySelector(selector) {{
      if (selector === "[data-generation-intake-campaign-select]") return mirror;
      if (selector === "[data-generation-intake-campaign-hint]") return hint;
      if (selector === "[data-generation-intake-campaign-note]") return note;
      if (selector === "[data-generation-intake-campaign-note-text]") return message;
      if (selector === '[data-action="generation-intake-prepare-copy"]') return button;
      if (selector === "[data-generation-intake-status]") return status;
      return null;
    }},
  }};
  let form = null;
  const shell = {{
    querySelector(selector) {{
      return selector === '[data-generation-intake-panel="copy_video"]'
        ? panel
        : null;
    }},
    closest(selector) {{ return selector === "form" ? form : null; }},
  }};
  const state = {{
    shell,
    panel,
    copyEngine: {{ modelId: engine, qualityCode: "standard" }},
    express: {{ ...express }},
  }};
  form = {{
    dataset: {{}},
    elements: {{
      campaign_id: native,
      real_spend_confirmation: confirmation,
      generation_intake_engine: {{ value: engine }},
    }},
    querySelector(selector) {{
      return selector === "#generation-submit" ? nativeSubmit : null;
    }},
  }};
  return {{
    form,
    state,
    panel,
    native,
    mirror,
    hint,
    note,
    message,
    button,
    confirmation,
  }};
}}

setProject(projects[0]);
const first = makeUi({{
  options: [option("Main · $25", main), option("Boots · $0.85", boots)],
  value: main,
}});
const firstResolution = subject.syncCompactCampaignControl(first.form, first.state);
const firstOptionNodes = [...first.mirror.options];
subject.syncCompactCampaignControl(first.form, first.state);
const initialSnapshot = {{
  id: firstResolution.id,
  state: first.mirror.dataset.selectionState,
  replacements: first.mirror.replaceCount,
  preservedNodes: first.mirror.options.every(
    (candidate, index) => candidate === firstOptionNodes[index],
  ),
}};
first.mirror.value = boots;
const committed = subject.commitCompactCampaignSelection(
  first.form,
  first.state,
  first.mirror,
);

// Native form re-rendered with its own Main default. Explicit Boots must win.
const rerender = makeUi({{
  options: [option("Main · $25", main), option("Boots · $0.85", boots)],
  value: main,
}});
const restored = subject.syncCompactCampaignControl(
  rerender.form,
  rerender.state,
);

// The explicit Boots campaign disappears. Main exists, but substitution is
// forbidden; price/token/confirmation are invalidated instead.
const invalid = makeUi({{
  options: [option("Main · $25", main)],
  value: main,
  express: {{
    phase: "priced",
    price: "$0.85",
    spend_confirmation: "KLING-BOOTS-ONCE",
    campaign_id: boots,
  }},
}});
invalid.state.panel = invalid.panel;
invalid.state.express = {{
  phase: "priced",
  price: "$0.85",
  spend_confirmation: "KLING-BOOTS-ONCE",
  campaign_id: boots,
}};
invalid.confirmation.value = "KLING-BOOTS-ONCE";
invalid.confirmation.checked = true;
const invalidResolution = subject.syncCompactCampaignControl(
  invalid.form,
  invalid.state,
);
const invalidSnapshot = {{
  id: invalidResolution.id,
  invalidExplicit: invalidResolution.invalidExplicit,
  native: invalid.native.value,
  mirrorState: invalid.mirror.dataset.selectionState,
  phase: invalid.state.express.phase,
  price: invalid.state.express.price,
  token: invalid.state.express.spend_confirmation,
  confirmationValue: invalid.confirmation.value,
  confirmationChecked: invalid.confirmation.checked,
}};

// A new explicit choice recovers the form, but still needs a fresh price.
invalid.mirror.value = main;
const recovered = subject.commitCompactCampaignSelection(
  invalid.form,
  invalid.state,
  invalid.mirror,
);
const exactExpress = {{ campaign_id: main }};
const exactMatch = subject.expressCampaignMatchesPrice(
  invalid.form,
  exactExpress,
  main,
);
const wrongMatch = subject.expressCampaignMatchesPrice(
  invalid.form,
  {{ campaign_id: boots }},
  main,
);

// Repeat may retain the editable campaign choice, but no paid authority.
invalid.state.express = {{
  phase: "priced",
  price: "$0.47",
  spend_confirmation: "PIKA-ONCE",
  campaign_id: main,
}};
invalid.confirmation.value = "PIKA-ONCE";
invalid.confirmation.checked = true;
const repeated = subject.resetExpressAuthorityForStrategyRepeat(
  invalid.form,
  invalid.state,
);

// With no human choice, adopting the native/current default remains safe.
setProject(projects[1]);
const defaultUi = makeUi({{
  options: [option("Main", main), option("Boots", boots)],
  value: main,
}});
const safeDefault = subject.syncCompactCampaignControl(
  defaultUi.form,
  defaultUi.state,
);

// Campaign sync is route-agnostic and must not mutate any engine choice.
const engines = [
  "fal-ai:pika-v2.2",
  "fal-ai:kling-video-o3-pro",
  "runway:gen4_aleph",
];
const engineResults = engines.map((engine, index) => {{
  setProject(projects[index + 1]);
  const ui = makeUi({{
    options: [option("Main", main)],
    value: main,
    engine,
  }});
  subject.syncCompactCampaignControl(ui.form, ui.state);
  return {{
    expected: engine,
    hidden: ui.form.elements.generation_intake_engine.value,
    state: ui.state.copyEngine.modelId,
  }};
}});

process.stdout.write(JSON.stringify({{
  initial: initialSnapshot,
  committed,
  nativeEvents: first.native.events,
  restored: {{
    id: restored.id,
    native: rerender.native.value,
    mirror: rerender.mirror.value,
    state: rerender.mirror.dataset.selectionState,
  }},
  invalid: invalidSnapshot,
  recovered,
  exactMatch,
  wrongMatch,
  repeat: {{
    campaign: repeated.id,
    native: invalid.native.value,
    phase: invalid.state.express.phase,
    price: invalid.state.express.price,
    token: invalid.state.express.spend_confirmation,
    confirmationValue: invalid.confirmation.value,
    confirmationChecked: invalid.confirmation.checked,
  }},
  safeDefault: {{
    id: safeDefault.id,
    explicit: safeDefault.explicit,
    state: defaultUi.mirror.dataset.selectionState,
  }},
  engineResults,
}}));
"""
        )

    assert payload == {
        "initial": {
            "id": "11111111-1111-4111-8111-111111111111",
            "state": "default",
            "replacements": 1,
            "preservedNodes": True,
        },
        "committed": "22222222-2222-4222-8222-222222222222",
        "nativeEvents": ["input", "change"],
        "restored": {
            "id": "22222222-2222-4222-8222-222222222222",
            "native": "22222222-2222-4222-8222-222222222222",
            "mirror": "22222222-2222-4222-8222-222222222222",
            "state": "explicit",
        },
        "invalid": {
            "id": "",
            "invalidExplicit": True,
            "native": "",
            "mirrorState": "invalid",
            "phase": "idle",
            "price": "",
            "token": "",
            "confirmationValue": "",
            "confirmationChecked": False,
        },
        "recovered": "11111111-1111-4111-8111-111111111111",
        "exactMatch": True,
        "wrongMatch": False,
        "repeat": {
            "campaign": "11111111-1111-4111-8111-111111111111",
            "native": "11111111-1111-4111-8111-111111111111",
            "phase": "idle",
            "price": "",
            "token": "",
            "confirmationValue": "",
            "confirmationChecked": False,
        },
        "safeDefault": {
            "id": "11111111-1111-4111-8111-111111111111",
            "explicit": False,
            "state": "default",
        },
        "engineResults": [
            {"expected": engine, "hidden": engine, "state": engine}
            for engine in (
                "fal-ai:pika-v2.2",
                "fal-ai:kling-video-o3-pro",
                "runway:gen4_aleph",
            )
        ],
    }


def test_repeat_contract_excludes_campaign_authority_but_keeps_campaign_editable() -> None:
    intake = INTAKE.read_text(encoding="utf-8")
    app = APP.read_text(encoding="utf-8")
    repeat_handler = app.split(
        "async function repeatGenerationStrategyFromArchive", 1
    )[1].split("function productResearchPaidStartContext", 1)[0]

    for marker in (
        "clearAllGenerationPreflightRetries();",
        "state.generationPreflight.entries.clear();",
        "resetGenerationSpecState();",
        'form.elements.real_spend_confirmation.checked = false',
        'form.elements.real_spend_confirmation.value = ""',
    ):
        assert marker in repeat_handler
    assert "campaign_id" not in repeat_handler
    assert "startRealGeneration" not in repeat_handler
    assert "resetExpressAuthorityForStrategyRepeat(form, state)" in intake
    assert "commitCompactCampaignSelection(form, state, campaignMirror)" in intake
