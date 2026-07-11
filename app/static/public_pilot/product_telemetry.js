(function () {
  "use strict";

  const endpoint = "/api/product-events";
  const sessionStorageKey = "qvf.productTelemetry.session.v1";
  const clientEventNames = new Set([
    "page_viewed",
    "navigation_clicked",
    "primary_action_clicked",
    "help_opened",
    "validation_failed",
    "onboarding_started",
    "product_selected",
    "generation_requested",
    "human_review_completed",
    "video_approved",
    "video_rejected",
    "publishing_package_approved",
  ]);

  function randomId(prefix) {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return prefix + ":" + window.crypto.randomUUID();
    }
    const randomPart = Math.random().toString(36).slice(2);
    return prefix + ":" + Date.now().toString(36) + ":" + randomPart;
  }

  function getSession() {
    try {
      const existing = window.sessionStorage.getItem(sessionStorageKey);
      if (existing) {
        return { id: existing, isNew: false };
      }
      const created = randomId("session");
      window.sessionStorage.setItem(sessionStorageKey, created);
      return { id: created, isNew: true };
    } catch (_error) {
      return { id: randomId("session"), isNew: true };
    }
  }

  const session = getSession();

  function cleanStaticValue(value, maxLength) {
    if (typeof value !== "string") {
      return null;
    }
    const cleaned = value.trim();
    if (!cleaned || cleaned.length > maxLength || !/^[A-Za-z0-9._:-]+$/.test(cleaned)) {
      return null;
    }
    return cleaned;
  }

  function positiveInteger(value) {
    if (!/^\d+$/.test(value || "")) {
      return null;
    }
    const parsed = Number(value);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  }

  function send(eventName, context) {
    if (eventName !== "session_started" && !clientEventNames.has(eventName)) {
      return;
    }
    const body = Object.assign(
      {
        event_name: eventName,
        event_version: 1,
        occurred_at: new Date().toISOString(),
        source: "web",
        session_id: session.id,
        idempotency_key: randomId("event"),
        properties: { path: window.location.pathname },
      },
      context || {}
    );
    window
      .fetch(endpoint, {
        method: "POST",
        credentials: "same-origin",
        keepalive: true,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      })
      .catch(function () {
        // Product telemetry must never interrupt the user's task.
      });
  }

  function trackedContext(element) {
    const context = {
      properties: {
        path: window.location.pathname,
        element: element.tagName.toLowerCase(),
      },
    };
    const area = cleanStaticValue(element.dataset.trackArea, 80);
    if (area) {
      context.properties.area = area;
    }
    const target = cleanStaticValue(element.dataset.trackTarget, 80);
    if (target) {
      context.properties.target = target;
    }

    const stringFields = [
      ["factoryRunId", "factory_run_id", 160],
      ["entityType", "entity_type", 120],
      ["entityId", "entity_id", 160],
      ["sku", "sku", 120],
    ];
    stringFields.forEach(function (field) {
      const value = cleanStaticValue(element.dataset[field[0]], field[2]);
      if (value) {
        context[field[1]] = value;
      }
    });

    const integerFields = [
      ["productId", "product_id"],
      ["campaignId", "campaign_id"],
      ["videoJobId", "video_job_id"],
      ["publishingTaskId", "publishing_task_id"],
    ];
    integerFields.forEach(function (field) {
      const value = positiveInteger(element.dataset[field[0]]);
      if (value) {
        context[field[1]] = value;
      }
    });
    return context;
  }

  function start() {
    if (session.isNew) {
      send("session_started");
    }
    send("page_viewed");
    document.addEventListener("click", function (event) {
      const origin = event.target;
      if (!(origin instanceof Element)) {
        return;
      }
      const tracked = origin.closest("[data-track-event]");
      if (!tracked) {
        return;
      }
      const eventName = tracked.dataset.trackEvent;
      if (clientEventNames.has(eventName)) {
        send(eventName, trackedContext(tracked));
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }
})();
