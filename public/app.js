const state = {
  plan: null,
  shoppingList: null
};

const dom = {
  planText: document.querySelector("#plan-text"),
  planFile: document.querySelector("#plan-file"),
  parserMode: document.querySelector("#parser-mode"),
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
  statusBadge: document.querySelector("#status-badge"),
  llmHint: document.querySelector("#llm-hint"),
  parseSummary: document.querySelector("#parse-summary")
};

bootstrap();

async function bootstrap() {
  bindEvents();
  const response = await fetch("/api/state");
  const data = await response.json();
  applyCapabilities(data.capabilities);

  if (data.lastPlan) {
    state.plan = data.lastPlan;
    renderPlan();
    renderPlanSummary();
    setStatus("Plano carregado", false);
  } else {
    renderPlanSummary();
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
    payload.parserMode = dom.parserMode.value;

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
    renderPlanSummary();
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
    renderPlanSummary();
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
    renderPlanSummary();
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

function applyCapabilities(capabilities) {
  const llm = capabilities?.llm || {};
  const llmOption = dom.parserMode.querySelector("option[value='llm']");

  if (llmOption) {
    llmOption.disabled = !llm.configured;
  }

  if (!llm.configured && dom.parserMode.value === "llm") {
    dom.parserMode.value = "auto";
  }

  if (llm.configured) {
    dom.llmHint.textContent = `Gemini configurado (${llm.model}). Automatico usa parser local como base e chama o LLM so nas refeicoes complexas.`;
  } else {
    dom.llmHint.textContent = "Automatico usa parser local ate configurar GEMINI_API_KEY.";
  }
}

function renderPlanSummary() {
  if (!state.plan) {
    dom.parseSummary.textContent = "PDF usa extracao best-effort nesta versao. Se vier ruim, cole o texto manualmente.";
    return;
  }

  const parts = [];
  parts.push(state.plan.parseStrategy === "llm:gemini" ? "Interpretado com Gemini." : "Interpretado com parser local.");

  const metadata = state.plan.parseMetadata || {};
  if (metadata.totalDurationMs) {
    parts.push(`Tempo total: ${formatNumber(metadata.totalDurationMs)} ms.`);
  }
  if (state.plan.parseStrategy === "llm:gemini" && metadata.llmDurationMs) {
    parts.push(`Gemini: ${formatNumber(metadata.llmDurationMs)} ms.`);
  }
  if (metadata.llmModel) {
    parts.push(`Modelo: ${metadata.llmModel}.`);
  }
  if (metadata.thinkingBudget !== undefined) {
    parts.push(`Thinking budget: ${formatNumber(metadata.thinkingBudget)}.`);
  }
  if (metadata.preprocessedChars) {
    parts.push(`Texto enviado ao LLM: ${formatNumber(metadata.preprocessedChars)} chars.`);
  }
  if (metadata.sourceChars) {
    parts.push(`Fonte original: ${formatNumber(metadata.sourceChars)} chars.`);
  }
  if (state.plan.parseStrategy === "llm:gemini" && metadata.llmAttempts > 1) {
    parts.push(`Tentativas Gemini: ${formatNumber(metadata.llmAttempts)}.`);
  }
  if (metadata.usedFallbackModel) {
    parts.push("Fallback para modelo mais forte ativado.");
  }
  if (metadata.llmSkipped) {
    parts.push("LLM pulado porque o parser local resolveu as refeicoes sem ambiguidade relevante.");
  }

  if (Array.isArray(state.plan.parseWarnings) && state.plan.parseWarnings.length) {
    parts.push(state.plan.parseWarnings.join(" "));
  }

  dom.parseSummary.textContent = parts.join(" ");
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
