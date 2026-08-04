/*
 * Small DOM reconciler for repeated updates inside one workspace route.
 *
 * The application renders trusted markup from its current state. Replacing the
 * whole workspace surface for every poll/filter update made Safari tear down
 * media, focus, animations and large Finder lists. This patcher keeps compatible
 * nodes alive, moves uniquely keyed records, and changes only the DOM that is
 * different in the next render.
 */

const WORKSPACE_PATCH_KEY_ATTRIBUTES = Object.freeze([
  "data-ce-patch-key",
  "data-workspace-item-key",
  "data-work-item-id",
  "data-task-id",
  "data-generation-job-id",
  "data-review-result-id",
  "data-review-id",
  "data-placement-id",
  "data-publication-id",
  "data-payout-id",
  "data-media-id",
  "data-member-id",
  "data-invite-email",
  "data-folder-id",
  "data-campaign-id",
  "data-research-id",
  "data-view-id",
  "data-practical-review-id",
  "data-notification-id",
  "data-job-id",
  "data-incident-id",
  "data-item-key",
]);

const CONTENT_REVIEW_RUNTIME_ATTRIBUTES = new Set([
  "data-media-binding",
  "data-exact-media-state",
  "data-content-review-loaded-src",
  "data-content-review-ended-src",
  "data-content-review-safe-zone-geometry",
]);

const RUNTIME_OWNED_SELECTOR = [
  "[data-ce-v4-owned]",
  ".ce-v4-home",
  ".ce-v4-finder-toolbar",
  ".ce-v4-folder-search",
  ".ce-v4-finder-sidebar-close",
  ".ce-v4-finder-sidebar-backdrop",
  ".ce-v4-finder-kind",
].join(",");

import "https://cdn.jsdelivr.net/npm/dompurify@3.4.13/dist/purify.min.js";

const BLOCKED_MARKUP_ELEMENTS = [
  "base",
  "embed",
  "iframe",
  "link",
  "meta",
  "object",
  "script",
  "style",
  "template",
];

const DOMPurify = globalThis.DOMPurify;

function hardenWorkspaceMarkup(fragment) {
  fragment.querySelectorAll("*").forEach((element) => {
    [...element.attributes].forEach((attribute) => {
      const name = attribute.name.toLowerCase();
      if (
        name === "style"
          && /(?:@import|behavior\s*:|expression\s*\(|-moz-binding|url\s*\()/iu.test(attribute.value)
      ) {
        element.removeAttribute(attribute.name);
      }
    });
    if (element.getAttribute("target") === "_blank") {
      const rel = new Set(String(element.getAttribute("rel") || "").split(/\s+/u).filter(Boolean));
      rel.add("noopener");
      rel.add("noreferrer");
      element.setAttribute("rel", [...rel].join(" "));
    }
  });
}

function parseWorkspaceMarkup(markup) {
  if (!DOMPurify?.sanitize) throw new Error("Workspace HTML sanitizer is unavailable.");
  const fragment = DOMPurify.sanitize(String(markup || ""), {
    RETURN_DOM_FRAGMENT: true,
    ADD_ATTR: ["target"],
    FORBID_ATTR: ["srcdoc", "srcset"],
    FORBID_TAGS: BLOCKED_MARKUP_ELEMENTS,
  });
  hardenWorkspaceMarkup(fragment);
  return fragment;
}

function runtimeOwnedNode(node) {
  return node instanceof Element && node.matches(RUNTIME_OWNED_SELECTOR);
}

function declarativeClassName(node) {
  if (!(node instanceof Element)) return "";
  return [...node.classList]
    .filter((token) => !token.startsWith("ce-v4-"))
    .sort()
    .join(".");
}

function patchKey(node) {
  if (!(node instanceof Element)) return "";
  const explicit = String(node.getAttribute("data-ce-patch-key") || "").trim();
  if (explicit) return `${node.localName}[data-ce-patch-key=${explicit}]`;
  const semanticParts = WORKSPACE_PATCH_KEY_ATTRIBUTES
    .filter((attribute) => attribute !== "data-ce-patch-key")
    .map((attribute) => [attribute, String(node.getAttribute(attribute) || "").trim()])
    .filter(([, value]) => Boolean(value));
  if (semanticParts.length) {
    return `${node.localName}${semanticParts.map(([attribute, value]) => `[${attribute}=${value}]`).join("")}`;
  }
  if (node.id && node.dataset.ceV4RuntimeId !== "true") return `${node.localName}#${node.id}`;
  return "";
}

function reviewForm(node) {
  if (!(node instanceof Element)) return null;
  if (node.matches(".content-review-decision-form")) return node;
  return node.closest(".content-review-decision-form");
}

function reviewMediaIdentity(form) {
  if (!(form instanceof Element)) return "";
  const media = form.querySelector("[data-content-review-exact-media]");
  const reviewId = String(form.getAttribute("data-review-id") || "").trim();
  if (!(media instanceof Element)) return `${reviewId}|none`;
  return [
    reviewId,
    media.localName,
    media.getAttribute("data-media-kind") || "",
    media.getAttribute("src") || "",
    media.getAttribute("srcset") || "",
  ].join("|");
}

function sameReviewBinding(current, next) {
  const currentForm = reviewForm(current);
  const nextForm = reviewForm(next);
  return Boolean(
    currentForm
    && nextForm
    && reviewMediaIdentity(currentForm) === reviewMediaIdentity(nextForm),
  );
}

function runtimeOwnedAttribute(node, attributeName) {
  if (!(node instanceof Element)) return false;
  if (attributeName.startsWith("data-ce-v4-")) return true;
  if (CONTENT_REVIEW_RUNTIME_ATTRIBUTES.has(attributeName) && reviewForm(node)) return true;
  return attributeName === "style"
    && node.matches("[data-content-review-safe-zone-stage]")
    && node.dataset.contentReviewSafeZoneGeometry === "ready";
}

function mediaSourceSignature(node) {
  if (!(node instanceof HTMLMediaElement)) return "";
  const sources = [...node.querySelectorAll("source")].map((source) => [
    source.getAttribute("src") || "",
    source.getAttribute("type") || "",
    source.getAttribute("media") || "",
  ].join("|"));
  return [
    node.getAttribute("src") || "",
    node.getAttribute("poster") || "",
    ...sources,
  ].join("||");
}

function patchHint(node) {
  if (!(node instanceof Element)) return "";
  return [
    node.localName,
    declarativeClassName(node),
    node.getAttribute("role") || "",
    node.getAttribute("name") || "",
    node.getAttribute("type") || "",
    node.getAttribute("data-action") || "",
  ].join("|");
}

function compatibleNodes(current, next) {
  if (!current || !next || current.nodeType !== next.nodeType) return false;
  if (current.nodeType !== Node.ELEMENT_NODE) return true;
  if (current.localName !== next.localName || current.namespaceURI !== next.namespaceURI) return false;
  const currentKey = patchKey(current);
  const nextKey = patchKey(next);
  return !currentKey && !nextKey ? true : currentKey === nextKey;
}

function uniqueKeyedNodes(nodes) {
  const records = new Map();
  const duplicates = new Set();
  nodes.forEach((node) => {
    const key = patchKey(node);
    if (!key) return;
    if (records.has(key)) {
      records.delete(key);
      duplicates.add(key);
      return;
    }
    if (!duplicates.has(key)) records.set(key, node);
  });
  return records;
}

function syncClassName(current, next) {
  const runtimeClasses = [...current.classList]
    .filter((token) => (
      token.startsWith("ce-v4-")
      || (token === "is-sidebar-open" && current.matches(".workspace-board"))
      || (token === "is-open" && current.matches(".workspace-board__sidebar"))
    ));
  const classes = new Set([...next.classList, ...runtimeClasses]);
  const value = [...classes].join(" ");
  if (current.getAttribute("class") !== value) {
    if (value) current.setAttribute("class", value);
    else current.removeAttribute("class");
  }
}

function syncAttributes(current, next) {
  [...current.attributes].forEach((attribute) => {
    if (attribute.name === "class" || runtimeOwnedAttribute(current, attribute.name)) return;
    if (!next.hasAttribute(attribute.name)) current.removeAttribute(attribute.name);
  });
  [...next.attributes].forEach((attribute) => {
    if (attribute.name === "class") return;
    if (runtimeOwnedAttribute(current, attribute.name) && current.hasAttribute(attribute.name)) return;
    if (current.getAttribute(attribute.name) !== attribute.value) {
      current.setAttribute(attribute.name, attribute.value);
    }
  });
  syncClassName(current, next);
}

function syncControlState(current, next) {
  if (current instanceof HTMLInputElement && next instanceof HTMLInputElement) {
    if (current.type !== "file") current.value = next.value;
    current.checked = next.checked;
    current.indeterminate = next.indeterminate;
    return;
  }
  if (current instanceof HTMLTextAreaElement && next instanceof HTMLTextAreaElement) {
    current.value = next.value;
    return;
  }
  if (current instanceof HTMLSelectElement && next instanceof HTMLSelectElement) {
    const selected = Array.from(next.options, (option) => option.selected);
    Array.from(current.options).forEach((option, index) => {
      option.selected = selected[index] === true;
    });
  }
}

function declarativeChildren(parent) {
  return [...parent.childNodes].filter((node) => !runtimeOwnedNode(node));
}

function declarativeChildAt(parent, index) {
  let position = 0;
  for (const node of parent.childNodes) {
    if (runtimeOwnedNode(node)) continue;
    if (position === index) return node;
    position += 1;
  }
  return null;
}

function findUnkeyedCandidate(oldChildren, used, next, index) {
  const preferred = oldChildren[index];
  const nextHint = patchHint(next);
  if (
    preferred
    && !used.has(preferred)
    && !patchKey(preferred)
    && compatibleNodes(preferred, next)
    && patchHint(preferred) === nextHint
  ) return preferred;

  const hinted = oldChildren.find((candidate) => (
    !used.has(candidate)
    && !patchKey(candidate)
    && compatibleNodes(candidate, next)
    && patchHint(candidate) === nextHint
  ));
  if (hinted) return hinted;

  if (
    preferred
    && !used.has(preferred)
    && !patchKey(preferred)
    && compatibleNodes(preferred, next)
  ) return preferred;
  return null;
}

function patchChildren(current, next) {
  const oldChildren = declarativeChildren(current);
  const nextChildren = [...next.childNodes];
  const keyed = uniqueKeyedNodes(oldChildren);
  const used = new Set();

  nextChildren.forEach((nextChild, index) => {
    const key = patchKey(nextChild);
    let candidate = key ? keyed.get(key) : null;
    if (candidate && (used.has(candidate) || !compatibleNodes(candidate, nextChild))) {
      candidate = null;
    }
    if (!candidate && !key) {
      candidate = findUnkeyedCandidate(oldChildren, used, nextChild, index);
    }

    const reference = declarativeChildAt(current, index);
    if (!candidate) {
      candidate = nextChild.cloneNode(true);
      current.insertBefore(candidate, reference);
    } else if (candidate !== reference) {
      current.insertBefore(candidate, reference);
    }
    used.add(candidate);
    patchNode(candidate, nextChild);
  });

  oldChildren.forEach((node) => {
    if (!used.has(node) && node.parentNode === current) node.remove();
  });
}

function patchNode(current, next) {
  if (
    current instanceof HTMLFormElement
    && next instanceof HTMLFormElement
    && current.matches(".content-review-decision-form")
    && next.matches(".content-review-decision-form")
    && reviewMediaIdentity(current) !== reviewMediaIdentity(next)
  ) {
    const replacement = next.cloneNode(true);
    current.replaceWith(replacement);
    return replacement;
  }
  if (!compatibleNodes(current, next)) {
    const replacement = next.cloneNode(true);
    current.replaceWith(replacement);
    return replacement;
  }
  if (current.nodeType !== Node.ELEMENT_NODE) {
    if (current.nodeValue !== next.nodeValue) current.nodeValue = next.nodeValue;
    return current;
  }
  if (
    sameReviewBinding(current, next)
    && current.matches("[data-content-review-media-state]")
  ) return current;
  if (current.isEqualNode(next)) return current;

  const sourceChanged = current instanceof HTMLMediaElement
    && mediaSourceSignature(current) !== mediaSourceSignature(next);
  const detailsOpen = current instanceof HTMLDetailsElement ? current.open : null;
  const reviewControlState = sameReviewBinding(current, next)
    && current.matches('[name="media_watched_confirmed"], [data-review-decision-submit]')
    ? {
        checked: current instanceof HTMLInputElement ? current.checked : null,
        disabled: "disabled" in current ? current.disabled : null,
      }
    : null;
  syncAttributes(current, next);
  patchChildren(current, next);
  syncControlState(current, next);
  if (detailsOpen !== null) current.open = detailsOpen;
  if (reviewControlState) {
    if (reviewControlState.checked !== null) current.checked = reviewControlState.checked;
    if (reviewControlState.disabled !== null) current.disabled = reviewControlState.disabled;
  }
  if (sourceChanged) current.load();
  return current;
}

export function patchWorkspaceContent(container, markup) {
  if (!(container instanceof HTMLElement)) return false;
  const activeElement = container.contains(document.activeElement) ? document.activeElement : null;
  patchChildren(container, parseWorkspaceMarkup(markup));
  if (
    activeElement instanceof HTMLElement
    && activeElement.isConnected
    && document.activeElement !== activeElement
  ) activeElement.focus({ preventScroll: true });
  return true;
}
