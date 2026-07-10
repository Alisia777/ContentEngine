(() => {
  const form = document.querySelector("[data-recipe-form]");
  if (form) {
    const counter = document.querySelector("[data-reference-counter]");
    const checkboxes = [...form.querySelectorAll("[data-reference-input]")];
    const files = [...form.querySelectorAll("[data-reference-file]")];
    const referenceCount = () => {
      const selected = checkboxes.filter((input) => input.checked).length;
      const uploaded = files.filter((input) => input.files && input.files.length).length;
      return selected + uploaded;
    };
    const updateReferences = () => {
      const total = referenceCount();
      if (counter) {
        counter.textContent = `${total} / ${total < 3 ? 3 : 4}`;
        counter.classList.toggle("is-ready", total >= 3 && total <= 4);
        counter.classList.toggle("is-blocked", total < 3 || total > 4);
      }
    };
    [...checkboxes, ...files].forEach((input) => input.addEventListener("change", updateReferences));
    updateReferences();

    const duration = form.querySelector("[data-duration]");
    const ratio = form.querySelector("[data-ratio]");
    const estimate = form.querySelector("[data-credit-estimate]");
    const updateCredits = () => {
      const seconds = Math.min(15, Math.max(4, Number(duration?.value || 15)));
      const pro = ratio?.value === "1080:1920";
      const credits = (pro ? 208 : 192) + Math.max(0, seconds - 4) * (pro ? 40 : 36);
      if (estimate) estimate.textContent = `${credits} credits`;
    };
    duration?.addEventListener("input", updateCredits);
    ratio?.addEventListener("change", updateCredits);
    updateCredits();

    const audio = form.querySelector('[name="audio_enabled"]');
    const spoken = form.querySelector('[name="spoken_message"]');
    const updateAudioRequirement = () => {
      if (!spoken) return;
      spoken.required = Boolean(audio?.checked);
      spoken.setAttribute("aria-required", spoken.required ? "true" : "false");
    };
    audio?.addEventListener("change", updateAudioRequirement);
    updateAudioRequirement();

    form.addEventListener("submit", (event) => {
      const total = referenceCount();
      if (total < 3 || total > 4) {
        event.preventDefault();
        counter?.scrollIntoView({ behavior: "smooth", block: "center" });
        counter?.focus?.();
        window.alert("Выберите или загрузите ровно 3 или 4 фото одного варианта товара.");
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
