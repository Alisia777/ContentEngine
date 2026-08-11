from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "web" / "app"
APP_MODULE = APP / "app.js"
TRAINING = APP / "workspace-ai-research-training.js"
EXACT_SOURCES = APP / "workspace-ai-exact-youtube-sources.js"
BOOTSTRAP = APP / "workspace-research-training-bootstrap.js"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def run_node(script: str, *args: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        pytest.skip("node is unavailable")
    result = subprocess.run(
        [node, "--input-type=module", "-e", script, *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return json.loads(result.stdout)


def test_both_ai_center_roots_are_owned_by_the_v4_runtime() -> None:
    assert 'root.dataset.ceV4Owned = "ai-research-training";' in read(TRAINING)
    assert 'root.dataset.ceV4Owned = "ai-exact-youtube-sources";' in read(
        EXACT_SOURCES
    )


def test_project_scope_is_invalidated_before_old_ai_actions_can_fire() -> None:
    exact_sources = read(EXACT_SOURCES)
    training = read(TRAINING)

    assert (
        'root.addEventListener("click", guardRenderedProjectClick, true);'
        in exact_sources
    )
    assert "event.stopImmediatePropagation();" in exact_sources
    assert 'root.dataset.renderedProjectId = "";' in exact_sources
    assert "if (scopeChanged) {" in exact_sources
    assert "root.replaceChildren();" in exact_sources

    assert (
        'root.addEventListener("click", guardRenderedTrainingScopeClick, true);'
        in training
    )
    assert "function invalidateRenderedTrainingScope(root)" in training
    assert "event.stopImmediatePropagation();" in training
    assert training.count("invalidateRenderedTrainingScope(runtime.root);") == 2
    assert "if (scopeChanged) invalidateRenderedTrainingScope(root);" in training


def test_training_capture_guard_blocks_stale_selection_and_clear_is_immediate() -> None:
    training = read(TRAINING)
    invalidate = training.split(
        "function invalidateRenderedTrainingScope(root) {", 1
    )[1].split("\n}\n\nfunction guardRenderedTrainingScopeClick", 1)[0]
    invalidate = "function invalidateRenderedTrainingScope(root) {" + invalidate + "\n}"
    guard = training.split(
        "function guardRenderedTrainingScopeClick(event) {", 1
    )[1].split("\n}\n\nfunction prepareTrainingRoot", 1)[0]
    guard = "function guardRenderedTrainingScopeClick(event) {" + guard + "\n}"
    script = f"""
      class FakeElement {{}}
      globalThis.HTMLElement = FakeElement;
      let routeProject = '22222222-2222-4222-8222-222222222222';
      let routeCategory = 'household';
      const currentTrainingProjectId = () => routeProject;
      const currentCategory = () => routeCategory;
      {invalidate}
      {guard}

      const queue = {{ clears: 0, replaceChildren() {{ this.clears += 1; }} }};
      const history = {{ clears: 0, replaceChildren() {{ this.clears += 1; }} }};
      const root = new FakeElement();
      root.dataset = {{
        renderedProjectId: '11111111-1111-4111-8111-111111111111',
        renderedCategory: 'cosmetics',
      }};
      root.querySelector = (selector) => selector.includes('queue') ? queue : history;
      const staleProjectClick = {{
        currentTarget: root,
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      guardRenderedTrainingScopeClick(staleProjectClick);
      const oldASelectionArmedUnderB = !staleProjectClick.stopped;

      root.dataset.renderedProjectId = routeProject;
      root.dataset.renderedCategory = 'cosmetics';
      const staleCategoryClick = {{
        currentTarget: root,
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      guardRenderedTrainingScopeClick(staleCategoryClick);

      root.dataset.renderedCategory = routeCategory;
      const currentScopeClick = {{
        currentTarget: root,
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      guardRenderedTrainingScopeClick(currentScopeClick);

      invalidateRenderedTrainingScope(root);
      process.stdout.write(JSON.stringify({{
        oldASelectionArmedUnderB,
        staleProjectBlocked: staleProjectClick.prevented && staleProjectClick.stopped,
        staleCategoryBlocked: staleCategoryClick.prevented && staleCategoryClick.stopped,
        currentScopeAllowed: !currentScopeClick.prevented && !currentScopeClick.stopped,
        clearedImmediately: root.dataset.renderedProjectId === ''
          && root.dataset.renderedCategory === ''
          && queue.clears === 1
          && history.clears === 1,
      }}));
    """
    assert run_node(script) == {
        "oldASelectionArmedUnderB": False,
        "staleProjectBlocked": True,
        "staleCategoryBlocked": True,
        "currentScopeAllowed": True,
        "clearedImmediately": True,
    }


def test_exact_source_mount_deduplicates_same_root_and_project_but_reloads_edges() -> None:
    module_url = EXACT_SOURCES.as_uri()
    script = f"""
      class FakeElement {{
        constructor(tag = 'section') {{
          this.tagName = String(tag).toUpperCase();
          this.dataset = {{}};
          this.isConnected = true;
          this.attributes = new Map();
          this.children = [];
          this.parentNode = null;
          this.className = '';
          this.textContent = '';
          this.renderCount = 0;
          this.listeners = [];
        }}
        setAttribute(name, value) {{ this.attributes.set(name, String(value)); }}
        removeAttribute(name) {{ this.attributes.delete(name); }}
        append(...nodes) {{
          for (const node of nodes) {{
            if (node && typeof node === 'object') node.parentNode = this;
            this.children.push(node);
          }}
        }}
        prepend(...nodes) {{
          for (const node of [...nodes].reverse()) {{
            if (node && typeof node === 'object') node.parentNode = this;
            this.children.unshift(node);
          }}
        }}
        replaceChildren(...nodes) {{
          this.renderCount += 1;
          this.children = [];
          this.append(...nodes);
        }}
        addEventListener(type, callback, options) {{
          this.listeners.push({{
            type,
            callback,
            capture: options === true || options?.capture === true,
          }});
        }}
        querySelector() {{ return null; }}
        matches() {{ return false; }}
        remove() {{ this.isConnected = false; }}
      }}

      const projectOne = '11111111-1111-4111-8111-111111111111';
      const projectTwo = '22222222-2222-4222-8222-222222222222';
      let root = new FakeElement();
      root.setAttribute('data-ai-exact-youtube-sources-root', 'true');
      const calls = [];
      const deferred = [];
      const windowListeners = new Map();
      const queuedWindowMicrotasks = [];
      let deferRequests = false;
      const responseFor = (projectId) => ({{
        ok: true,
        version: 'exact-youtube-source-queue-v2',
        project_id: projectId,
        sources: [],
        contract: {{
          url_is_video_evidence: false,
          requires_lawful_mp4: true,
          unattached_source_affects_learning: false,
          unattached_source_affects_generation: false,
          external_call_started: false,
          paid_call_started: false,
        }},
      }});
      const api = {{
        call() {{}},
        async exactYoutubeSourceQueue({{ projectId }}) {{
          calls.push(projectId);
          if (!deferRequests) return responseFor(projectId);
          return new Promise((resolve) => deferred.push({{ projectId, resolve }}));
        }},
      }};
      globalThis.HTMLElement = FakeElement;
      globalThis.document = {{
        body: new FakeElement('body'),
        createElement: (tag) => new FakeElement(tag),
        querySelector(selector) {{
          if (selector === '[data-ai-exact-youtube-sources-root]') return root;
          return null;
        }},
      }};
      globalThis.window = {{
        location: {{ hash: '#/workspace/ai?project_id=' + projectOne }},
        sessionStorage: {{}},
        addEventListener(type, callback) {{
          const callbacks = windowListeners.get(type) || [];
          callbacks.push(callback);
          windowListeners.set(type, callbacks);
        }},
        queueMicrotask(callback) {{ queuedWindowMicrotasks.push(callback); }},
        ContentEngineDesktopV4: {{
          route: () => '/workspace/ai',
          registerAdapter() {{}},
        }},
        ContentEngineWorkspaceRuntime: {{ getApi: () => api }},
      }};

      const mod = await import({json.dumps(module_url)} + '?mount-contract=1');
      queuedWindowMicrotasks.length = 0;
      const settle = async () => {{
        await Promise.resolve();
        await Promise.resolve();
        await new Promise((resolve) => setImmediate(resolve));
      }};

      mod.AiExactYoutubeSources.mount({{ force: true }});
      await settle();
      const initial = calls.length;

      for (const callback of windowListeners.get('hashchange') || []) callback();
      while (queuedWindowMicrotasks.length) queuedWindowMicrotasks.shift()();
      for (const callback of windowListeners.get('contentengine:v4-route-ready') || []) callback();
      await settle();
      const duplicateRouteSignals = calls.length;

      mod.AiExactYoutubeSources.mount();
      await settle();
      const repeatedSameRootProject = calls.length;

      mod.AiExactYoutubeSources.mount({{ force: true }});
      await settle();
      const forced = calls.length;

      root.append({{ stale: true }});
      window.location.hash = '#/workspace/ai?project_id=' + projectTwo;
      const guard = root.listeners.find((listener) => (
        listener.type === 'click' && listener.capture === true
      ));
      const staleClick = {{
        currentTarget: root,
        target: {{ closest: () => ({{ href: '#stale' }}) }},
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      guard.callback(staleClick);
      const staleClickBlockedInCapture = staleClick.prevented && staleClick.stopped;
      const oldAHandoffArmedUnderB = !staleClick.stopped;
      mod.AiExactYoutubeSources.mount();
      const oldContentClearedOnProjectSwitch = root.children.length === 0
        && root.dataset.renderedProjectId === '';
      await settle();
      const newProject = calls.length;

      root.isConnected = false;
      root = new FakeElement();
      root.setAttribute('data-ai-exact-youtube-sources-root', 'true');
      mod.AiExactYoutubeSources.mount();
      await settle();
      const newRoot = calls.length;

      deferRequests = true;
      window.location.hash = '#/workspace/ai?project_id=' + projectOne;
      const staleRoot = root;
      const staleRootRendersBefore = staleRoot.renderCount;
      mod.AiExactYoutubeSources.mount({{ force: true }});
      while (deferred.length < 1) await Promise.resolve();
      const staleRootRendersAfterRequestStarted = staleRoot.renderCount;

      staleRoot.isConnected = false;
      root = new FakeElement();
      root.setAttribute('data-ai-exact-youtube-sources-root', 'true');
      window.location.hash = '#/workspace/ai?project_id=' + projectTwo;
      mod.AiExactYoutubeSources.mount();
      await Promise.resolve();
      const requestsBeforeOldResolution = calls.length;

      const oldRequest = deferred.shift();
      oldRequest.resolve(responseFor(projectOne));
      while (deferred.length < 1) await Promise.resolve();
      const latestRequest = deferred.shift();
      const staleRootRendersAfterOldResolution = staleRoot.renderCount;
      latestRequest.resolve(responseFor(projectTwo));
      await settle();

      process.stdout.write(JSON.stringify({{
        initial,
        duplicateRouteSignals,
        repeatedSameRootProject,
        forced,
        newProject,
        oldContentClearedOnProjectSwitch,
        staleClickBlockedInCapture,
        oldAHandoffArmedUnderB,
        newRoot,
        race: {{
          requestsBeforeOldResolution,
          staleRootRendersBefore,
          staleRootRendersAfterRequestStarted,
          staleRootRendersAfterOldResolution,
          latestProject: latestRequest.projectId,
          latestRootRenders: root.renderCount,
        }},
        calls,
      }}));
    """
    assert run_node(script) == {
        "initial": 1,
        "duplicateRouteSignals": 1,
        "repeatedSameRootProject": 1,
        "forced": 2,
        "newProject": 3,
        "oldContentClearedOnProjectSwitch": True,
        "staleClickBlockedInCapture": True,
        "oldAHandoffArmedUnderB": False,
        "newRoot": 4,
        "race": {
            "requestsBeforeOldResolution": 5,
            "staleRootRendersBefore": 2,
            "staleRootRendersAfterRequestStarted": 3,
            "staleRootRendersAfterOldResolution": 3,
            "latestProject": "22222222-2222-4222-8222-222222222222",
            "latestRootRenders": 2,
        },
        "calls": [
            "11111111-1111-4111-8111-111111111111",
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
            "22222222-2222-4222-8222-222222222222",
            "11111111-1111-4111-8111-111111111111",
            "22222222-2222-4222-8222-222222222222",
        ],
    }


def test_runtime_ready_retries_an_early_ai_route_without_terminal_failure(
    tmp_path: Path,
) -> None:
    assert (
        'window.dispatchEvent(new CustomEvent("contentengine:workspace-runtime-ready"));'
        in read(APP_MODULE)
    )
    for module_name in (
        "workspace-ai-research-training.js",
        "workspace-ai-exact-youtube-sources.js",
        "workspace-research-failure-recovery.js",
    ):
        (tmp_path / module_name).write_text("", encoding="utf-8")

    script = """
      import fs from 'node:fs';
      import { pathToFileURL } from 'node:url';

      const source = fs.readFileSync(process.argv[1], 'utf8');
      const baseUrl = pathToFileURL(process.argv[2]).href;
      const listeners = new Map();
      const emitted = [];
      const warnings = [];
      let flushes = 0;
      let styles = 0;

      class FakeCustomEvent {
        constructor(type, options = {}) {
          this.type = type;
          this.detail = options.detail;
        }
      }
      class FakeLink {
        constructor() {
          this.dataset = {};
          this.rel = '';
          this.href = '';
        }
        addEventListener(type, callback) {
          if (type === 'load') queueMicrotask(callback);
        }
        remove() {}
      }

      const addEventListener = (type, callback) => {
        const callbacks = listeners.get(type) || [];
        callbacks.push(callback);
        listeners.set(type, callbacks);
      };
      const dispatchEvent = (event) => {
        emitted.push(event.type);
        for (const callback of listeners.get(event.type) || []) callback(event);
        return true;
      };
      globalThis.CustomEvent = FakeCustomEvent;
      globalThis.document = {
        currentScript: { src: baseUrl },
        documentElement: { dataset: {} },
        querySelectorAll: () => [],
        createElement: () => new FakeLink(),
        head: { append() { styles += 1; } },
      };
      globalThis.window = {
        location: { hash: '#/workspace/ai?project_id=11111111-1111-4111-8111-111111111111' },
        queueMicrotask,
        addEventListener,
        dispatchEvent,
        ContentEngineDesktopV4: {
          async flush() { flushes += 1; },
        },
      };

      const originalWarn = console.warn;
      console.warn = (...args) => warnings.push(args.map(String).join(' '));
      try {
        eval(source);
        dispatchEvent(new FakeCustomEvent('contentengine:v4-route-ready'));
        for (let index = 0; index < 4; index += 1) await Promise.resolve();
        const beforeRuntime = {
          flushes,
          failures: emitted.filter((type) => type === 'contentengine:research-learning-failed').length,
          warnings: warnings.length,
          styles,
        };

        const api = { call() {} };
        window.ContentEngineWorkspaceRuntime = { getApi: () => api };
        dispatchEvent(new FakeCustomEvent('contentengine:workspace-runtime-ready'));
        for (let index = 0; index < 100 && flushes === 0; index += 1) {
          await new Promise((resolve) => setTimeout(resolve, 2));
        }
        process.stdout.write(JSON.stringify({
          beforeRuntime,
          afterRuntime: {
            flushes,
            failures: emitted.filter((type) => type === 'contentengine:research-learning-failed').length,
            warnings: warnings.length,
            styles,
          },
        }));
      } finally {
        console.warn = originalWarn;
      }
    """
    result = run_node(script, str(BOOTSTRAP), str(tmp_path / "bootstrap.js"))
    assert result == {
        "beforeRuntime": {
            "flushes": 0,
            "failures": 0,
            "warnings": 0,
            "styles": 0,
        },
        "afterRuntime": {
            "flushes": 1,
            "failures": 0,
            "warnings": 0,
            "styles": 3,
        },
    }
