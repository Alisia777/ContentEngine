(() => {
  const form = document.querySelector("[data-recipe-form]");
  if (!form) return;

  const counter = document.querySelector("[data-reference-counter]");
  const checkboxes = [...form.querySelectorAll("[data-reference-input]")];
  const files = [...form.querySelectorAll("[data-reference-file]")];
  const updateReferences = () => {
    const selected = checkboxes.filter((input) => input.checked).length;
    const uploaded = files.filter((input) => input.files && input.files.length).length;
    const total = selected + uploaded;
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
})();
