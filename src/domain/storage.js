const fs = require("fs");
const path = require("path");

const DATA_DIR = path.join(process.cwd(), "data");
const LAST_PLAN_FILE = path.join(DATA_DIR, "last-plan.json");
const PACKAGE_OVERRIDES_FILE = path.join(DATA_DIR, "package-overrides.json");

function ensureDataDir() {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function readJson(filePath, fallback) {
  try {
    if (!fs.existsSync(filePath)) {
      return fallback;
    }

    const content = fs.readFileSync(filePath, "utf8");
    return JSON.parse(content);
  } catch (error) {
    return fallback;
  }
}

function writeJson(filePath, value) {
  ensureDataDir();
  fs.writeFileSync(filePath, JSON.stringify(value, null, 2));
}

function loadState() {
  return {
    lastPlan: readJson(LAST_PLAN_FILE, null),
    packageOverrides: readJson(PACKAGE_OVERRIDES_FILE, {})
  };
}

function savePlan(plan) {
  writeJson(LAST_PLAN_FILE, plan);
}

function savePackageOverrides(overrides) {
  writeJson(PACKAGE_OVERRIDES_FILE, overrides);
}

module.exports = {
  loadState,
  savePlan,
  savePackageOverrides
};
