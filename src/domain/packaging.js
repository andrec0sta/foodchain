const { BASE_PACKAGE_CATALOG } = require("./catalog");
const { normalizeFoodName, toBaseUnit } = require("./normalization");

function buildEffectiveCatalog(overrides = {}) {
  const catalog = { ...BASE_PACKAGE_CATALOG };

  for (const [food, packages] of Object.entries(overrides)) {
    catalog[normalizeFoodName(food)] = packages.map(normalizePackage);
  }

  return catalog;
}

function normalizePackage(entry) {
  const base = toBaseUnit(entry.quantity, entry.unit);
  return {
    quantity: base.quantity,
    unit: base.unit,
    packageType: entry.packageType || "embalagem",
    source: entry.source || "override",
    confidence: entry.confidence || "user"
  };
}

function generateWeeklyNeeds(planItems) {
  const grouped = new Map();

  for (const item of planItems) {
    const normalizedFood = normalizeFoodName(item.normalizedFood || item.originalFood || "");
    const base = item.baseQuantity && item.baseUnit
      ? { quantity: Number(item.baseQuantity), unit: item.baseUnit }
      : toBaseUnit(item.quantity, item.unit);
    const weeklyQuantity = base.quantity * Number(item.frequencyPerWeek || 0);
    const key = `${normalizedFood}::${base.unit}`;

    if (!grouped.has(key)) {
      grouped.set(key, {
        normalizedFood,
        baseUnit: base.unit,
        weeklyQuantity: 0,
        sourceItems: []
      });
    }

    const aggregate = grouped.get(key);
    aggregate.weeklyQuantity += weeklyQuantity;
    aggregate.sourceItems.push(item.id);
  }

  return Array.from(grouped.values()).sort((a, b) => a.normalizedFood.localeCompare(b.normalizedFood));
}

function resolvePackages(weeklyNeeds, overrides = {}) {
  const catalog = buildEffectiveCatalog(overrides);

  return weeklyNeeds.map((need) => {
    const packages = (catalog[need.normalizedFood] || []).filter((pkg) => pkg.unit === need.baseUnit);
    if (!packages.length) {
      return {
        ...need,
        status: "missing_package",
        recommendation: null,
        overage: 0
      };
    }

    const recommendation = chooseBestCombination(need.weeklyQuantity, packages);
    return {
      ...need,
      status: "resolved",
      recommendation,
      overage: recommendation.totalQuantity - need.weeklyQuantity
    };
  });
}

function chooseBestCombination(targetQuantity, packages) {
  const sorted = [...packages].sort((a, b) => a.quantity - b.quantity);
  const smallest = sorted[0].quantity;
  const maxQuantity = targetQuantity + smallest * 6;
  const dp = Array(maxQuantity + 1).fill(null);
  dp[0] = { totalPackages: 0, combination: [] };

  for (let total = 0; total <= maxQuantity; total += 1) {
    if (!dp[total]) {
      continue;
    }

    for (const pkg of sorted) {
      const next = total + pkg.quantity;
      if (next > maxQuantity) {
        continue;
      }

      const candidate = {
        totalPackages: dp[total].totalPackages + 1,
        combination: appendPackage(dp[total].combination, pkg)
      };

      if (!dp[next] || candidate.totalPackages < dp[next].totalPackages) {
        dp[next] = candidate;
      }
    }
  }

  let best = null;
  for (let total = targetQuantity; total <= maxQuantity; total += 1) {
    if (!dp[total]) {
      continue;
    }

    const overage = total - targetQuantity;
    const candidate = {
      totalQuantity: total,
      totalPackages: dp[total].totalPackages,
      overage,
      packages: dp[total].combination
    };

    if (!best || isBetterCombination(candidate, best)) {
      best = candidate;
    }
  }

  return best;
}

function appendPackage(existing, pkg) {
  const index = existing.findIndex((entry) => entry.packageType === pkg.packageType && entry.quantity === pkg.quantity && entry.unit === pkg.unit);
  if (index === -1) {
    return [...existing, { ...pkg, count: 1 }];
  }

  return existing.map((entry, currentIndex) => (
    currentIndex === index ? { ...entry, count: entry.count + 1 } : entry
  ));
}

function isBetterCombination(candidate, currentBest) {
  if (candidate.overage !== currentBest.overage) {
    return candidate.overage < currentBest.overage;
  }

  if (candidate.totalPackages !== currentBest.totalPackages) {
    return candidate.totalPackages < currentBest.totalPackages;
  }

  return candidate.totalQuantity < currentBest.totalQuantity;
}

module.exports = {
  buildEffectiveCatalog,
  generateWeeklyNeeds,
  resolvePackages
};
