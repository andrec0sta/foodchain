const http = require("http");
const fs = require("fs");
const path = require("path");
const os = require("os");
const { spawnSync } = require("child_process");
const { parsePlan } = require("./src/domain/parser");
const { normalizeFoodName, normalizeUnit, toBaseUnit } = require("./src/domain/normalization");
const { BASE_PACKAGE_CATALOG } = require("./src/domain/catalog");
const { generateWeeklyNeeds, resolvePackages } = require("./src/domain/packaging");
const { loadState, savePlan, savePackageOverrides } = require("./src/domain/storage");

const PUBLIC_DIR = path.join(__dirname, "public");
const state = loadState();

const server = http.createServer(async (req, res) => {
  try {
    if (req.url === "/api/state" && req.method === "GET") {
      return sendJson(res, 200, state);
    }

    if (req.url === "/api/catalog" && req.method === "GET") {
      return sendJson(res, 200, { catalog: BASE_PACKAGE_CATALOG, overrides: state.packageOverrides });
    }

    if (req.url === "/api/plan/parse" && req.method === "POST") {
      const body = await readJsonBody(req);
      const planText = await resolvePlanText(body);
      const parsed = parsePlan(planText);
      savePlan(parsed);
      state.lastPlan = parsed;
      return sendJson(res, 200, { plan: parsed });
    }

    if (req.url === "/api/plan/review" && req.method === "POST") {
      const body = await readJsonBody(req);
      const reviewedPlan = normalizeReviewedPlan(body.plan);
      reviewedPlan.status = "reviewed";
      savePlan(reviewedPlan);
      state.lastPlan = reviewedPlan;
      return sendJson(res, 200, { plan: reviewedPlan });
    }

    if (req.url === "/api/shopping-list" && req.method === "POST") {
      const body = await readJsonBody(req);
      if (body.packageOverrides) {
        state.packageOverrides = body.packageOverrides;
        savePackageOverrides(state.packageOverrides);
      }

      const reviewedPlan = normalizeReviewedPlan(body.plan);
      const weeklyNeeds = generateWeeklyNeeds(reviewedPlan.items);
      const shoppingList = resolvePackages(weeklyNeeds, state.packageOverrides);
      const response = {
        plan: reviewedPlan,
        weeklyNeeds,
        shoppingList
      };
      savePlan(reviewedPlan);
      state.lastPlan = reviewedPlan;
      return sendJson(res, 200, response);
    }

    return serveStatic(req, res);
  } catch (error) {
    return sendJson(res, 500, {
      error: error.message || "Erro interno."
    });
  }
});

const PORT = process.env.PORT || 3000;
const HOST = process.env.HOST || "127.0.0.1";
server.listen(PORT, HOST, () => {
  console.log(`Diet Shopping Assistant running at http://${HOST}:${PORT}`);
});

function sendJson(res, statusCode, payload) {
  res.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store"
  });
  res.end(JSON.stringify(payload));
}

function serveStatic(req, res) {
  const safePath = req.url === "/" ? "/index.html" : req.url;
  const filePath = path.join(PUBLIC_DIR, safePath);

  if (!filePath.startsWith(PUBLIC_DIR) || !fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
    res.writeHead(404);
    res.end("Not found");
    return;
  }

  const ext = path.extname(filePath);
  const contentType = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8"
  }[ext] || "application/octet-stream";

  res.writeHead(200, { "Content-Type": contentType });
  fs.createReadStream(filePath).pipe(res);
}

function readJsonBody(req) {
  return new Promise((resolve, reject) => {
    let raw = "";
    req.on("data", (chunk) => {
      raw += chunk;
      if (raw.length > 5 * 1024 * 1024) {
        reject(new Error("Payload muito grande."));
      }
    });
    req.on("end", () => {
      try {
        resolve(raw ? JSON.parse(raw) : {});
      } catch (error) {
        reject(new Error("JSON invalido."));
      }
    });
    req.on("error", reject);
  });
}

async function resolvePlanText(body) {
  if (body.text && body.text.trim()) {
    return body.text.trim();
  }

  if (!body.fileContentBase64) {
    throw new Error("Envie um texto ou arquivo.");
  }

  const buffer = Buffer.from(body.fileContentBase64, "base64");
  const mimeType = body.mimeType || "";
  const fileName = body.fileName || "arquivo";

  if (mimeType.includes("pdf") || fileName.toLowerCase().endsWith(".pdf")) {
    return extractPdfText(buffer);
  }

  return buffer.toString("utf8");
}

function extractPdfText(buffer) {
  const tempFile = path.join(os.tmpdir(), `diet-plan-${Date.now()}.pdf`);
  fs.writeFileSync(tempFile, buffer);

  try {
    const pythonScript = path.join(__dirname, "scripts", "extract_pdf.py");
    const pythonResult = spawnSync("python3", [pythonScript, tempFile], { encoding: "utf8" });
    const pythonOutput = (pythonResult.stdout || "").trim();

    if (pythonResult.status === 0 && pythonOutput) {
      return pythonOutput;
    }

    const stringsResult = spawnSync("strings", [tempFile], { encoding: "utf8" });
    const output = stringsResult.stdout || "";
    const lines = output
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.length > 2 && /[A-Za-z0-9]/.test(line));

    if (!lines.length) {
      throw new Error("Nao foi possivel extrair texto util do PDF. Cole o texto manualmente.");
    }

    return lines.join("\n");
  } finally {
    fs.unlinkSync(tempFile);
  }
}

function normalizeReviewedPlan(plan) {
  if (!plan || !Array.isArray(plan.items)) {
    throw new Error("Plano invalido.");
  }

  return {
    id: plan.id || Math.random().toString(36).slice(2, 10),
    originalText: plan.originalText || "",
    basePeriod: plan.basePeriod || "weekly",
    status: plan.status || "reviewed",
    items: plan.items
      .filter((item) => item && item.normalizedFood)
      .map((item) => {
        const normalizedFood = normalizeFoodName(item.normalizedFood || item.originalFood || "");
        const unit = normalizeUnit(item.unit || item.baseUnit || "unit");
        const base = toBaseUnit(item.quantity, unit);

        return {
          id: item.id || Math.random().toString(36).slice(2, 10),
          mealLabel: item.mealLabel || "Plano",
          originalText: item.originalText || item.originalFood || normalizedFood,
          originalFood: item.originalFood || normalizedFood,
          normalizedFood,
          quantity: Number(item.quantity) || 1,
          unit,
          baseQuantity: base.quantity,
          baseUnit: base.unit,
          frequencyPerWeek: Number(item.frequencyPerWeek) || 7,
          notes: item.notes || ""
        };
      })
  };
}
