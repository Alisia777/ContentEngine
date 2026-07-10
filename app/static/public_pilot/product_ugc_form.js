(() => {
  const form = document.querySelector("[data-recipe-form]");
  if (form) {
    const counter = document.querySelector("[data-reference-counter]");
    const checkboxes = [...form.querySelectorAll("[data-reference-input]")];
    const files = [...form.querySelectorAll("[data-reference-file]")];
    const primaryInputs = [...form.querySelectorAll("[data-primary-input]")];
    const interactionInputs = [...form.querySelectorAll('[name="interaction_mode"]')];
    const audioInputs = [...form.querySelectorAll('[name="audio_enabled"]')];
    const providerSlot = form.querySelector('[name="provider_image_slot"]');
    const scaleType = form.querySelector("[data-scale-reference-type]");
    const proofType = form.querySelector("[data-proof-reference-type]");
    const characterFile = form.querySelector("[data-character-file]");
    const spoken = form.querySelector('[name="spoken_message"]');
    const duration = form.querySelector("[data-duration]");
    const ratio = form.querySelector("[data-ratio]");
    const estimate = form.querySelector("[data-credit-estimate]");
    const readiness = form.querySelector("[data-recipe-readiness]");
    const score = form.querySelector("[data-contract-score]");
    const submit = form.querySelector("[data-recipe-submit]");
    const characterPreview = form.querySelector("[data-character-preview]");
    const productPreview = form.querySelector("[data-product-preview]");
    const previewUrls = new WeakMap();

    const checkedValue = (inputs) => inputs.find((input) => input.checked)?.value;
    const hasFile = (input) => Boolean(input?.files?.length);
    const objectUrlFor = (input) => {
      if (!hasFile(input)) return "";
      const file = input.files[0];
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      const cached = previewUrls.get(input);
      if (cached?.key === key) return cached.url;
      if (cached?.url) URL.revokeObjectURL(cached.url);
      const url = URL.createObjectURL(file);
      previewUrls.set(input, { key, url });
      return url;
    };

    const referenceCount = () => (
      checkboxes.filter((input) => input.checked).length + files.filter(hasFile).length
    );

    const setPreview = (container, source) => {
      if (!container) return;
      const image = container.querySelector("img");
      const placeholder = container.querySelector(".recipe-live-preview-placeholder");
      if (source) {
        image.src = source;
        image.hidden = false;
        placeholder.hidden = true;
      } else {
        image.removeAttribute("src");
        image.hidden = true;
        placeholder.hidden = false;
      }
    };

    const updateCredits = () => {
      const seconds = Math.min(15, Math.max(4, Number(duration?.value || 15)));
      const pro = ratio?.value === "1080:1920";
      const credits = (pro ? 208 : 192) + Math.max(0, seconds - 4) * (pro ? 40 : 36);
      if (estimate) estimate.textContent = `${credits} credits`;
    };

    const updateAudioRequirement = () => {
      if (!spoken) return;
      spoken.required = checkedValue(audioInputs) === "true";
      spoken.setAttribute("aria-required", spoken.required ? "true" : "false");
      spoken.placeholder = spoken.required
        ? "Точный русский текст или смысл реплики"
        : "Необязательно: видео будет без сгенерированного аудио";
    };

    const syncReferenceRoles = () => {
      const scaleFile = files.find((input) => input.dataset.referenceSlot === "scale");
      const proofFile = files.find((input) => input.dataset.referenceSlot === "proof");
      if (scaleFile && scaleType) scaleFile.dataset.referenceRole = scaleType.value;
      if (proofFile && proofType) proofFile.dataset.referenceRole = proofType.value;
    };

    const selectedRoles = () => {
      syncReferenceRoles();
      return [
        ...checkboxes.filter((input) => input.checked).map((input) => input.dataset.referenceRole),
        ...files.filter(hasFile).map((input) => input.dataset.referenceRole),
      ].filter(Boolean);
    };

    const syncPrimarySelection = () => {
      primaryInputs.forEach((radio) => {
        const checkbox = radio.closest(".recipe-asset-option")?.querySelector("[data-reference-input]");
        if (!checkbox) return;
        radio.disabled = !checkbox.checked;
        if (radio.disabled) radio.checked = false;
      });
    };

    const providerImageSource = () => {
      const selectedPrimary = primaryInputs.find((input) => input.checked && !input.disabled);
      if (selectedPrimary?.dataset.primaryPreview) return selectedPrimary.dataset.primaryPreview;
      const upload = files.find((input) => input.dataset.referenceSlot === providerSlot?.value);
      return objectUrlFor(upload);
    };

    const updatePreviews = () => {
      setPreview(characterPreview, objectUrlFor(characterFile));
      setPreview(productPreview, providerImageSource());
    };

    const actionText = () => (
      `${form.querySelector('[name="product_action"]')?.value || ""} ${form.querySelector('[name="proof_moment"]')?.value || ""}`
    ).toLocaleLowerCase("ru");

    const positiveActionText = () => actionText().replace(
      /\bне\s+(?:проб[а-яёa-z-]*|кус[а-яёa-z-]*|ест[а-яёa-z-]*|съед[а-яёa-z-]*|разрез[а-яёa-z-]*|открыва[а-яёa-z-]*|нанос[а-яёa-z-]*|апплик[а-яёa-z-]*|пример[а-яёa-z-]*|надева[а-яёa-z-]*|носит[а-яёa-z-]*|примен[а-яёa-z-]*|использ[а-яёa-z-]*|включ[а-яёa-z-]*|очища[а-яёa-z-]*)/gi,
      "",
    );

    const actionImpliesUse = () => {
      const keywords = {
        food_snack: ["проб", "куса", "ест ", "съед", "вкус", "разрез", "открыва", "bite", "taste", "eat"],
        cosmetic: ["нанос", "апплик", "свотч", "на губ", "на кож", "apply", "swatch"],
        apparel: ["пример", "надева", "носит", "посадк", "try on", "wear"],
        household: ["примен", "использ", "включ", "работ", "очища", "use", "operate"],
        general: ["примен", "использ", "демонстрирует работу", "включ", "use", "operate"],
      }[form.dataset.productProfile] || [];
      const text = positiveActionText();
      return keywords.some((token) => text.includes(token));
    };

    const foodBiteRequested = () => {
      if (form.dataset.productProfile !== "food_snack") return false;
      const text = positiveActionText().replace(
        /\bне\s+(?:надкус[а-яёa-z-]*|кус[а-яёa-z-]*|жев[а-яёa-z-]*|жу[а-яёa-z-]*|ест[а-яёa-z-]*|съед[а-яёa-z-]*|проб[а-яёa-z-]*|поднос[а-яёa-z-]*\s+(?:к|ко)\s+рту)/gi,
        "",
      );
      return ["надкус", "куса", "укус", "жует", "жуёт", "ест ", "съед", "пробует", "у рта", "ко рту", "bite", "chew", "eats", "taste"].some((token) => text.includes(token));
    };

    const gateState = () => {
      syncPrimarySelection();
      const roles = selectedRoles();
      const mode = checkedValue(interactionInputs) || "presentation";
      const useRequested = mode === "use" || actionImpliesUse();
      const total = referenceCount();
      const requiredCount = useRequested ? 4 : 3;
      const identity = Boolean(
        form.querySelector("[data-variant-input]")?.value.trim()
        && form.querySelector('[name="exact_variant_confirmed"]')?.checked
      );
      const baseline = [
        ["front_packshot", "front_view"],
        ["angled_wrapper", "angled_product", "back_view"],
        ["wrapper_in_hand", "wrapper_on_table", "product_in_hand", "product_on_surface", "scale_context"],
      ].every((group) => group.some((role) => roles.includes(role)));
      const references = total >= requiredCount && total <= 4 && baseline;
      const provider = Boolean(
        primaryInputs.some((input) => input.checked && !input.disabled) || providerImageSource()
      );
      const character = Boolean(
        hasFile(characterFile)
        && form.querySelector('[name="likeness_consent"]')?.checked
        && form.querySelector('[name="character_product_free_confirmed"]')?.checked
      );
      const profileProof = {
        food_snack: ["whole_unwrapped_product", "cutaway_product", "bitten_product", "wrapper_plus_product"],
        cosmetic: ["application_demo", "application_context", "application_area", "texture_swatch"],
        apparel: ["on_body", "movement_reference"],
        household: ["application_demo", "application_context", "result_context"],
        general: ["application_demo", "application_context", "result_context"],
      }[form.dataset.productProfile] || ["application_context"];
      const useProof = !useRequested || profileProof.some((role) => roles.includes(role));
      const biteProof = !foodBiteRequested() || roles.includes("bitten_product");
      const action = useProof && biteProof;
      const requiredBrief = [...form.querySelectorAll("[data-brief-required]")].every((input) => input.value.trim());
      const audioReady = checkedValue(audioInputs) === "false" || Boolean(spoken?.value.trim());
      const brief = requiredBrief && audioReady;
      const seconds = Number(duration?.value || 0);
      const output = seconds >= 4
        && seconds <= 15
        && ["720:1280", "1080:1920"].includes(ratio?.value)
        && Boolean(checkedValue(audioInputs));
      return { identity, references, provider, character, action, brief, output, total, requiredCount };
    };

    const updateContract = () => {
      updateAudioRequirement();
      updateCredits();
      syncReferenceRoles();
      const state = gateState();
      const keys = ["identity", "references", "provider", "character", "action", "brief", "output"];
      const readyCount = keys.filter((key) => state[key]).length;
      keys.forEach((key) => {
        form.querySelector(`[data-contract-gate="${key}"]`)?.classList.toggle("is-ready", state[key]);
      });
      if (counter) {
        counter.textContent = `${state.total} / ${state.requiredCount}${state.requiredCount === 3 ? "–4" : ""}`;
        counter.classList.toggle("is-ready", state.references);
        counter.classList.toggle("is-blocked", !state.references);
      }
      if (score) score.textContent = `${readyCount} / ${keys.length}`;
      readiness?.classList.toggle("is-ready", readyCount === keys.length);
      if (submit) {
        submit.disabled = readyCount !== keys.length;
        submit.setAttribute("aria-disabled", submit.disabled ? "true" : "false");
      }
      updatePreviews();
      return readyCount === keys.length;
    };

    primaryInputs.filter((radio) => radio.checked).forEach((radio) => {
      const checkbox = radio.closest(".recipe-asset-option")?.querySelector("[data-reference-input]");
      if (checkbox) checkbox.checked = true;
    });
    primaryInputs.forEach((radio) => {
      radio.addEventListener("change", () => {
        const checkbox = radio.closest(".recipe-asset-option")?.querySelector("[data-reference-input]");
        if (radio.checked && checkbox) checkbox.checked = true;
        updateContract();
      });
    });
    checkboxes.forEach((checkbox) => {
      checkbox.addEventListener("change", () => {
        if (!checkbox.checked) {
          const radio = checkbox.closest(".recipe-asset-option")?.querySelector("[data-primary-input]");
          if (radio) radio.checked = false;
        }
        updateContract();
      });
    });
    form.querySelectorAll("input, select, textarea").forEach((input) => {
      if (!input.matches("[data-reference-input], [data-primary-input]")) {
        input.addEventListener("change", updateContract);
      }
      if (input.matches("input:not([type=file]):not([type=checkbox]):not([type=radio]), textarea")) {
        input.addEventListener("input", updateContract);
      }
    });
    updateContract();

    form.addEventListener("submit", (event) => {
      if (!updateContract()) {
        event.preventDefault();
        readiness?.scrollIntoView({ behavior: "smooth", block: "start" });
        window.alert("Сначала закройте все 7 обязательных проверок ТЗ. Runway пока не будет вызван.");
        return;
      }
      const submitter = event.submitter;
      if (submitter) {
        submitter.disabled = true;
        submitter.textContent = "Проверяем ТЗ...";
      }
    });
  }

  const paidForm = document.querySelector("[data-paid-run-form]");
  paidForm?.addEventListener("submit", (event) => {
    const submitter = event.submitter;
    if (submitter) {
      submitter.disabled = true;
      submitter.textContent = "Отправляем один task...";
    }
  });

  const poll = document.querySelector("[data-recipe-poll]");
  if (poll) {
    const draftId = poll.dataset.draftId;
    const statusNode = document.querySelector("[data-recipe-run-status]");
    const active = new Set(["provider_launching", "provider_submitted"]);
    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`/api/runway-recipes/product-ugc/${draftId}`, {
          headers: { Accept: "application/json" },
          cache: "no-store",
        });
        if (!response.ok) return;
        const payload = await response.json();
        if (statusNode) statusNode.textContent = payload.provider_status || payload.status;
        if (!active.has(payload.status)) {
          window.clearInterval(timer);
          window.location.reload();
        }
      } catch (_error) {
        // Keep the current page usable; a later poll can recover after a short network interruption.
      }
    }, 4000);
  }
})();
