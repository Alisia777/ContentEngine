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
      const ROUTE = '/workspace/ai';
      let route = ROUTE;
      const routePath = () => route;
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


def test_owned_ai_roots_unmount_off_route_and_reenter_with_fresh_requests() -> None:
    training_url = TRAINING.as_uri()
    exact_sources_url = EXACT_SOURCES.as_uri()
    script = f"""
      const dataKey = (attribute) => attribute.slice(5).replace(
        /-([a-z])/gu,
        (_, letter) => letter.toUpperCase(),
      );

      class FakeElement {{
        constructor(tag = 'div') {{
          this.tagName = String(tag).toUpperCase();
          this.dataset = {{}};
          this.attributes = new Map();
          this.children = [];
          this.parentNode = null;
          this.isConnected = false;
          this.className = '';
          this.textContent = '';
          this.value = '';
          this.hidden = false;
          this.listeners = [];
          this.replaceCount = 0;
          this.classList = {{
            toggle: (name, enabled) => {{
              const names = new Set(this.className.split(/\\s+/u).filter(Boolean));
              if (enabled) names.add(name);
              else names.delete(name);
              this.className = [...names].join(' ');
            }},
          }};
        }}
        connect(value) {{
          this.isConnected = value;
          this.children.forEach((child) => child?.connect?.(value));
        }}
        detach(node) {{
          if (!node?.parentNode) return;
          node.parentNode.children = node.parentNode.children.filter((item) => item !== node);
          node.parentNode = null;
        }}
        append(...nodes) {{
          for (const node of nodes) {{
            if (!node || typeof node !== 'object') continue;
            this.detach(node);
            node.parentNode = this;
            node.connect?.(this.isConnected);
            this.children.push(node);
          }}
        }}
        prepend(...nodes) {{
          for (const node of [...nodes].reverse()) {{
            if (!node || typeof node !== 'object') continue;
            this.detach(node);
            node.parentNode = this;
            node.connect?.(this.isConnected);
            this.children.unshift(node);
          }}
        }}
        insertBefore(node, reference) {{
          this.detach(node);
          const index = this.children.indexOf(reference);
          node.parentNode = this;
          node.connect?.(this.isConnected);
          if (index < 0) this.children.push(node);
          else this.children.splice(index, 0, node);
        }}
        replaceChildren(...nodes) {{
          this.replaceCount += 1;
          this.children.forEach((child) => {{
            child.parentNode = null;
            child.connect?.(false);
          }});
          this.children = [];
          this.append(...nodes);
        }}
        remove() {{
          if (this.parentNode) {{
            this.parentNode.children = this.parentNode.children.filter(
              (item) => item !== this,
            );
          }}
          this.parentNode = null;
          this.connect(false);
        }}
        setAttribute(name, value) {{
          this.attributes.set(name, String(value));
          if (name.startsWith('data-')) this.dataset[dataKey(name)] = String(value);
        }}
        getAttribute(name) {{
          if (this.attributes.has(name)) return this.attributes.get(name);
          if (name.startsWith('data-')) return this.dataset[dataKey(name)] ?? null;
          return null;
        }}
        removeAttribute(name) {{
          this.attributes.delete(name);
          if (name.startsWith('data-')) delete this.dataset[dataKey(name)];
        }}
        addEventListener(type, callback, options) {{
          this.listeners.push({{
            type,
            callback,
            capture: options === true || options?.capture === true,
          }});
        }}
        matches(selector) {{
          const alternatives = String(selector).split(',').map((value) => value.trim());
          return alternatives.some((candidate) => {{
            if (!candidate || candidate.startsWith(':scope')) return false;
            const tag = candidate.match(/^[a-z]+/iu)?.[0];
            if (tag && this.tagName !== tag.toUpperCase()) return false;
            for (const match of candidate.matchAll(/[.]([a-z0-9_-]+)/giu)) {{
              if (!this.className.split(/\\s+/u).includes(match[1])) return false;
            }}
            for (const match of candidate.matchAll(
              /\\[([^=\\]]+)(?:=[\"']?([^\"'\\]]+)[\"']?)?\\]/gu,
            )) {{
              const actual = this.getAttribute(match[1]);
              if (actual === null) return false;
              if (match[2] !== undefined && actual !== match[2]) return false;
            }}
            return true;
          }});
        }}
        descendants() {{
          return this.children.flatMap((child) => [child, ...child.descendants()]);
        }}
        querySelector(selector) {{
          if (selector === ':scope > header, .ai-learning-hero') {{
            return this.children.find((child) => child.tagName === 'HEADER')
              || this.descendants().find((child) => child.matches('.ai-learning-hero'))
              || null;
          }}
          return this.descendants().find((child) => child.matches(selector)) || null;
        }}
        querySelectorAll(selector) {{
          return this.descendants().filter((child) => child.matches(selector));
        }}
      }}

      globalThis.HTMLElement = FakeElement;
      globalThis.HTMLSelectElement = FakeElement;
      globalThis.HTMLInputElement = FakeElement;
      globalThis.HTMLButtonElement = FakeElement;

      const body = new FakeElement('body');
      body.connect(true);
      const host = new FakeElement('main');
      host.className = 'ai-learning-control-room';
      body.append(host);
      const documentListeners = new Map();
      globalThis.document = {{
        body,
        createElement: (tag) => new FakeElement(tag),
        querySelector: (selector) => {{
          if (body.matches(selector)) return body;
          return body.querySelector(selector);
        }},
        querySelectorAll: (selector) => {{
          const matches = body.querySelectorAll(selector);
          return body.matches(selector) ? [body, ...matches] : matches;
        }},
        addEventListener(type, callback) {{
          const callbacks = documentListeners.get(type) || [];
          callbacks.push(callback);
          documentListeners.set(type, callbacks);
        }},
      }};

      const projectId = '11111111-1111-4111-8111-111111111111';
      let route = '/workspace/ai';
      const storage = new Map();
      const queuedMicrotasks = [];
      const trainingRequests = [];
      const exactRequests = [];
      const api = {{
        call(name, payload) {{
          return new Promise((resolve) => trainingRequests.push({{
            name,
            payload,
            resolve,
          }}));
        }},
        exactYoutubeSourceQueue({{ projectId: requestedProjectId }}) {{
          return new Promise((resolve) => exactRequests.push({{
            projectId: requestedProjectId,
            resolve,
          }}));
        }},
      }};
      globalThis.window = {{
        location: {{ hash: '#/workspace/ai?project_id=' + projectId }},
        history: {{
          state: null,
          replaceState(_state, _title, nextHash) {{ this.lastHash = nextHash; }},
        }},
        sessionStorage: {{
          getItem: (key) => storage.get(key) ?? null,
          setItem: (key, value) => storage.set(key, String(value)),
        }},
        queueMicrotask: (callback) => queuedMicrotasks.push(callback),
        addEventListener() {{}},
        getComputedStyle: () => ({{ display: 'block', visibility: 'visible' }}),
        ContentEngineDesktopV4: {{
          route: () => route,
          registerAdapter() {{}},
        }},
        ContentEngineWorkspaceRuntime: {{
          getApi: () => api,
          getExactYoutubeHandoffContext: () => ({{ project_id: projectId }}),
        }},
      }};

      const training = await import(
        {json.dumps(training_url)} + '?route-exit-lifecycle=1'
      );
      const exact = await import(
        {json.dumps(exact_sources_url)} + '?route-exit-lifecycle=1'
      );
      queuedMicrotasks.length = 0;
      const settle = async () => {{
        await Promise.resolve();
        await Promise.resolve();
        await new Promise((resolve) => setImmediate(resolve));
      }};
      const waitFor = async (predicate) => {{
        for (let index = 0; index < 20 && !predicate(); index += 1) {{
          await Promise.resolve();
        }}
      }};

      training.AiResearchTraining.mount();
      exact.AiExactYoutubeSources.mount();
      await waitFor(() => trainingRequests.length === 1 && exactRequests.length === 1);
      const oldTrainingRoot = document.querySelector('[data-ai-research-training-root]');
      const oldExactRoot = document.querySelector('[data-ai-exact-youtube-sources-root]');
      const oldTrainingQueue = oldTrainingRoot.querySelector(
        '[data-ai-research-training-queue]',
      );
      const oldTrainingHistory = oldTrainingRoot.querySelector(
        '[data-ai-research-training-history]',
      );
      const oldTrainingMutations = oldTrainingQueue.replaceCount
        + oldTrainingHistory.replaceCount;
      const oldExactMutations = oldExactRoot.replaceCount;

      route = '/workspace/generation';
      window.location.hash = '#/workspace/generation?project_id=' + projectId;
      const exactGuard = oldExactRoot.listeners.find(
        (listener) => listener.type === 'click' && listener.capture,
      );
      const trainingGuard = oldTrainingRoot.listeners.find(
        (listener) => listener.type === 'click' && listener.capture,
      );
      const staleExactClick = {{
        currentTarget: oldExactRoot,
        target: {{ closest: () => ({{ href: '#stale-exact' }}) }},
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      const staleTrainingClick = {{
        currentTarget: oldTrainingRoot,
        prevented: false,
        stopped: false,
        preventDefault() {{ this.prevented = true; }},
        stopImmediatePropagation() {{ this.stopped = true; }},
      }};
      exactGuard.callback(staleExactClick);
      trainingGuard.callback(staleTrainingClick);
      const offRouteHandoff = exact.beginMediaHandoff({{ id: 'stale-source' }});

      exact.AiExactYoutubeSources.mount();
      training.AiResearchTraining.mount();
      const rootsAfterExit = {{
        exact: document.querySelectorAll('[data-ai-exact-youtube-sources-root]').length,
        training: document.querySelectorAll('[data-ai-research-training-root]').length,
      }};

      trainingRequests[0].resolve({{
        project_id: projectId,
        product_category: 'other',
        queue: [],
        learned: [],
        capabilities: {{}},
      }});
      exactRequests[0].resolve({{
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
      await settle();
      const staleResponsesIgnored = !oldTrainingRoot.isConnected
        && !oldExactRoot.isConnected
        && oldTrainingMutations === oldTrainingQueue.replaceCount
          + oldTrainingHistory.replaceCount
        && oldExactMutations === oldExactRoot.replaceCount
        && document.querySelectorAll('[data-ai-exact-youtube-sources-root]').length === 0
        && document.querySelectorAll('[data-ai-research-training-root]').length === 0;

      route = '/workspace/ai';
      window.location.hash = '#/workspace/ai';
      exact.AiExactYoutubeSources.mount();
      const missingProjectKeepsExactUnmounted = document.querySelectorAll(
        '[data-ai-exact-youtube-sources-root]',
      ).length === 0;

      window.location.hash = '#/workspace/ai?project_id=' + projectId;
      training.AiResearchTraining.mount();
      exact.AiExactYoutubeSources.mount();
      await waitFor(() => trainingRequests.length === 2 && exactRequests.length === 2);
      const newTrainingRoot = document.querySelector('[data-ai-research-training-root]');
      const newExactRoot = document.querySelector('[data-ai-exact-youtube-sources-root]');
      trainingRequests[1].resolve({{
        project_id: projectId,
        product_category: 'other',
        queue: [],
        learned: [],
        capabilities: {{}},
      }});
      exactRequests[1].resolve({{
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
      await settle();
      training.AiResearchTraining.mount();
      exact.AiExactYoutubeSources.mount();
      await settle();

      process.stdout.write(JSON.stringify({{
        initialRequests: {{
          training: trainingRequests[0].payload.project_id,
          exact: exactRequests[0].projectId,
        }},
        offRouteGuards: {{
          exact: staleExactClick.prevented && staleExactClick.stopped,
          training: staleTrainingClick.prevented && staleTrainingClick.stopped,
          handoffRejected: offRouteHandoff === false,
        }},
        rootsAfterExit,
        staleResponsesIgnored,
        missingProjectKeepsExactUnmounted,
        reentry: {{
          oneTrainingRoot: document.querySelectorAll(
            '[data-ai-research-training-root]',
          ).length === 1,
          oneExactRoot: document.querySelectorAll(
            '[data-ai-exact-youtube-sources-root]',
          ).length === 1,
          freshTrainingRoot: newTrainingRoot !== oldTrainingRoot,
          freshExactRoot: newExactRoot !== oldExactRoot,
          trainingRenderedProject: newTrainingRoot.dataset.renderedProjectId,
          exactRenderedProject: newExactRoot.dataset.renderedProjectId,
          trainingRequests: trainingRequests.length,
          exactRequests: exactRequests.length,
        }},
      }}));
    """
    assert run_node(script) == {
        "initialRequests": {
            "training": "11111111-1111-4111-8111-111111111111",
            "exact": "11111111-1111-4111-8111-111111111111",
        },
        "offRouteGuards": {
            "exact": True,
            "training": True,
            "handoffRejected": True,
        },
        "rootsAfterExit": {"exact": 0, "training": 0},
        "staleResponsesIgnored": True,
        "missingProjectKeepsExactUnmounted": True,
        "reentry": {
            "oneTrainingRoot": True,
            "oneExactRoot": True,
            "freshTrainingRoot": True,
            "freshExactRoot": True,
            "trainingRenderedProject": "11111111-1111-4111-8111-111111111111",
            "exactRenderedProject": "11111111-1111-4111-8111-111111111111",
            "trainingRequests": 2,
            "exactRequests": 2,
        },
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
