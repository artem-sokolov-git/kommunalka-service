// Live consumption and bill preview on the readings page. The form works without it.
const form = document.querySelector("[data-readings]");

const parse = (text) => {
  const cleaned = text.replace(/[\s ]/g, "").replace(",", ".");
  return cleaned === "" ? null : Number(cleaned);
};
const money = (value) =>
  value.toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const quantity = (value) => value.toLocaleString("ru-RU", { maximumFractionDigits: 3 });

function meterState(input) {
  const value = parse(input.value);
  const { last, price, unit } = input.dataset;
  if (value === null) return { missing: true };
  if (Number.isNaN(value)) return { error: "Это не число" };
  if (last === "") return { baseline: true };
  if (value < Number(last)) {
    return { error: `Меньше прошлого показания (${quantity(Number(last))}). Проверьте цифры.` };
  }
  const used = value - Number(last);
  const amount = price === "" ? null : Math.round(used * Number(price) * 100) / 100;
  const priced = price === "" ? "" : ` × ${money(Number(price))}`;
  return {
    used: `· ${quantity(used)} ${unit}${priced}`,
    amount,
    hint: `Расход ${quantity(used)} ${unit}` + (amount === null ? "" : ` → ${money(amount)} грн`),
  };
}

function update() {
  let total = 0;
  let complete = true;
  for (const input of form.querySelectorAll("[data-meter]")) {
    const id = input.dataset.meter;
    const hint = document.getElementById(`hint-${id}`);
    const used = form.querySelector(`[data-qty="${id}"]`);
    const amount = form.querySelector(`[data-amount="${id}"]`);
    const state = meterState(input);
    if (state.error) input.setAttribute("aria-invalid", "true");
    else input.removeAttribute("aria-invalid");
    hint.className = state.error ? "hint bad" : state.hint ? "hint good" : "hint";
    if (state.error || state.hint) hint.textContent = state.error || state.hint;
    else if (!state.baseline) hint.textContent = hint.dataset.default;
    if (used && state.used) used.textContent = state.used;
    if (amount) amount.textContent = state.amount == null ? "—" : money(state.amount);
    if (state.missing || state.error) complete = false;
    total += state.amount ?? 0;
  }
  for (const input of form.querySelectorAll("[data-fixed]")) {
    const value = parse(input.value);
    if (value === null || Number.isNaN(value)) complete = false;
    else total += value;
  }
  const sum = form.querySelector("[data-total]");
  if (sum) sum.textContent = complete ? money(total) : "—";
}

if (form) {
  form.addEventListener("input", update);
  update();
}
