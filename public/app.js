const state = {
  plan: null,
  shoppingList: null
};

const dom = {
  planText: document.querySelector("#plan-text"),
  planFile: document.querySelector("#plan-file"),
  parseButton: document.querySelector("#parse-button"),
  saveReviewButton: document.querySelector("#save-review-button"),
  generateButton: document.querySelector("#generate-button"),
  addItemButton: document.querySelector("#add-item-button"),
  reviewEmpty: document.querySelector("#review-empty"),
  reviewTableWrapper: document.querySelector("#review-table-wrapper"),
  reviewBody: document.querySelector("#review-body"),
  shoppingEmpty: document.querySelector("#shopping-empty"),
  shoppingList: document.querySelector("#shopping-list"),
  rowTemplate: document.querySelector("#row-template"),
  statusBadge: document.querySelector("#status-badge")
};

bootstrap();

async function bootstrap() {
  bindEvents();
  const response = await fetch("/api/state");
  const data = await response.json();

  if (data.lastPlan) {
    state.plan = data.lastPlan;
    renderPlan();
    setStatus("Plano carregado", false);
  }
}

function bindEvents() {
  dom.parseButton.addEventListener("click", onParse);
  dom.saveReviewButton.addEventListener("click", onSaveReview);
  dom.generateButton.addEventListener("click", onGenerateShoppingList);
  dom.addItemButton.addEventListener("click", () => {
    ensurePlan();
    state.plan.items.push(createEmptyItem());
    renderPlan();
  });
}

async function onParse() {
  try {
    setStatus("Extraindo plano...", true);
    const payload = {
      text: dom.planText.value.trim()
    };

    const file = dom.planFile.files[0];
    if (file) {
      const content = await fileToBase64(file);
      payload.fileName = file.name;
      payload.mimeType = file.type;
      payload.fileContentBase64 = content;
    }

    const response = await fetch("/api/plan/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Falha ao interpretar o plano.");
    }

    state.plan = data.plan;
    state.shoppingList = null;
    renderPlan();
    renderShoppingList([]);
    setStatus("Plano extraido. Revise os itens.", false);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function onSaveReview() {
  try {
    ensurePlan();
    syncInputsToState();
    setStatus("Salvando revisao...", true);
    const response = await fetch("/api/plan/review", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: state.plan })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Falha ao salvar revisao.");
    }

    state.plan = data.plan;
    renderPlan();
    setStatus("Revisao salva.", false);
  } catch (error) {
    setStatus(error.message, true);
  }
}

async function onGenerateShoppingList() {
  try {
    ensurePlan();
    syncInputsToState();
    setStatus("Gerando lista semanal...", true);
    const response = await fetch("/api/shopping-list", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan: state.plan })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Falha ao gerar lista.");
    }

    state.plan = data.plan;
    state.shoppingList = data.shoppingList;
    renderPlan();
    renderShoppingList(data.shoppingList);
    setStatus("Lista semanal pronta.", false);
  } catch (error) {
    setStatus(error.message, true);
  }
}

function renderPlan() {
  const items = state.plan?.items || [];
  dom.reviewBody.innerHTML = "";
  dom.reviewEmpty.classList.toggle("hidden", items.length > 0);
  dom.reviewTableWrapper.classList.toggle("hidden", items.length === 0);

  items.forEach((item, index) => {
    const row = dom.rowTemplate.content.firstElementChild.cloneNode(true);
    row.dataset.index = index;

    for (const field of row.querySelectorAll("[data-field]")) {
      field.value = item[field.dataset.field] ?? "";
    }

    row.querySelector("[data-action='remove']").addEventListener("click", () => {
      state.plan.items.splice(index, 1);
      renderPlan();
    });

    dom.reviewBody.appendChild(row);
  });
}

function renderShoppingList(items) {
  dom.shoppingList.innerHTML = "";
  dom.shoppingEmpty.classList.toggle("hidden", items.length > 0);

  items.forEach((item) => {
    const card = document.createElement("article");
    card.className = `shopping-card ${item.status === "missing_package" ? "missing" : ""}`;

    if (item.status === "missing_package") {
      card.innerHTML = `
        <h3>${capitalize(item.normalizedFood)}</h3>
        <p>Necessidade semanal: ${formatNumber(item.weeklyQuantity)} ${displayUnit(item.baseUnit)}</p>
        <p>Sem embalagem conhecida no catalogo atual. Edite manualmente em uma proxima iteracao.</p>
      `;
    } else {
      const packages = item.recommendation.packages
        .map((pkg) => `${pkg.count}x ${formatNumber(pkg.quantity)} ${displayUnit(pkg.unit)} (${pkg.packageType})`)
        .join(", ");

      card.innerHTML = `
        <h3>${capitalize(item.normalizedFood)}</h3>
        <p>Necessidade semanal: ${formatNumber(item.weeklyQuantity)} ${displayUnit(item.baseUnit)}</p>
        <p>Compra sugerida: ${packages}</p>
        <p>Sobra estimada: ${formatNumber(item.overage)} ${displayUnit(item.baseUnit)}</p>
      `;
    }

    dom.shoppingList.appendChild(card);
  });
}

function syncInputsToState() {
  const rows = Array.from(dom.reviewBody.querySelectorAll("tr"));
  state.plan.items = rows.map((row, index) => {
    const current = state.plan.items[index];
    const next = { ...current };
    row.querySelectorAll("[data-field]").forEach((field) => {
      const key = field.dataset.field;
      next[key] = ["quantity", "frequencyPerWeek"].includes(key) ? Number(field.value) : field.value;
    });
    return next;
  });
}

function createEmptyItem() {
  return {
    id: Math.random().toString(36).slice(2, 10),
    mealLabel: "Plano",
    originalText: "",
    originalFood: "",
    normalizedFood: "",
    quantity: 1,
    unit: "unit",
    frequencyPerWeek: 7,
    notes: ""
  };
}

function ensurePlan() {
  if (!state.plan) {
    throw new Error("Insira um plano primeiro.");
  }
}

function setStatus(message, isPending) {
  dom.statusBadge.textContent = message;
  dom.statusBadge.classList.toggle("muted", !isPending);
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const [, payload] = String(reader.result).split(",");
      resolve(payload);
    };
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function formatNumber(value) {
  return Number(value).toLocaleString("pt-BR", { maximumFractionDigits: 2 });
}

function displayUnit(unit) {
  if (unit === "unit") {
    return "un";
  }
  return unit;
}

function capitalize(value) {
  return value.charAt(0).toUpperCase() + value.slice(1);
}
