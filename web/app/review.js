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
  var tabsNode = document.getElementById("review-tabs");
  var tabVideos = document.getElementById("tab-videos");
  var tabIntake = document.getElementById("tab-intake");
  var intakePanel = document.getElementById("intake-panel");
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

  function uploadOneFile(token, file) {
    return api({
      action: "intake_upload_init",
      token: token,
      original_filename: String(file.name || "file").slice(0, 255),
      mime_type: String(file.type || ""),
      size_bytes: file.size,
      rights_confirmed: true,
      client_request_id: crypto.randomUUID(),
    }).then(function (init) {
      if (!init || init.ok !== true || !init.signed_url) {
        throw new Error((init && init.message) || "upload_init_failed");
      }
      return fetch(init.signed_url, {
        method: "PUT",
        headers: { "content-type": String(file.type || "application/octet-stream") },
        body: file,
      }).then(function (put) {
        if (!put.ok) throw new Error("upload_put_failed");
        return true;
      });
    });
  }

  function renderIntake(token, result) {
    intakePanel.replaceChildren();

    var card = document.createElement("div");
    card.className = "intake-card";
    var heading = document.createElement("h2");
    heading.textContent = "Бриф и материалы для команды";
    card.append(heading);

    var briefs = Array.isArray(result.intake_briefs)
      ? result.intake_briefs
      : [];
    briefs.forEach(function (brief) {
      var line = document.createElement("div");
      line.className = "brief-status " + String(brief.status || "");
      var label = brief.status === "accepted"
        ? "принят в работу"
        : brief.status === "returned"
          ? "возвращён"
          : "на рассмотрении";
      line.textContent = "Бриф «" + String(brief.brief_product || "")
        + "» — " + label
        + (brief.operator_comment
          ? ". Комментарий команды: " + String(brief.operator_comment)
          : "");
      card.append(line);
    });

    function fieldBlock(labelText, control) {
      var label = document.createElement("label");
      label.append(document.createTextNode(labelText), control);
      return label;
    }
    var productInput = document.createElement("input");
    productInput.type = "text";
    productInput.maxLength = 180;
    productInput.placeholder = "Например: Байкальский пробиотик для животных";
    var audienceInput = document.createElement("textarea");
    audienceInput.maxLength = 600;
    audienceInput.placeholder = "Кто покупатель: владельцы кошек и собак, которые…";
    var toneInput = document.createElement("input");
    toneInput.type = "text";
    toneInput.maxLength = 400;
    toneInput.placeholder = "Например: тёплый, заботливый, без агрессивных продаж";
    var restrictionsInput = document.createElement("textarea");
    restrictionsInput.maxLength = 800;
    restrictionsInput.placeholder = "Чего в роликах быть не должно (необязательно)";
    var wishesInput = document.createElement("textarea");
    wishesInput.maxLength = 1200;
    wishesInput.placeholder = "Пожелания: сюжеты, акценты, примеры (необязательно)";

    var fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.multiple = true;
    fileInput.accept = "image/jpeg,image/png,image/webp,video/mp4";
    var fileList = document.createElement("div");
    fileInput.addEventListener("change", function () {
      fileList.replaceChildren();
      Array.from(fileInput.files || []).forEach(function (file) {
        var row = document.createElement("div");
        row.className = "file-row";
        var nameSpan = document.createElement("span");
        nameSpan.textContent = file.name;
        var sizeSpan = document.createElement("span");
        sizeSpan.textContent = Math.ceil(file.size / 1048576) + " МБ";
        if (file.size > 52428800) {
          sizeSpan.textContent += " — больше 50 МБ, не уйдёт";
          sizeSpan.className = "err";
        }
        row.append(nameSpan, sizeSpan);
        fileList.append(row);
      });
    });

    var rightsLine = document.createElement("label");
    rightsLine.className = "option-line";
    var rightsBox = document.createElement("input");
    rightsBox.type = "checkbox";
    var rightsText = document.createElement("span");
    rightsText.textContent =
      "Подтверждаю: у меня есть права на загружаемые фото и видео "
      + "(это мой товар и мои материалы).";
    rightsLine.append(rightsBox, rightsText);

    var submitButton = document.createElement("button");
    submitButton.className = "primary";
    submitButton.type = "button";
    submitButton.style.marginTop = "14px";
    submitButton.textContent = "Отправить бриф и файлы команде";

    submitButton.addEventListener("click", function () {
      if (busy) return;
      var product = productInput.value.trim();
      var audience = audienceInput.value.trim();
      var tone = toneInput.value.trim();
      if (product.length < 2 || audience.length < 3 || tone.length < 3) {
        toast("Заполните товар, аудиторию и тон — это основа брифа.");
        return;
      }
      var files = Array.from(fileInput.files || []).filter(function (file) {
        return file.size <= 52428800;
      });
      if (files.length && !rightsBox.checked) {
        toast("Отметьте подтверждение прав на материалы.");
        return;
      }
      busy = true;
      submitButton.disabled = true;
      submitButton.textContent = "Отправляем…";
      var chain = Promise.resolve();
      files.forEach(function (file) {
        chain = chain.then(function () {
          submitButton.textContent = "Загружаем: " + file.name;
          return uploadOneFile(token, file);
        });
      });
      chain.then(function () {
        submitButton.textContent = "Отправляем бриф…";
        return api({
          action: "intake_brief",
          token: token,
          brief_product: product,
          brief_audience: audience,
          brief_tone: tone,
          brief_restrictions: restrictionsInput.value.trim() || null,
          brief_wishes: wishesInput.value.trim() || null,
          client_request_id: crypto.randomUUID(),
        });
      }).then(function (result2) {
        busy = false;
        if (result2 && result2.ok === true) {
          toast("Бриф и материалы отправлены. Команда получила уведомление.");
          load(token);
          return;
        }
        submitButton.disabled = false;
        submitButton.textContent = "Отправить бриф и файлы команде";
        toast((result2 && result2.message) || "Не получилось отправить бриф.");
      }).catch(function () {
        busy = false;
        submitButton.disabled = false;
        submitButton.textContent = "Отправить бриф и файлы команде";
        toast("Не удалось загрузить файлы. Проверьте интернет и попробуйте ещё раз.");
      });
    });

    card.append(
      fieldBlock("Товар *", productInput),
      fieldBlock("Кто покупатель *", audienceInput),
      fieldBlock("Тон роликов *", toneInput),
      fieldBlock("Ограничения", restrictionsInput),
      fieldBlock("Пожелания", wishesInput),
      fieldBlock("Фото товара и свои видео (до 50 МБ файл)", fileInput),
      fileList,
      rightsLine,
      submitButton,
    );
    var note = document.createElement("p");
    note.className = "note";
    note.textContent =
      "Материалы попадают команде на проверку; в работу их принимает оператор.";
    card.append(note);
    intakePanel.append(card);
  }

  function showTab(which) {
    tabVideos.classList.toggle("active", which === "videos");
    tabIntake.classList.toggle("active", which === "intake");
    listNode.hidden = which !== "videos";
    intakePanel.hidden = which !== "intake";
  }
  tabVideos.addEventListener("click", function () { showTab("videos"); });
  tabIntake.addEventListener("click", function () { showTab("intake"); });

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
      var allItems = Array.isArray(result.items) ? result.items : [];
      var decidedCount = allItems.filter(function (item) {
        return item.last_decision && item.last_decision.decision;
      }).length;
      subtitleNode.textContent = (result.client_label
        ? "Для: " + result.client_label
        : "")
        + (allItems.length
          ? " · решения: " + decidedCount + " из " + allItems.length
          : "");
      listNode.replaceChildren();
      var items = Array.isArray(result.items) ? result.items : [];
      var intakeOn = result.intake_enabled === true;
      if (!items.length && !intakeOn) {
        showState(
          "Роликов пока нет",
          "Команда добавит их в ближайшее время.",
        );
        return;
      }
      if (!items.length) {
        var emptyNote = document.createElement("p");
        emptyNote.className = "note";
        emptyNote.style.textAlign = "center";
        emptyNote.textContent =
          "Роликов пока нет — начните с вкладки «Материалы и бриф».";
        listNode.append(emptyNote);
      }
      if (items.length && decidedCount === items.length) {
        var allDone = document.createElement("div");
        allDone.className = "all-done";
        allDone.textContent =
          "Все ролики просмотрены — команда получила ваши решения. "
          + "Новые ролики появятся по этой же ссылке, мы сообщим.";
        listNode.append(allDone);
      }
      items.forEach(function (item) {
        listNode.append(renderItem(token, item));
      });
      if (intakeOn) {
        tabsNode.hidden = false;
        renderIntake(token, result);
        showTab(items.length ? "videos" : "intake");
      } else {
        tabsNode.hidden = true;
        intakePanel.hidden = true;
        listNode.hidden = false;
      }
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
