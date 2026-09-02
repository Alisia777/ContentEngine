/*
 * Витрина согласования (ступень 1): клиентская страница без входа.
 * Токен читается из hash-фрагмента (#t=crv1_...) и никогда не уходит в
 * query/логи. Все действия идут в edge client-review; решения идемпотентны
 * по client_request_id (crypto.randomUUID на каждый клик). DOM строится
 * только через createElement/textContent — чужие строки (комментарии,
 * названия) в innerHTML не попадают.
 */
(function () {
  "use strict";

  var CONFIG = window.CONTENTENGINE_CONFIG || {};
  var ENDPOINT = String(CONFIG.SUPABASE_URL || "").replace(/\/$/, "")
    + "/functions/v1/client-review";
  var TOKEN_PATTERN = /^crv1_[A-Za-z0-9_-]{43}$/;

  var stateNode = document.getElementById("review-state");
  var listNode = document.getElementById("review-list");
  var headerNode = document.getElementById("review-header");
  var titleNode = document.getElementById("review-title");
  var subtitleNode = document.getElementById("review-subtitle");
  var footerNode = document.getElementById("review-footer");
  var toastNode = document.getElementById("review-toast");
  var toastTimer = null;
  var busy = false;

  function readToken() {
    var hash = String(window.location.hash || "");
    var match = /[#&]t=([^&]+)/.exec(hash);
    var token = match ? decodeURIComponent(match[1]) : "";
    return TOKEN_PATTERN.test(token) ? token : "";
  }

  function toast(message) {
    toastNode.textContent = message;
    toastNode.classList.add("show");
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () {
      toastNode.classList.remove("show");
    }, 4000);
  }

  function showState(title, detail) {
    listNode.replaceChildren();
    headerNode.hidden = true;
    footerNode.hidden = true;
    stateNode.replaceChildren();
    var strong = document.createElement("strong");
    strong.textContent = title;
    stateNode.append(strong, document.createTextNode(detail || ""));
    stateNode.style.display = "block";
  }

  function api(payload) {
    return fetch(ENDPOINT, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        apikey: String(CONFIG.SUPABASE_PUBLISHABLE_KEY || ""),
      },
      body: JSON.stringify(payload),
    }).then(function (response) {
      return response.json().catch(function () {
        return { ok: false, code: "invalid_response" };
      });
    });
  }

  function decisionLabel(decision) {
    if (decision === "accepted") return "Принят вами";
    if (decision === "returned") return "Возвращён на доработку";
    if (decision === "publish_requested") return "Передан в публикацию";
    return "";
  }

  function renderItem(token, item) {
    var card = document.createElement("article");
    card.className = "card";

    if (item.video_url) {
      var video = document.createElement("video");
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      video.src = String(item.video_url);
      video.addEventListener("error", function () {
        toast("Срок видео-ссылки истёк — обновите страницу.");
      });
      card.append(video);
    }

    var body = document.createElement("div");
    body.className = "body";

    var title = document.createElement("h2");
    title.textContent = String(item.title || "Ролик");
    body.append(title);

    if (item.duration_seconds) {
      var meta = document.createElement("p");
      meta.className = "meta";
      meta.textContent = "Длительность: " + item.duration_seconds + " сек";
      body.append(meta);
    }

    var lastDecision = item.last_decision && item.last_decision.decision;
    if (item.published && item.published.final_url) {
      var published = document.createElement("span");
      published.className = "status published";
      published.textContent = "Опубликован";
      body.append(published);
      var link = document.createElement("p");
      link.className = "note";
      var anchor = document.createElement("a");
      anchor.href = String(item.published.final_url);
      anchor.rel = "noopener noreferrer";
      anchor.target = "_blank";
      anchor.textContent = "Открыть публикацию";
      anchor.style.color = "var(--accent)";
      link.append(anchor);
      body.append(link);
    } else if (lastDecision) {
      var status = document.createElement("span");
      status.className = "status " + lastDecision;
      status.textContent = decisionLabel(lastDecision);
      body.append(status);
      if (lastDecision === "returned" && item.last_decision.comment) {
        var comment = document.createElement("p");
        comment.className = "note";
        comment.textContent = "Ваш комментарий: "
          + String(item.last_decision.comment);
        body.append(comment);
      }
    }

    var actions = document.createElement("div");
    actions.className = "actions";
    var acceptButton = document.createElement("button");
    acceptButton.className = "primary";
    acceptButton.type = "button";
    acceptButton.textContent = "Принять";
    var returnButton = document.createElement("button");
    returnButton.className = "ghost";
    returnButton.type = "button";
    returnButton.textContent = "Вернуть";
    var publishButton = document.createElement("button");
    publishButton.className = "accent";
    publishButton.type = "button";
    publishButton.textContent = "Опубликовать";
    actions.append(acceptButton, returnButton, publishButton);

    var returnBox = document.createElement("div");
    returnBox.className = "return-box";
    var textarea = document.createElement("textarea");
    textarea.maxLength = 2000;
    textarea.placeholder =
      "Что именно доработать? Например: «замените первую фразу, банка должна быть в кадре с 3-й секунды».";
    var sendReturn = document.createElement("button");
    sendReturn.type = "button";
    sendReturn.textContent = "Отправить на доработку";
    sendReturn.style.marginTop = "8px";
    returnBox.append(textarea, sendReturn);

    function sendDecision(decision, comment) {
      if (busy) return;
      busy = true;
      acceptButton.disabled = true;
      returnButton.disabled = true;
      publishButton.disabled = true;
      sendReturn.disabled = true;
      api({
        action: "decide",
        token: token,
        item_id: String(item.item_id || ""),
        decision: decision,
        comment: comment || null,
        client_request_id: crypto.randomUUID(),
      }).then(function (result) {
        busy = false;
        if (result && result.ok === true) {
          toast(
            decision === "accepted"
              ? "Ролик принят. Спасибо!"
              : decision === "returned"
                ? "Отправили команде на доработку."
                : "Передали команде запрос на публикацию.",
          );
          load(token);
          return;
        }
        acceptButton.disabled = false;
        returnButton.disabled = false;
        publishButton.disabled = false;
        sendReturn.disabled = false;
        toast(
          (result && result.message)
            || "Не получилось сохранить решение. Попробуйте ещё раз.",
        );
      });
    }

    acceptButton.addEventListener("click", function () {
      sendDecision("accepted", null);
    });
    publishButton.addEventListener("click", function () {
      sendDecision("publish_requested", null);
    });
    returnButton.addEventListener("click", function () {
      returnBox.classList.toggle("open");
      if (returnBox.classList.contains("open")) textarea.focus();
    });
    sendReturn.addEventListener("click", function () {
      var comment = textarea.value.trim();
      if (comment.length < 3) {
        toast("Добавьте комментарий: что именно доработать.");
        textarea.focus();
        return;
      }
      sendDecision("returned", comment);
    });

    var hint = document.createElement("p");
    hint.className = "note";
    hint.textContent =
      "«Опубликовать» передаёт ролик команде — публикацию с маркировкой выполняет оператор.";

    body.append(actions, returnBox, hint);
    card.append(body);
    return card;
  }

  function load(token) {
    api({ action: "view", token: token }).then(function (result) {
      if (!result || result.ok !== true) {
        if (result && result.code === "client_review_rate_limited") {
          showState(
            "Слишком много запросов",
            "Подождите немного и обновите страницу.",
          );
        } else {
          showState(
            "Ссылка недействительна или устарела",
            "Запросите новую ссылку у вашей команды.",
          );
        }
        return;
      }
      stateNode.style.display = "none";
      headerNode.hidden = false;
      footerNode.hidden = false;
      titleNode.textContent = result.campaign_name
        ? "Ролики: " + result.campaign_name
        : "Согласование роликов";
      subtitleNode.textContent = result.client_label
        ? "Для: " + result.client_label
        : "";
      listNode.replaceChildren();
      var items = Array.isArray(result.items) ? result.items : [];
      if (!items.length) {
        showState(
          "Роликов пока нет",
          "Команда добавит их в ближайшее время.",
        );
        return;
      }
      items.forEach(function (item) {
        listNode.append(renderItem(token, item));
      });
    }).catch(function () {
      showState(
        "Не удалось загрузить",
        "Проверьте интернет и обновите страницу.",
      );
    });
  }

  var token = readToken();
  if (!token) {
    showState(
      "Ссылка недействительна",
      "Откройте ссылку из сообщения вашей команды целиком.",
    );
    return;
  }
  load(token);
})();
